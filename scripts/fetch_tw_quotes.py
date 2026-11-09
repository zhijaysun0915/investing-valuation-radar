#!/usr/bin/env python3
"""
Multi-Market Stock Quotes & Valuation Benchmarks Fetcher
- TWSE / TPEX (Taiwan): Fetches batch quotes via TWSE MIS & official issued shares for Market Cap.
- US (NASDAQ / NYSE) & Global (HKEX / TSE): Fetches live market prices via Yahoo Finance.
- Detects local market session (OPEN / PRE / POST / CLOSED / WEEKEND).
- Outputs `data/quotes.json`.
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
US_TZ = timezone(timedelta(hours=-5)) # Eastern Standard Time (EST)
JP_TZ = timezone(timedelta(hours=9))

def get_market_session(market, dt=None):
    if dt is None:
        dt = datetime.now(timezone.utc)
    m = (market or 'TWSE').upper()

    if m in ('TWSE', 'TPEX', 'OTC'):
        tw_dt = dt.astimezone(TW_TZ)
        if tw_dt.weekday() >= 5:
            return 'WEEKEND', '週末休市', '09:00~13:30 (UTC+8)', False
        hm = tw_dt.hour * 60 + tw_dt.minute
        if 9 * 60 <= hm <= 13 * 60 + 30:
            return 'OPEN', '盤中動態撮合', '09:00~13:30', True
        if 8 * 60 + 30 <= hm < 9 * 60:
            return 'PRE', '盤前試撮', '08:30~09:00', False
        return 'CLOSED', '今日已收盤', '13:30 收盤', False

    if m in ('NASDAQ', 'NYSE', 'AMEX'):
        us_dt = dt.astimezone(US_TZ)
        if us_dt.weekday() >= 5:
            return 'WEEKEND', '美股週末休市', '美東 09:30~16:00', False
        hm = us_dt.hour * 60 + us_dt.minute
        if 9 * 60 + 30 <= hm <= 16 * 60:
            return 'OPEN', '美股盤中交易', '美東 09:30~16:00 (台 22:30~05:00)', True
        if 4 * 60 <= hm < 9 * 60 + 30:
            return 'PRE', '美股盤前交易', '美東 04:00~09:30', True
        if 16 * 60 < hm <= 20 * 60:
            return 'POST', '美股盤後交易', '美東 16:00~20:00', False
        return 'CLOSED', '美股已收盤', '美東 16:00 收盤', False

    if m == 'HKEX':
        hk_dt = dt.astimezone(TW_TZ)
        if hk_dt.weekday() >= 5:
            return 'WEEKEND', '港股週末休市', '09:30~16:00', False
        hm = hk_dt.hour * 60 + hk_dt.minute
        if (9 * 60 + 30 <= hm <= 12 * 60) or (13 * 60 <= hm <= 16 * 60):
            return 'OPEN', '港股盤中交易', '09:30~16:00', True
        return 'CLOSED', '港股已收盤', '16:00 收盤', False

    if m == 'TSE':
        jp_dt = dt.astimezone(JP_TZ)
        if jp_dt.weekday() >= 5:
            return 'WEEKEND', '日股週末休市', '09:00~15:30 (JST)', False
        hm = jp_dt.hour * 60 + jp_dt.minute
        if (9 * 60 <= hm <= 11 * 60 + 30) or (12 * 60 + 30 <= hm <= 15 * 60 + 30):
            return 'OPEN', '日股盤中交易', '09:00~15:30 (JST)', True
        return 'CLOSED', '日股已收盤', '15:30 收盤', False

    return 'CLOSED', '休市', '—', False

def get_shares_map():
    """Fetch official total issued shares from TWSE and TPEX open data."""
    shares = {}
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

def fetch_quotes_batch(symbol_list):
    joined = '|'.join(symbol_list)
    timestamp = int(time.time() * 1000)
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={joined}&_={timestamp}"
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            'Accept': 'application/json',
            'Referer': 'https://mis.twse.com.tw/'
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))

def parse_price_item(item):
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
        'market': 'TWSE' if item.get('ex') == 'tse' else 'TPEX',
        'currency': 'NT$'
    }

def fetch_global_quote(symbol, market, name, currency):
    """Fetch global stock quote (US, HK, JP) via Yahoo Finance API."""
    ticker_map = {
        '0700': '0700.HK',
        '7203': '7203.T'
    }
    y_ticker = ticker_map.get(symbol, symbol)
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{y_ticker}?interval=1d&range=1d"
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            meta = data['chart']['result'][0]['meta']
            price = round(float(meta.get('regularMarketPrice', 0)), 2)
            prev_close = round(float(meta.get('chartPreviousClose', price)), 2)
            change = round(price - prev_close, 2)
            change_pct = round((change / prev_close) * 100, 2) if prev_close > 0 else 0.0
            
            # Approximate Market Cap if available
            market_cap_val = 0
            cap_str = '—'
            
            return {
                'code': symbol,
                'name': name,
                'price': price,
                'prevClose': prev_close,
                'change': change,
                'changePct': change_pct,
                'open': round(float(meta.get('regularMarketOpen', price)), 2),
                'high': round(float(meta.get('regularMarketDayHigh', price)), 2),
                'low': round(float(meta.get('regularMarketDayLow', price)), 2),
                'volume': int(meta.get('regularMarketVolume', 0)),
                'time': datetime.now(TW_TZ).strftime('%H:%M:%S'),
                'market': market,
                'currency': currency,
                'marketCap': cap_str,
                'marketCapVal': market_cap_val
            }
    except Exception as e:
        print(f"Error fetching global quote {symbol}: {e}", file=sys.stderr)
        return None

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_html = os.path.join(root_dir, 'index.html')
    data_dir = os.path.join(root_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    output_path = os.path.join(data_dir, 'quotes.json')

    now_utc = datetime.now(timezone.utc)
    now_tw = now_utc.astimezone(TW_TZ)

    # 1. Evaluate Regional Markets status
    market_sessions = {
        'TWSE': get_market_session('TWSE', now_utc),
        'TPEX': get_market_session('TPEX', now_utc),
        'NASDAQ': get_market_session('NASDAQ', now_utc),
        'NYSE': get_market_session('NYSE', now_utc),
        'HKEX': get_market_session('HKEX', now_utc),
        'TSE': get_market_session('TSE', now_utc),
    }

    print(f"[{now_tw.strftime('%Y-%m-%d %H:%M:%S')}] Regional Markets Status:")
    for m, (stat, desc, hrs, is_live) in market_sessions.items():
        print(f"  {m:7s}: {stat:7s} ({desc}) [{hrs}] Live: {is_live}")

    # Fetch issued shares for Taiwan stocks
    shares_map = get_shares_map()

    # Load known stocks from index.html
    # ...
    symbols_dict = {}
    with open(index_html, 'r', encoding='utf-8') as f:
        content = f.read()

    m_universe = re.search(r'const TAIWAN_CORE_UNIVERSE = (\[[\s\S]*?\]);', content)
    if m_universe:
        try:
            for item in json.loads(m_universe.group(1)):
                code = str(item.get('code', '')).strip()
                if code:
                    symbols_dict[code] = {
                        'code': code,
                        'name': item.get('name', ''),
                        'market': str(item.get('market', 'TWSE')).upper(),
                        'slug': item.get('slug', ''),
                        'currency': 'NT$'
                    }
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

    # Add global stocks
    global_stocks = {
        'NVDA': {'name': '英偉達 (NVIDIA)', 'market': 'NASDAQ', 'currency': 'USD'},
        'AAPL': {'name': '蘋果 (Apple)', 'market': 'NASDAQ', 'currency': 'USD'},
        'TSLA': {'name': '特斯拉 (Tesla)', 'market': 'NASDAQ', 'currency': 'USD'},
        'MSFT': {'name': '微軟 (Microsoft)', 'market': 'NASDAQ', 'currency': 'USD'},
        'AMD':  {'name': '超微 (AMD)', 'market': 'NASDAQ', 'currency': 'USD'},
        'AVGO': {'name': '博通 (Broadcom)', 'market': 'NASDAQ', 'currency': 'USD'},
        'TSM':  {'name': '台積電 ADR', 'market': 'NYSE', 'currency': 'USD'},
        '0700': {'name': '騰訊控股', 'market': 'HKEX', 'currency': 'HK$'},
        '7203': {'name': '豐田汽車 (Toyota)', 'market': 'TSE', 'currency': '¥'},
        '3701': {'name': '大眾控', 'market': 'TWSE', 'currency': 'NT$'},
        '2342': {'name': '茂矽', 'market': 'TWSE', 'currency': 'NT$'},
        '4716': {'name': '大立高', 'market': 'TPEX', 'currency': 'NT$'},
        '4989': {'name': '榮科', 'market': 'TWSE', 'currency': 'NT$'},
        '6443': {'name': '元晶', 'market': 'TWSE', 'currency': 'NT$'},
    }
    for code, info in global_stocks.items():
        if code not in symbols_dict:
            symbols_dict[code] = {
                'code': code,
                'name': info['name'],
                'market': info['market'],
                'currency': info['currency']
            }

    quotes = {}

    # Query Taiwan stocks in batches
    tw_symbols = []
    for code, info in symbols_dict.items():
        mkt = info.get('market', 'TWSE')
        if mkt in ('TWSE', 'TPEX', 'OTC'):
            prefix = 'otc' if mkt in ('TPEX', 'OTC') else 'tse'
            if code in ('6533', '6589'):
                prefix = 'tse'
            tw_symbols.append(f"{prefix}_{code}.tw")

    chunk_size = 25
    chunks = [tw_symbols[i:i + chunk_size] for i in range(0, len(tw_symbols), chunk_size)]

    for chunk in chunks:
        try:
            resp_data = fetch_quotes_batch(chunk)
            for item in resp_data.get('msgArray', []):
                parsed = parse_price_item(item)
                if parsed and parsed.get('code'):
                    code = parsed['code']
                    if code in symbols_dict and symbols_dict[code].get('name'):
                        parsed['name'] = symbols_dict[code]['name']
                    
                    sh = shares_map.get(code, 0)
                    price = parsed['price']
                    market_cap_ntd = round(price * sh) if (sh > 0 and price > 0) else 0
                    market_cap_yi = round(market_cap_ntd / 100_000_000, 1)
                    market_cap_zhao = round(market_cap_ntd / 1_000_000_000_000, 2)
                    
                    if market_cap_zhao >= 1.0:
                        cap_str = f"{market_cap_zhao} 兆"
                    elif market_cap_yi >= 1.0:
                        cap_str = f"{market_cap_yi:,.1f} 億"
                    else:
                        cap_str = "—"

                    parsed['shares'] = sh
                    parsed['marketCapVal'] = market_cap_ntd
                    parsed['marketCap'] = cap_str

                    # Market session info
                    stat, desc, hrs, is_live = market_sessions.get(parsed['market'], ('CLOSED', '已收盤', '', False))
                    parsed['sessionStatus'] = stat
                    parsed['sessionDesc'] = desc
                    parsed['sessionHours'] = hrs
                    parsed['isSessionLive'] = is_live

                    quotes[code] = parsed
            time.sleep(0.12)
        except Exception as e:
            print(f"Error chunk: {e}", file=sys.stderr)

    # Rank Taiwan stocks by marketCap
    tw_stocks_sorted = sorted(
        [q for q in quotes.values() if q.get('market') in ('TWSE', 'TPEX')],
        key=lambda x: x.get('marketCapVal', 0),
        reverse=True
    )
    for rank_idx, item in enumerate(tw_stocks_sorted, 1):
        code = item['code']
        quotes[code]['marketCapRank'] = rank_idx
        quotes[code]['isTop100Cap'] = (rank_idx <= 100)

    # Query Global Stocks
    print("Fetching Global stocks (US, HK, JP)...")
    for code, info in global_stocks.items():
        if info['market'] not in ('TWSE', 'TPEX'):
            gq = fetch_global_quote(code, info['market'], info['name'], info['currency'])
            if gq:
                stat, desc, hrs, is_live = market_sessions.get(info['market'], ('CLOSED', '已收盤', '', False))
                gq['sessionStatus'] = stat
                gq['sessionDesc'] = desc
                gq['sessionHours'] = hrs
                gq['isSessionLive'] = is_live
                quotes[code] = gq

    output_data = {
        'version': '2.8.0',
        'updatedAt': now_tw.strftime('%Y-%m-%d %H:%M:%S'),
        'timestamp': int(now_tw.timestamp()),
        'total': len(quotes),
        'marketSessions': {
            m: {'status': s[0], 'desc': s[1], 'hours': s[2], 'isLive': s[3]}
            for m, s in market_sessions.items()
        },
        'quotes': quotes
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"Successfully wrote {len(quotes)} regional quotes to {output_path}!")

if __name__ == '__main__':
    main()
