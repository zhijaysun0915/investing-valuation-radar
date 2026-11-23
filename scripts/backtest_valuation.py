#!/usr/bin/env python3
"""
Reproducible Zero-Look-Ahead Out-of-Sample Empirical Backtest (2023-2026)
Directly imports and evaluates the exact production valuation engine in
`scripts/update_fundamentals.py` across 4 annual/YTD cohorts on the 127-stock universe.

Usage:
  python3 scripts/backtest_valuation.py            # uses cached /tmp/backtest_cache.json if present, else fetches
  python3 scripts/backtest_valuation.py --refresh  # force fresh historical download from Yahoo Finance
"""

import json
import math
import os
import statistics
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update_fundamentals as uf  # noqa: E402

CACHE_PATH = '/tmp/backtest_cache.json'
ANNUAL_TYPES = (
    'annualNetIncome,annualBasicEPS,annualDilutedEPS,annualStockholdersEquity,'
    'annualFreeCashFlow,annualOperatingCashFlow,annualEBITDA,annualTotalDebt,'
    'annualCashAndCashEquivalents,annualOrdinarySharesNumber,annualCashDividendsPaid,'
    'annualTotalRevenue,annualGrossProfit,annualTotalAssets'
)


def fetch_historical_cache(root_dir):
    h = uf.Http()
    h.init_yahoo_crumb()
    universe = uf.load_universe(os.path.join(root_dir, 'index.html'))
    cache = {}
    for idx, (code, info) in enumerate(universe.items(), 1):
        sym = uf.yahoo_symbol(code, info['market'])
        rec = {'code': code, 'name': info['name'], 'market': info['market'], 'symbol': sym}
        try:
            ch = h.get_json(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1wk&range=5y')
            res = ch['chart']['result'][0]
            ts = res.get('timestamp') or []
            adj = (res['indicators'].get('adjclose') or [{}])[0].get('adjclose')
            cls = res['indicators']['quote'][0].get('close') or []
            rec['prices'] = [[t, round(c, 4) if c else None, round(a, 4) if a else None]
                             for t, c, a in zip(ts, cls, adj or [None] * len(ts)) if c is not None]
        except Exception as e:  # noqa: BLE001
            rec['prices_err'] = str(e)
        try:
            fs = h.get_json(
                f'https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{sym}'
                f'?type={ANNUAL_TYPES}&period1=1577836800&period2=1900000000'
            )
            fin = {}
            for item in fs['timeseries']['result']:
                t = item['meta']['type'][0]
                fin[t] = {x['asOfDate'][:4]: x['reportedValue']['raw']
                          for x in item.get(t, []) if x.get('reportedValue') and 'raw' in x['reportedValue']}
            rec['annual'] = fin
        except Exception as e:  # noqa: BLE001
            rec['annual_err'] = str(e)
        try:
            rec['qs'] = uf.fetch_quote_summary(h, sym)
        except Exception as e:  # noqa: BLE001
            rec['qs_err'] = str(e)
        cache[code] = rec
        if idx % 25 == 0 or idx == len(universe):
            print(f'Fetched {idx}/{len(universe)} stocks...', flush=True)
        time.sleep(0.2)
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)
    return cache


def price_at_date(prices, target_ts):
    cand = None
    for t, c, a in prices:
        if t <= target_ts:
            cand = (c, a if a else c)
        else:
            break
    return cand


def spearman_corr(xs, ys):
    n = len(xs)
    if n < 5:
        return None

    def ranks(vals):
        order = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg_r = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg_r
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den > 0 else 0.0


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if '--refresh' in sys.argv or not os.path.exists(CACHE_PATH):
        cache = fetch_historical_cache(root)
    else:
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            cache = json.load(f)

    cohorts = [
        ('2022', '2023-04-01', '2024-04-01', '2023→2024 (12M)'),
        ('2023', '2024-04-01', '2025-04-01', '2024→2025 (12M)'),
        ('2024', '2025-04-01', '2026-04-01', '2025→2026 (12M)'),
        ('2025', '2026-04-01', '2026-11-22', '2026 YTD (8M)'),
    ]

    print('=' * 84)
    print('OUT-OF-SAMPLE EMPIRICAL BACKTEST OF PRODUCTION 5-MODEL ENGINE (ZERO LOOK-AHEAD)')
    print('=' * 84)
    print(f'{"Cohort":18s} | {"N":>3s} | {"MedV/P":>6s} | {"MedAPE":>7s} | {"±30%":>6s} | {"RankIC":>7s} | {"MedQ1":>7s} | {"MedQ5":>7s}')
    print('-' * 84)

    ics, apes, in30s, vps = [], [], [], []
    total_obs = 0
    for fy, fdate, edate, label in cohorts:
        f_ts = int(datetime.strptime(fdate, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())
        e_ts = int(datetime.strptime(edate, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())
        prev_fy = str(int(fy) - 1)
        pit = {}
        fwd_rets = {}
        for code, rec in cache.items():
            prices = rec.get('prices') or []
            p0_p, p1_p = price_at_date(prices, f_ts), price_at_date(prices, e_ts)
            if not p0_p or not p1_p or not p0_p[0] or not p1_p[0]:
                continue
            p0, adj0 = p0_p
            _, adj1 = p1_p
            ann = rec.get('annual') or {}
            ni = (ann.get('annualNetIncome') or {}).get(fy)
            eq = (ann.get('annualStockholdersEquity') or {}).get(fy)
            qs = rec.get('qs') or {}
            qs_sh = uf.raw(qs.get('defaultKeyStatistics'), 'sharesOutstanding')
            eps_rep = (ann.get('annualDilutedEPS') or {}).get(fy) or (ann.get('annualBasicEPS') or {}).get(fy)
            if ni is None or eq is None or eq <= 0 or not qs_sh:
                continue
            eff_sh = (ni / eps_rep) if (eps_rep and eps_rep != 0 and ni / eps_rep > 0) else qs_sh
            eps, bvps, roe = ni / eff_sh, eq / eff_sh, ni / eq
            eps_prev = (ann.get('annualDilutedEPS') or {}).get(prev_fy) or (ann.get('annualBasicEPS') or {}).get(prev_fy)
            rev, gp = (ann.get('annualTotalRevenue') or {}).get(fy), (ann.get('annualGrossProfit') or {}).get(fy)
            gm = (gp / rev) if (rev and gp and rev > 0) else 0.25
            ebitda = (ann.get('annualEBITDA') or {}).get(fy)
            debt = (ann.get('annualTotalDebt') or {}).get(fy) or 0.0
            cash = (ann.get('annualCashAndCashEquivalents') or {}).get(fy) or 0.0
            div_paid = (ann.get('annualCashDividendsPaid') or {}).get(fy)
            payout = abs(div_paid) / ni if (div_paid is not None and ni > 0) else 0.40
            ap, sd, fd = qs.get('assetProfile') or {}, qs.get('summaryDetail') or {}, qs.get('financialData') or {}
            sec, ind = ap.get('sector') or 'Unknown', ap.get('industry') or 'Unknown'
            cur, fin_cur = sd.get('currency'), fd.get('financialCurrency')
            is_fx_mismatch = bool(cur and fin_cur and cur != fin_cur)
            re, gl, beta_adj, region = uf.blume_coe(rec['market'], uf.raw(qs.get('defaultKeyStatistics'), 'beta'))

            g_est = 0.06
            if eps > 0 and eps_prev and eps_prev > 0:
                raw_g = (eps / eps_prev) - 1.0
                g_sust = uf.clamp(roe * (1.0 - uf.clamp(payout, 0.15, 0.75)), 0.0, 0.20)
                g_est = uf.clamp(0.35 * uf.clamp(raw_g, -0.25, 0.35) + 0.65 * g_sust, -0.08, 0.18)
            e1 = eps * (1.0 + g_est) if eps > 0 else eps
            e2 = e1 * (1.0 + g_est * 0.75) if e1 > 0 else e1

            pit[code] = {
                'code': code, 'name': rec['name'], 'market': rec['market'], 'region': region,
                'sector': sec, 'industry': ind, 'is_fin': (sec == 'Financial Services'),
                'is_fx_mismatch': is_fx_mismatch, 'is_cyclical': False,
                'price': p0, 'eff_sh': eff_sh, 'bvps': bvps,
                'e1': e1, 'e2': e2, 'e_mult': eps, 'roe_est': roe, 'g_est': g_est, 'gm': gm,
                'ebitda': ebitda, 'debt': debt, 'cash': cash, 'ev': p0 * eff_sh + debt - cash,
                'payout': payout, 're': re, 'gl': gl, 'beta_adj': beta_adj,
            }
            fwd_rets[code] = (adj1 / adj0) - 1.0

        valued = uf.run_cross_sectional_valuation(pit)
        rows = [(v['fairValue'] / pit[c]['price'], fwd_rets[c])
                for c, v in valued.items() if v.get('fairValue') and v['fairValue'] > 0]
        med_vp = statistics.median(x[0] for x in rows)
        med_ape = statistics.median(abs(x[0] - 1.0) for x in rows) * 100
        in30 = sum(1 for x in rows if abs(x[0] - 1.0) <= 0.30) / len(rows) * 100
        ic = spearman_corr([x[0] for x in rows], [x[1] for x in rows])
        sr = sorted(rows, key=lambda x: x[0], reverse=True)
        k = max(5, len(sr) // 5)
        q1_med = statistics.median(x[1] for x in sr[:k]) * 100
        q5_med = statistics.median(x[1] for x in sr[-k:]) * 100
        ics.append(ic); apes.append(med_ape); in30s.append(in30); vps.append(med_vp); total_obs += len(rows)
        print(f'{label:18s} | {len(rows):3d} | {med_vp:6.2f} | {med_ape:6.1f}% | {in30:5.1f}% | {ic:+7.3f} | {q1_med:+6.1f}% | {q5_med:+6.1f}%')

    print('-' * 84)
    print(f'{"AVERAGE (4 Cohorts)":18s} | {total_obs:3d} | {statistics.mean(vps):6.2f} | '
          f'{statistics.mean(apes):6.1f}% | {statistics.mean(in30s):5.1f}% | {statistics.mean(ics):+7.3f} |')


if __name__ == '__main__':
    main()
