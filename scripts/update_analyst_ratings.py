#!/usr/bin/env python3
"""
Automated Institutional Analyst Ratings & Price Targets Updater
- US stocks (NASDAQ / NYSE): Yahoo Finance `upgradeDowngradeHistory` (structured, real-time)
- TW / HK / JP stocks: Investing.com public equity & consensus-estimates pages via Jina Reader
- Outputs `data/analyst_ratings.json` (used by index.html for live-recalculated upside & daily auto-updates)
Zero external dependencies (pure Python 3 standard library).
"""

import concurrent.futures
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

TW_TZ = timezone(timedelta(hours=8))
UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'text/plain,application/json,*/*',
}

# Verified Investing.com slug overrides where default slug has no consensus table
SLUG_OVERRIDES = {
    '2330': 'taiwan-semicon',
    '2454': 'mediatek',
    '2317': 'hon-hai',
    '2327': 'yageo-corp',
    '2308': 'delta-electron',
    '6669': 'wiwynn',
    '2603': 'evergreen-mari',
    '8299': 'phison-electronics',
    '3037': 'unimicron-tech',
    '2382': 'quanta',
    '3231': 'wistron-corp',
    '2357': 'asustek-computer',
    '2303': 'united-micro',
    '3711': 'ase-industrial',
    '2379': 'realtek',
    '2408': 'nanya-tech',
    '2344': 'winbond',
    '3008': 'largan-precision',
    '2881': 'fubon-financial',
    '2882': 'cathay-financial',
    '2891': 'ctbc-financial',
    '2886': 'mega-financial',
    '2884': 'e.sun-financial',
    '2412': 'chunghwa-telecom',
    '0700': 'tencent-holdings-hk',
    '7203': 'toyota-motor-corp',
}

US_GRADE_MAP = {
    'strong buy': '強力買入',
    'buy': '買入',
    'outperform': '優於大盤',
    'overweight': '加碼',
    'market perform': '中立',
    'sector perform': '中立',
    'equal-weight': '中立',
    'equal weight': '中立',
    'neutral': '中立',
    'hold': '持有',
    'underperform': '劣於大盤',
    'underweight': '減碼',
    'sell': '賣出',
    'strong sell': '強力賣出',
}

US_ACTION_MAP = {
    'Raises': '調升',
    'Lowers': '調降',
    'Maintains': '持平',
    'Initiates': '新納入',
    'Reiterates': '重申',
    'Announces': '首次評級',
    'up': '升評',
    'down': '降評',
    'main': '維持',
    'reit': '重申',
    'init': '新納入',
}

# Match Investing.com Hong Kong Traditional Chinese markdown table rows:
# | Bernstein SocGen Group |  | 買入 | 6,520.00 | +60.99% | 5,500.00 | 持平 | 2026年11月13日 |
INVESTING_ROW_RE = re.compile(
    r'\|\s*([^|\[\]\n]{2,60}?)\s*\|\s*[^|\n]*\|\s*'
    r'(強力買入|買入|賣出|強力賣出|持有|加碼|減碼|中立|優於大盤|劣於大盤|Buy|Sell|Hold|Overweight|Outperform|Neutral|Underweight|Underperform)\s*\|\s*'
    r'([0-9,]+(?:\.[0-9]+)?)\s*\|\s*([+-]?[0-9.]+%?|-)\s*\|\s*([^|\n]*)\|\s*([^|\n]+?)\s*\|\s*(\d{4}年\d{2}月\d{2}日)\s*\|'
)


def load_stocks_with_slugs(index_html):
    with open(index_html, 'r', encoding='utf-8') as f:
        html = f.read()

    stocks = {}
    m_univ = re.search(r'const TAIWAN_CORE_UNIVERSE = (\[[\s\S]*?\]);', html)
    if m_univ:
        for item in json.loads(m_univ.group(1)):
            code = str(item.get('code', '')).strip().upper()
            if code:
                stocks[code] = {
                    'code': code,
                    'name': item.get('name', code),
                    'market': str(item.get('market', 'TWSE')).upper(),
                    'slug': SLUG_OVERRIDES.get(code, item.get('slug', '')),
                }

    m_ks = re.search(r'const KNOWN_SLUGS = \{([\s\S]*?)\n    \};', html)
    if m_ks:
        for line in m_ks.group(1).splitlines():
            cm = re.search(r"'([A-Z0-9]+)'\s*:\s*\{", line)
            if not cm:
                continue
            code = cm.group(1).upper()
            sm = re.search(r"slug:\s*'([^']+)'", line)
            nm = re.search(r"name:\s*'([^']+)'", line)
            mm = re.search(r"market:\s*'([^']+)'", line)
            if code not in stocks:
                stocks[code] = {
                    'code': code,
                    'name': nm.group(1) if nm else code,
                    'market': (mm.group(1) if mm else 'TWSE').upper(),
                    'slug': SLUG_OVERRIDES.get(code, sm.group(1) if sm else ''),
                }
            elif not stocks[code].get('slug') and sm:
                stocks[code]['slug'] = SLUG_OVERRIDES.get(code, sm.group(1))

    return stocks


class YahooClient:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.crumb = None

    def init_crumb(self):
        try:
            self.opener.open(urllib.request.Request('https://fc.yahoo.com', headers=UA), timeout=10)
        except Exception:
            pass
        try:
            req = urllib.request.Request('https://query1.finance.yahoo.com/v1/test/getcrumb', headers=UA)
            with self.opener.open(req, timeout=10) as r:
                self.crumb = r.read().decode('utf-8', 'ignore').strip()
        except Exception as e:
            print(f'Warning: Yahoo crumb failed: {e}', file=sys.stderr)

    def fetch_us_ratings(self, symbol):
        if not self.crumb:
            return []
        url = (
            f'https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}'
            f'?modules=upgradeDowngradeHistory,financialData&crumb={urllib.parse.quote(self.crumb)}'
        )
        req = urllib.request.Request(url, headers=UA)
        with self.opener.open(req, timeout=12) as r:
            d = json.loads(r.read().decode('utf-8', 'ignore'))
        res = (d.get('quoteSummary', {}).get('result') or [{}])[0]
        hist = (res.get('upgradeDowngradeHistory') or {}).get('history') or []
        out = []
        seen = set()
        for it in hist:
            tgt = it.get('currentPriceTarget')
            if not tgt or tgt <= 0:
                continue
            firm = (it.get('firm') or '').strip()
            if not firm:
                continue
            ep = it.get('epochGradeDate') or 0
            dt = datetime.fromtimestamp(ep, TW_TZ).strftime('%Y年%m月%d日') if ep else ''
            key = (firm, round(float(tgt), 2), dt)
            if key in seen:
                continue
            seen.add(key)
            grade_raw = (it.get('toGrade') or '').strip()
            rating = US_GRADE_MAP.get(grade_raw.lower(), grade_raw or '買入')
            pt_act = it.get('priceTargetAction') or it.get('action') or ''
            action = US_ACTION_MAP.get(pt_act, pt_act or '持平')
            prev_t = it.get('priorPriceTarget')
            out.append({
                'firm': firm,
                'rating': rating,
                'target': f'{float(tgt):,.2f}',
                'targetNum': round(float(tgt), 2),
                'prevTarget': f'{float(prev_t):,.2f}' if (prev_t and prev_t > 0) else '—',
                'action': action,
                'date': dt,
            })
            if len(out) >= 8:
                break
        return out


def parse_investing_ratings(md):
    ratings = []
    seen = set()
    for m in INVESTING_ROW_RE.finditer(md):
        firm = m.group(1).strip()
        if not firm or firm in ('公司', '名稱', '持有者') or '---' in firm:
            continue
        rating = m.group(2).strip()
        target_str = m.group(3).strip()
        try:
            target_num = float(target_str.replace(',', ''))
        except ValueError:
            continue
        if target_num <= 0:
            continue
        upside = m.group(4).strip()
        prev_t = m.group(5).strip() or '—'
        action = m.group(6).strip()
        date_str = m.group(7).strip()
        key = (firm, target_str, date_str)
        if key in seen:
            continue
        seen.add(key)
        ratings.append({
            'firm': firm,
            'rating': rating,
            'target': f'{target_num:,.2f}',
            'targetNum': round(target_num, 2),
            'upside': upside,
            'prevTarget': prev_t,
            'action': action,
            'date': date_str,
        })
        if len(ratings) >= 8:
            break
    return ratings


PRIORITY_CODES = [
    '2330', '2454', '2317', '2308', '6669', '2327', '2603', '8299',
    '3037', '2382', '3231', '2357', '2303', '3711', '2379', '3034',
    '2408', '2344', '3008', '2881', '2882', '2891', '2886', '2884',
    '2412', '2383', '2368', '3017', '6274', '8046', '2395', '2345',
    '3006', '2492', '0700', '7203',
]


def fetch_investing_ratings_for_stock(code, info):
    slug = (info.get('slug') or '').strip()
    if not slug:
        return code, [], None

    url = f'https://r.jina.ai/https://hk.investing.com/equities/{slug}'
    for attempt in range(2):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0',
                    'X-Wait-For-Selector': 'h1',
                },
            )
            with urllib.request.urlopen(req, timeout=22) as r:
                md = r.read().decode('utf-8', 'ignore')
            rows = parse_investing_ratings(md)
            if rows:
                return code, rows, 'Investing.com 公開分析師共識表'
            return code, [], None
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                time.sleep(12)
                continue
            return code, [], None
        except Exception:
            if attempt == 0:
                time.sleep(3)
                continue
            return code, [], None
    return code, [], None


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_html = os.path.join(root, 'index.html')
    out_path = os.path.join(root, 'data', 'analyst_ratings.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    now = datetime.now(TW_TZ)

    limit_inv = None
    if '--limit' in sys.argv:
        try:
            limit_inv = int(sys.argv[sys.argv.index('--limit') + 1])
        except Exception:
            limit_inv = None

    # Preserve existing valid ratings so temporary rate-limits don't wipe prior data
    existing = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, 'r', encoding='utf-8') as f:
                existing = json.load(f).get('stocks', {})
        except Exception:
            existing = {}

    fund_path = os.path.join(root, 'data', 'fundamentals.json')
    analyst_covered = set()
    if os.path.exists(fund_path):
        try:
            fd = json.load(open(fund_path, 'r', encoding='utf-8')).get('stocks', {})
            for c, rec in fd.items():
                if (rec.get('analystCount') or 0) >= 1 or (rec.get('analystTarget') or 0) > 0:
                    analyst_covered.add(c)
        except Exception:
            pass

    stocks = load_stocks_with_slugs(index_html)
    print(f'Loaded {len(stocks)} stocks ({len(analyst_covered)} with analyst coverage)')

    out_stocks = dict(existing)

    # 1. US stocks via Yahoo Finance upgradeDowngradeHistory
    yc = YahooClient()
    yc.init_crumb()
    us_ok = 0
    for code, info in stocks.items():
        if info['market'] in ('NASDAQ', 'NYSE', 'AMEX', 'US'):
            try:
                rows = yc.fetch_us_ratings(code)
                if rows:
                    out_stocks[code] = {
                        'code': code,
                        'name': info['name'],
                        'source': 'Yahoo Finance 華爾街投行評級紀錄',
                        'updatedAt': now.strftime('%Y-%m-%d %H:%M'),
                        'ratings': rows,
                    }
                    us_ok += 1
                    print(f'  [US] {code:5s} {info["name"][:8]:8s}: {len(rows)} rows (latest {rows[0]["date"]})')
            except Exception as e:
                print(f'  [US] {code} failed: {e}', file=sys.stderr)
            time.sleep(0.15)

    # 2. TW / HK / JP stocks via Investing.com (priority-ordered, polite 3.2s pacing for Jina free tier)
    prio_rank = {c: i for i, c in enumerate(PRIORITY_CODES)}
    non_us = [
        (c, info) for c, info in stocks.items()
        if info['market'] not in ('NASDAQ', 'NYSE', 'AMEX', 'US')
        and info.get('slug')
        and (not analyst_covered or c in analyst_covered)
    ]
    non_us.sort(key=lambda kv: (prio_rank.get(kv[0], 9999), kv[0]))
    if limit_inv is not None:
        non_us = non_us[:limit_inv]

    print(f'Fetching Investing.com institutional tables for {len(non_us)} TW/HK/JP stocks (polite pacing)...', flush=True)
    inv_ok = 0
    for idx, (c, info) in enumerate(non_us, 1):
        code, rows, src = fetch_investing_ratings_for_stock(c, info)
        if rows:
            out_stocks[code] = {
                'code': code,
                'name': info['name'],
                'source': src,
                'updatedAt': now.strftime('%Y-%m-%d %H:%M'),
                'ratings': rows,
            }
            inv_ok += 1
            print(f'  [INV {idx:3d}/{len(non_us)}] {code:5s} {info["name"][:6]:6s}: {len(rows)} rows (latest {rows[0]["date"]})', flush=True)
        elif idx % 10 == 0 or idx == len(non_us):
            print(f'  [INV {idx:3d}/{len(non_us)}] progress (fetched {inv_ok} tables)', flush=True)
        time.sleep(3.2)

    payload = {
        'version': '2.15.0',
        'updatedAt': now.strftime('%Y-%m-%d %H:%M:%S'),
        'timestamp': int(now.timestamp()),
        'total': len(out_stocks),
        'freshFetched': {'us': us_ok, 'investing': inv_ok},
        'stocks': out_stocks,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'Done! Saved {len(out_stocks)} stocks institutional ratings (fresh US={us_ok}, Investing={inv_ok}) -> {out_path}')


if __name__ == '__main__':
    main()
