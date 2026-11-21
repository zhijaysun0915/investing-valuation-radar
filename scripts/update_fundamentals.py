#!/usr/bin/env python3
"""
Daily Fundamentals Auto-Updater  (slow-but-real data, replaces hardcoded snapshots)

Free public sources (no API key):
  1. Yahoo Finance chart API (1y daily closes)  -> real 1W / 1M / 1Q / 1Y period returns
  2. Yahoo Finance quoteSummary (crumb session) -> analyst consensus target mean/high/low,
                                                   analyst count, recommendation, forward/trailing EPS
  3. TWSE / TPEX official open data             -> official P/E, P/B, dividend yield

Fair value: InvestingPro's Fair Value is a paid model with no public API, so it cannot be
auto-scraped. We therefore compute a transparent "auto model fair value" =
  mean of available components:
    a) PV of 12M analyst consensus target  (target / 1.10)
    b) Forward-EPS growth-adjusted price    (price * clamp(fwdEPS / ttmEPS, 0.7, 1.5))
    c) InvestingPro snapshot in index.html  (only if not stale: within 0.5x ~ 2x of a)+b))
The snapshot is kept for reference, and flagged as stale when it drifts too far.

Output: data/fundamentals.json   (pure standard library, python3.8+)
"""

import http.cookiejar
import json
import os
import re
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

TW_TZ = timezone(timedelta(hours=8))
UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'application/json,text/plain,*/*',
}
YAHOO_SYMBOL_OVERRIDES = {'0700': '0700.HK', '7203': '7203.T'}
REC_LABELS = {
    'strong_buy': '強力買入', 'buy': '買入', 'hold': '持有',
    'underperform': '減碼', 'sell': '賣出', 'strong_sell': '強力賣出',
}
SLEEP_SEC = 0.35  # be polite; slow is fine


class Http:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.crumb = None

    def get(self, url, timeout=20):
        req = urllib.request.Request(url, headers=UA)
        with self.opener.open(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', 'ignore')

    def get_json(self, url, retries=2):
        last = None
        for i in range(retries + 1):
            try:
                return json.loads(self.get(url))
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(1.5 * (i + 1))
        raise last

    def init_yahoo_crumb(self):
        try:
            self.get('https://fc.yahoo.com')
        except Exception:
            pass  # 404 is expected; it still sets the session cookie
        try:
            self.crumb = self.get('https://query1.finance.yahoo.com/v1/test/getcrumb').strip()
        except Exception as e:  # noqa: BLE001
            print(f'Warning: cannot obtain Yahoo crumb: {e}', file=sys.stderr)
            self.crumb = None


def raw(d, key):
    v = (d or {}).get(key)
    if isinstance(v, dict):
        return v.get('raw')
    return v


def to_float(s):
    try:
        v = float(str(s).replace(',', '').strip())
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def yahoo_symbol(code, market):
    if code in YAHOO_SYMBOL_OVERRIDES:
        return YAHOO_SYMBOL_OVERRIDES[code]
    m = (market or '').upper()
    if m in ('TPEX', 'OTC'):
        return f'{code}.TWO'
    if m == 'TWSE':
        return f'{code}.TW'
    return code  # US tickers


def load_universe(index_html):
    with open(index_html, 'r', encoding='utf-8') as f:
        content = f.read()
    stocks = {}
    m = re.search(r'const TAIWAN_CORE_UNIVERSE = (\[[\s\S]*?\]);', content)
    if m:
        for it in json.loads(m.group(1)):
            code = str(it.get('code', '')).strip()
            if code:
                stocks[code] = {
                    'code': code, 'name': it.get('name', ''), 'market': (it.get('market') or 'TWSE').upper(),
                    'snapshotFair': to_float(it.get('fairValue')),
                    'snapshotTarget': to_float(it.get('analystTarget')),
                }
    m = re.search(r'const KNOWN_SLUGS = \{([\s\S]*?)\};', content)
    if m:
        for blk in re.finditer(r"'([^']+)':\s*\{([^}]+)\}", m.group(1)):
            code, props = blk.group(1).strip(), blk.group(2)
            mk = re.search(r"market:\s*'([^']*)'", props)
            nm = re.search(r"name:\s*'([^']*)'", props)
            fv = re.search(r'proFairValue:\s*([0-9.]+)', props)
            at = re.search(r'analystTarget:\s*([0-9.]+)', props)
            s = stocks.setdefault(code, {'code': code, 'name': nm.group(1) if nm else code,
                                         'market': (mk.group(1) if mk else 'TWSE').upper(),
                                         'snapshotFair': None, 'snapshotTarget': None})
            if fv and not s.get('snapshotFair'):
                s['snapshotFair'] = float(fv.group(1))
            if at and not s.get('snapshotTarget'):
                s['snapshotTarget'] = float(at.group(1))
    return stocks


def fetch_official_ratios(h):
    """Official P/E, P/B, yield from TWSE + TPEX open data."""
    ratios = {}
    try:
        for r in h.get_json('https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL'):
            ratios[r.get('Code')] = {'pe': to_float(r.get('PEratio')), 'pb': to_float(r.get('PBratio')),
                                     'divYield': to_float(r.get('DividendYield'))}
    except Exception as e:  # noqa: BLE001
        print(f'Warning TWSE ratios: {e}', file=sys.stderr)
    try:
        for r in h.get_json('https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis'):
            ratios[r.get('SecuritiesCompanyCode')] = {'pe': to_float(r.get('PriceEarningRatio')),
                                                      'pb': to_float(r.get('PriceBookRatio')),
                                                      'divYield': to_float(r.get('YieldRatio'))}
    except Exception as e:  # noqa: BLE001
        print(f'Warning TPEX ratios: {e}', file=sys.stderr)
    return ratios


def fetch_history_perf(h, sym):
    """Real period returns from 1y daily closes."""
    d = h.get_json(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1y')
    res = d['chart']['result'][0]
    ts = res.get('timestamp') or []
    closes = res['indicators']['quote'][0].get('close') or []
    series = [(t, c) for t, c in zip(ts, closes) if c is not None and c > 0]
    if len(series) < 5:
        return None
    last_t, last_c = series[-1]

    def close_at_or_before(days):
        target = last_t - days * 86400
        cand = None
        for t, c in series:
            if t <= target:
                cand = c
            else:
                break
        return cand if cand is not None else series[0][1]

    def pct(base):
        return round((last_c / base - 1) * 100, 2) if base else None

    return {
        'basePrice': round(last_c, 4),
        'baseDate': datetime.fromtimestamp(last_t, TW_TZ).strftime('%Y-%m-%d'),
        'w1': pct(close_at_or_before(7)),
        'm1': pct(close_at_or_before(30)),
        'q1': pct(close_at_or_before(91)),
        'y1': pct(close_at_or_before(365)) if (last_t - series[0][0]) > 300 * 86400 else None,
    }


def fetch_analyst(h, sym):
    if not h.crumb:
        return None
    url = (f'https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}'
           f'?modules=financialData,defaultKeyStatistics&crumb={h.crumb}')
    d = h.get_json(url)
    r = d['quoteSummary']['result'][0]
    fd, ks = r.get('financialData', {}), r.get('defaultKeyStatistics', {})
    rec = fd.get('recommendationKey')
    return {
        'price': raw(fd, 'currentPrice'),
        'targetMean': raw(fd, 'targetMeanPrice'),
        'targetHigh': raw(fd, 'targetHighPrice'),
        'targetLow': raw(fd, 'targetLowPrice'),
        'analystCount': raw(fd, 'numberOfAnalystOpinions'),
        'recommendation': rec,
        'consensusLabel': REC_LABELS.get(rec or '', None),
        'forwardEps': raw(ks, 'forwardEps'),
        'trailingEps': raw(ks, 'trailingEps'),
    }


def compute_fair_value(price, analyst, snapshot):
    comps = []
    notes = []
    if price and analyst:
        tm, n = analyst.get('targetMean'), analyst.get('analystCount') or 0
        if tm and n >= 1 and 0.4 * price <= tm <= 3.0 * price:
            comps.append(tm / 1.10)
            notes.append('分析師目標折現')
        fe, te = analyst.get('forwardEps'), analyst.get('trailingEps')
        if fe and te and fe > 0 and te > 0 and price / te < 120:
            ratio = max(0.7, min(1.5, fe / te))
            comps.append(price * ratio)
            notes.append('預估EPS成長調整')
    snapshot_stale = None
    if snapshot:
        anchor = statistics.mean(comps) if comps else price
        if anchor and 0.5 * anchor <= snapshot <= 2.0 * anchor:
            comps.append(snapshot)
            notes.append('InvestingPro快照')
            snapshot_stale = False
        else:
            snapshot_stale = True
    if not comps:
        return None, None, None, snapshot_stale
    fair = round(statistics.mean(comps), 2)
    rng = f'{min(comps):,.2f} - {max(comps):,.2f}'
    return fair, rng, ' + '.join(notes), snapshot_stale


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(root, 'data', 'fundamentals.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    now = datetime.now(TW_TZ)

    old = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, 'r', encoding='utf-8') as f:
                old = json.load(f).get('stocks', {})
        except Exception:  # noqa: BLE001
            old = {}

    universe = load_universe(os.path.join(root, 'index.html'))
    h = Http()
    h.init_yahoo_crumb()
    ratios = fetch_official_ratios(h)
    print(f'Universe: {len(universe)} | official ratios: {len(ratios)} | crumb: {bool(h.crumb)}')

    out = {}
    ok_perf = ok_tgt = 0
    for code, s in universe.items():
        sym = yahoo_symbol(code, s['market'])
        rec = {'code': code, 'name': s['name'], 'market': s['market'], 'symbol': sym}
        prev = old.get(code, {})

        try:
            perf = fetch_history_perf(h, sym)
        except Exception as e:  # noqa: BLE001
            perf = None
            if sym.endswith('.TWO'):
                alt = sym[:-4] + '.TW'
                try:
                    perf = fetch_history_perf(h, alt)
                    sym = alt
                except Exception:
                    pass
            elif sym.endswith('.TW'):
                alt = sym[:-3] + '.TWO'
                try:
                    perf = fetch_history_perf(h, alt)
                    sym = alt
                except Exception:
                    pass
            if not perf:
                print(f'  [{code}] history failed: {e}', file=sys.stderr)
        rec['symbol'] = sym
        time.sleep(SLEEP_SEC)
        try:
            analyst = fetch_analyst(h, sym)
        except Exception as e:  # noqa: BLE001
            analyst = None
            print(f'  [{code}] analyst failed: {e}', file=sys.stderr)
        time.sleep(SLEEP_SEC)

        price = (perf or {}).get('basePrice') or (analyst or {}).get('price')
        if perf:
            rec['perf'] = perf
            ok_perf += 1
        elif prev.get('perf'):
            rec['perf'] = prev['perf']  # keep last good data rather than blanking

        if analyst and analyst.get('targetMean') and (analyst.get('analystCount') or 0) >= 1:
            rec.update({
                'analystTarget': round(analyst['targetMean'], 2),
                'analystHigh': analyst.get('targetHigh'),
                'analystLow': analyst.get('targetLow'),
                'analystCount': analyst.get('analystCount'),
                'consensusLabel': analyst.get('consensusLabel'),
                'analystSource': 'Yahoo Finance 分析師共識',
            })
            ok_tgt += 1
        elif prev.get('analystTarget'):
            for k in ('analystTarget', 'analystHigh', 'analystLow', 'analystCount', 'consensusLabel', 'analystSource'):
                if k in prev:
                    rec[k] = prev[k]
        if analyst:
            rec['forwardEps'] = analyst.get('forwardEps')
            rec['trailingEps'] = analyst.get('trailingEps')

        fair, rng, src, stale = compute_fair_value(price, analyst, s.get('snapshotFair'))
        if fair:
            rec.update({'fairValue': fair, 'fairRange': rng, 'fairSource': f'模型參考價（非 InvestingPro：{src}）'})
        rec['snapshotFair'] = s.get('snapshotFair')
        rec['snapshotStale'] = stale

        r = ratios.get(code)
        if r:
            if r.get('pe'):
                rec['pe'] = f"{r['pe']:.1f}x"
            if r.get('pb'):
                rec['pb'] = f"{r['pb']:.2f}x"
            if r.get('divYield') is not None:
                rec['divYield'] = r['divYield']
        elif analyst and price and analyst.get('trailingEps') and analyst['trailingEps'] > 0:
            rec['pe'] = f"{price / analyst['trailingEps']:.1f}x"

        rec['updatedAt'] = now.strftime('%Y-%m-%d %H:%M')
        out[code] = rec
        print(f"  {code} {s['name']}: price={price} fair={rec.get('fairValue')} "
              f"tgt={rec.get('analystTarget')} w1={(rec.get('perf') or {}).get('w1')} stale={stale}")

    data = {
        'version': '2.11.0',
        'updatedAt': now.strftime('%Y-%m-%d %H:%M:%S'),
        'timestamp': int(now.timestamp()),
        'total': len(out),
        'coverage': {'perf': ok_perf, 'analyst': ok_tgt},
        'sources': {
            'perf': 'Yahoo Finance 1Y daily closes',
            'analyst': 'Yahoo Finance quoteSummary (financialData)',
            'ratios': 'TWSE BWIBBU_ALL / TPEX peratio_analysis (official)',
            'fairValue': 'Auto model: PV(analyst target) + forward-EPS adjusted price + non-stale InvestingPro snapshot',
        },
        'stocks': out,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f'Done: {len(out)} stocks | perf {ok_perf} | analyst {ok_tgt} -> {out_path}')
    if ok_perf == 0 and ok_tgt == 0:
        sys.exit(1)  # total failure: do not commit an empty refresh


if __name__ == '__main__':
    main()
