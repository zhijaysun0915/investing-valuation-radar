#!/usr/bin/env python3
"""
Taiwan Stock Exchange (TWSE) & Taipei Exchange (TPEX) Real-time Quotes Fetcher
Queries official TWSE MIS API in batches and computes official Market Cap (市值)
from TWSE & TPEX official open data. Outputs `data/quotes.json`.
Zero external dependencies (pure standard library python3).
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

TW_TZ = timezone(timedelta(hours=8))

def get_shares_map():
    """Fetch official total issued shares from TWSE and TPEX open data."""
    shares = {}
    # TWSE Listed Companies Base Info
    try:
        req = urllib.request.Request(
            'https://openapi.twse.com.tw/v1/opendata/t187ap03_L',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            for c in json.loads(resp.read().decode('utf-8')):
                code = c.get('公司代號')
                s_str = c.get('已發行普通股數或TDR原股發行股數')
                if code and s_str:
                    try:
                        shares[code] = int(str(s_str).replace(',', '').strip())
                    except:
                        pass
    except Exception as e:
        print(f"Warning fetching TWSE shares: {e}", file=sys.stderr)

    # TPEX OTC Companies Base Info
    try:
        req = urllib.request.Request(
            'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            for c in json.loads(resp.read().decode('utf-8')):
                code = c.get('SecuritiesCompanyCode')
                s_str = c.get('IssueShares')
                if code and s_str:
                    try:
                        shares[code] = int(str(s_str).replace(',', '').strip())
                    except:
                        pass
    except Exception as e:
        print(f"Warning fetching TPEX shares: {e}", file=sys.stderr)

    return shares

def get_symbols_from_index_html(index_path):
    symbols = {}
    if not os.path.exists(index_path):
        return symbols

    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Parse TAIWAN_CORE_UNIVERSE
    m_universe = re.search(r'const TAIWAN_CORE_UNIVERSE = (\[[\s\S]*?\]);', content)
    if m_universe:
        try:
            universe = json.loads(m_universe.group(1))
            for item in universe:
                code = str(item.get('code', '')).strip()
                if code:
                    market = str(item.get('market', 'TWSE')).upper()
                    symbols[code] = {
                        'code': code,
                        'name': item.get('name', ''),
                        'market': market,
                        'slug': item.get('slug', '')
                    }
        except Exception as e:
            print(f"Warning parsing universe: {e}", file=sys.stderr)

    # 2. Parse KNOWN_SLUGS
    m_slugs = re.search(r'const KNOWN_SLUGS = \{([\s\S]*?)\};', content)
    if m_slugs:
        slug_matches = re.findall(r"'(\d+)':\s*\{\s*name:\s*'([^']+)',\s*slug:\s*'([^']+)',\s*market:\s*'([^']+)'", m_slugs.group(1))
        for code, name, slug, market in slug_matches:
            if code not in symbols:
                symbols[code] = {
                    'code': code,
                    'name': name,
                    'market': market.upper(),
                    'slug': slug
                }

    # 3. Extra monitored stocks (like 3701, 2342, 4716, 4989, 6443)
    extra_watchlist = {
        '3701': {'name': '大眾控', 'market': 'TWSE', 'slug': 'fic-global-inc'},
        '2342': {'name': '茂矽', 'market': 'TWSE', 'slug': 'mosel-vitelic'},
        '4716': {'name': '大立高', 'market': 'TPEX', 'slug': 'dali-chemical'},
        '4989': {'name': '榮科', 'market': 'TWSE', 'slug': 'unitech-printed'},
        '6443': {'name': '元晶', 'market': 'TWSE', 'slug': 'tsec-corp'},
        '2301': {'name': '光寶科', 'market': 'TWSE', 'slug': 'lite-on-techno'},
    }
    for code, info in extra_watchlist.items():
        if code not in symbols:
            symbols[code] = {
                'code': code,
                'name': info['name'],
                'market': info['market'],
                'slug': info['slug']
            }

    return symbols

def fetch_quotes_batch(symbol_list):
    """Fetch a list of symbols from TWSE MIS API. symbol_list is ['tse_2330.tw', 'otc_8299.tw', ...]"""
    joined = '|'.join(symbol_list)
    timestamp = int(time.time() * 1000)
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={joined}&_={timestamp}"
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Referer': 'https://mis.twse.com.tw/stock/fibest.jsp?lang=zh_tw'
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))

def parse_price_item(item):
    """Extract standard pricing numbers from TWSE MIS response item."""
    code = item.get('c', '').strip()
    if not code:
        return None

    name = item.get('n', '').strip()
    
    y_raw = item.get('y', '0')
    try:
        prev_close = float(y_raw) if y_raw and y_raw != '-' else 0.0
    except (ValueError, TypeError):
        prev_close = 0.0

    price = None
    z = item.get('z')
    trade_z = item.get('trade', {}).get('z') if isinstance(item.get('trade'), dict) else None
    a_first = item.get('a', '').split('_')[0] if item.get('a') else None
    b_first = item.get('b', '').split('_')[0] if item.get('b') else None

    for cand in [z, trade_z, a_first, b_first, item.get('h'), item.get('o')]:
        if cand and cand != '-' and cand != '0.0000':
            try:
                val = float(cand)
                if val > 0:
                    price = val
                    break
            except (ValueError, TypeError):
                pass

    if not price and prev_close > 0:
        price = prev_close

    if not price:
        return None

    change = round(price - prev_close, 2) if prev_close > 0 else 0.0
    change_pct = round((change / prev_close) * 100, 2) if prev_close > 0 else 0.0

    def parse_float(val, fallback=price):
        if val and val != '-':
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
        return fallback

    def parse_int(val, fallback=0):
        if val and val != '-':
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
        return fallback

    return {
        'code': code,
        'name': name,
        'price': round(price, 2),
        'prevClose': round(prev_close, 2),
        'change': change,
        'changePct': change_pct,
        'open': parse_float(item.get('o')),
        'high': parse_float(item.get('h')),
        'low': parse_float(item.get('l')),
        'volume': parse_int(item.get('v')),
        'time': item.get('t', ''),
        'market': 'TWSE' if item.get('ex') == 'tse' else 'TPEX'
    }

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_html = os.path.join(root_dir, 'index.html')
    data_dir = os.path.join(root_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    output_path = os.path.join(data_dir, 'quotes.json')

    print(f"[{datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')}] Parsing stock universe from index.html...")
    symbols_dict = get_symbols_from_index_html(index_html)
    print(f"Found {len(symbols_dict)} unique stocks to monitor.")

    # Fetch official total issued shares
    print("Fetching official total shares from TWSE & TPEX...")
    shares_map = get_shares_map()
    print(f"Retrieved shares data for {len(shares_map)} companies.")

    query_symbols = []
    for code, info in symbols_dict.items():
        mkt = info.get('market', 'TWSE')
        prefix = 'otc' if mkt in ('TPEX', 'OTC') else 'tse'
        if code in ('6533', '6589'):
            prefix = 'tse'
        query_symbols.append(f"{prefix}_{code}.tw")

    chunk_size = 25
    chunks = [query_symbols[i:i + chunk_size] for i in range(0, len(query_symbols), chunk_size)]
    quotes = {}

    print(f"Querying TWSE/TPEX MIS API across {len(chunks)} batches...")
    for i, chunk in enumerate(chunks):
        try:
            resp_data = fetch_quotes_batch(chunk)
            msg_array = resp_data.get('msgArray', [])
            for item in msg_array:
                parsed = parse_price_item(item)
                if parsed and parsed.get('code'):
                    code = parsed['code']
                    if code in symbols_dict and symbols_dict[code].get('name'):
                        parsed['name'] = symbols_dict[code]['name']
                    
                    # Calculate Market Capitalization
                    sh = shares_map.get(code, 0)
                    price = parsed['price']
                    market_cap_ntd = round(price * sh) if (sh > 0 and price > 0) else 0
                    market_cap_yi = round(market_cap_ntd / 100_000_000, 1) # 億元
                    market_cap_zhao = round(market_cap_ntd / 1_000_000_000_000, 2) # 兆元
                    
                    if market_cap_zhao >= 1.0:
                        cap_str = f"{market_cap_zhao} 兆"
                    elif market_cap_yi >= 1.0:
                        cap_str = f"{market_cap_yi:,.1f} 億"
                    else:
                        cap_str = "—"

                    parsed['shares'] = sh
                    parsed['marketCapVal'] = market_cap_ntd
                    parsed['marketCap'] = cap_str

                    quotes[code] = parsed
            time.sleep(0.15)
        except Exception as e:
            print(f"Error fetching chunk {i}: {e}", file=sys.stderr)

    # Rank all stocks by Market Capitalization
    sorted_by_cap = sorted(
        quotes.values(),
        key=lambda x: x.get('marketCapVal', 0),
        reverse=True
    )

    # Assign marketCapRank (1..N) and isTop100Cap flag
    for rank_idx, item in enumerate(sorted_by_cap, 1):
        code = item['code']
        quotes[code]['marketCapRank'] = rank_idx
        quotes[code]['isTop100Cap'] = (rank_idx <= 100)

    now_tw = datetime.now(TW_TZ)
    output_data = {
        'version': '2.6.0',
        'updatedAt': now_tw.strftime('%Y-%m-%d %H:%M:%S'),
        'timestamp': int(now_tw.timestamp()),
        'total': len(quotes),
        'marketStatus': 'OPEN' if (9 <= now_tw.hour < 13 or (now_tw.hour == 13 and now_tw.minute <= 30)) and now_tw.weekday() < 5 else 'CLOSED',
        'quotes': quotes
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"Successfully computed market caps and wrote {len(quotes)} live quotes to {output_path}!")

if __name__ == '__main__':
    main()
