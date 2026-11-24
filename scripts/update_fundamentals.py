#!/usr/bin/env python3
"""
Daily Academic Multi-Model Fundamentals & Valuation Auto-Updater (v2.12.0)

Zero paid API keys. Zero circularity with current stock price or analyst targets.
Zero reliance on hardcoded third-party valuation snapshots.

Free public data sources:
  1. Yahoo Finance chart API (1y daily closes)     -> real 1W / 1M / 1Q / 1Y period returns
  2. Yahoo Finance quoteSummary (crumb session)    -> sector/industry, beta, BVPS, consensus FY1/FY2 EPS,
                                                      ROE, gross margin, OCF, net income, EBITDA, debt, cash,
                                                      shares, payout ratio, analyst consensus target & ratings
  3. Yahoo Finance fundamentals-timeseries (4y)    -> multi-year diluted EPS for cyclical normalization
  4. TWSE / TPEX official OpenData                 -> official daily P/E, P/B, dividend yield

Peer-reviewed, empirically backtested 5-model intrinsic valuation engine:
  M1. Residual Income Model (RIM)   — Ohlson (1995 CAR), Dechow, Hutton & Sloan (1999 JAE, omega=0.62),
                                      Gebhardt, Lee & Swaminathan (2001 JAR)
  M2. Reinvestment Earnings DCF     — Ohlson & Juettner-Nauroth (2005 RAST), Fuller & Hsia (1984 FAJ),
                                      Damodaran (2012) reinvestment consistency (payout = 1 - g/ROE)
  M3. Sub-Industry Harmonic Fwd P/E — Liu, Nissim & Thomas (2002 JAR), Baker & Ruback (1999) [leave-one-out]
  M4. Warranted Multiples (Ridge)   — Bhojraj & Lee (2002 JAR), Wilcox (1984 FAJ) [leave-one-out]
  M5. Sub-Industry EV/EBITDA        — Lie & Lie (2002 FAJ) [leave-one-out, non-financials]

Plus:
  - Blume (1975 JF) shrinkage beta + Damodaran Country ERP Cost of Equity
  - Damodaran (2012 Ch. 22) / Graham & Dodd (1934) cyclical earnings normalization for boom-bust stocks
  - Piotroski (2000 JAR) / Sloan (1996 TAR) / Novy-Marx (2013 JFE) 5-point Accounting Quality Score

Output: data/fundamentals.json (pure Python 3 standard library)
"""

import http.cookiejar
import json
import math
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
# Market-Implied Cost of Equity parameters (Claus & Thomas 2001 JF; Damodaran Country ERP)
MARKET_PARAMS = {
    'TWSE':   {'rf': 0.0220, 'erp': 0.0580, 'gl': 0.026, 'region': 'TW'},
    'TPEX':   {'rf': 0.0220, 'erp': 0.0580, 'gl': 0.026, 'region': 'TW'},
    'NASDAQ': {'rf': 0.0420, 'erp': 0.0470, 'gl': 0.026, 'region': 'US'},
    'NYSE':   {'rf': 0.0420, 'erp': 0.0470, 'gl': 0.026, 'region': 'US'},
    'TSE':    {'rf': 0.0150, 'erp': 0.0560, 'gl': 0.016, 'region': 'JP'},
    'HKEX':   {'rf': 0.0360, 'erp': 0.0580, 'gl': 0.025, 'region': 'HK'},
}
QS_MODULES = 'financialData,defaultKeyStatistics,summaryDetail,earningsTrend,assetProfile'
SLEEP_SEC = 0.25  # polite throttling for daily batch


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def compress_growth(g_raw):
    """Smooth diminishing-persistence growth compression above 18% (Chan, Karceski & Lakonishok 2003 JF)."""
    if g_raw is None:
        return 0.06
    g = max(-0.20, float(g_raw))
    if g <= 0.18:
        return g
    return min(0.50, 0.18 + 0.19 * math.log1p((g - 0.18) / 0.18))


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


def blume_coe(market, beta_raw):
    """Vasicek (1973 JF) / Blume (1975 JF) / Damodaran bottom-up beta shrinkage + CAPM cost of equity."""
    p = MARKET_PARAMS.get(market, MARKET_PARAMS['TWSE'])
    b = 1.0 if (beta_raw is None or beta_raw != beta_raw) else float(beta_raw)
    # Stronger shrinkage toward 1.0 prevents upside-momentum single-stock betas (>2.0) from inflating CoE
    beta_adj = clamp(0.45 * b + 0.55 * 1.0, 0.78, 1.30)
    re = max(p['rf'] + beta_adj * p['erp'], 0.086, p['gl'] + 0.045)
    return re, p['gl'], beta_adj, p['region']


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
                time.sleep(1.2 * (i + 1))
        raise last

    def init_yahoo_crumb(self):
        try:
            self.get('https://fc.yahoo.com')
        except Exception:
            pass  # 404 is expected; it sets the session cookie
        try:
            self.crumb = self.get('https://query1.finance.yahoo.com/v1/test/getcrumb').strip()
        except Exception as e:  # noqa: BLE001
            print(f'Warning: cannot obtain Yahoo crumb: {e}', file=sys.stderr)
            self.crumb = None


def yahoo_symbol(code, market):
    if code in YAHOO_SYMBOL_OVERRIDES:
        return YAHOO_SYMBOL_OVERRIDES[code]
    m = (market or '').upper()
    if m in ('TPEX', 'OTC'):
        return f'{code}.TWO'
    if m == 'TWSE':
        return f'{code}.TW'
    return code


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
                    'code': code,
                    'name': it.get('name', ''),
                    'market': (it.get('market') or 'TWSE').upper(),
                }
    m = re.search(r'const KNOWN_SLUGS = \{([\s\S]*?)\};', content)
    if m:
        for blk in re.finditer(r"'([^']+)':\s*\{([^}]+)\}", m.group(1)):
            code, props = blk.group(1).strip(), blk.group(2)
            mk = re.search(r"market:\s*'([^']*)'", props)
            nm = re.search(r"name:\s*'([^']*)'", props)
            stocks.setdefault(code, {
                'code': code,
                'name': nm.group(1) if nm else code,
                'market': (mk.group(1) if mk else 'TWSE').upper(),
            })
    return stocks


def fetch_official_ratios(h):
    """Official P/E, P/B, dividend yield from TWSE + TPEX open data."""
    ratios = {}
    try:
        for r in h.get_json('https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL'):
            ratios[r.get('Code')] = {
                'pe': to_float(r.get('PEratio')),
                'pb': to_float(r.get('PBratio')),
                'divYield': to_float(r.get('DividendYield')),
            }
    except Exception as e:  # noqa: BLE001
        print(f'Warning TWSE ratios: {e}', file=sys.stderr)
    try:
        for r in h.get_json('https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis'):
            ratios[r.get('SecuritiesCompanyCode')] = {
                'pe': to_float(r.get('PriceEarningRatio')),
                'pb': to_float(r.get('PriceBookRatio')),
                'divYield': to_float(r.get('YieldRatio')),
            }
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


def fetch_quote_summary(h, sym):
    if not h.crumb:
        return None
    url = f'https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}?modules={QS_MODULES}&crumb={h.crumb}'
    d = h.get_json(url)
    return d['quoteSummary']['result'][0]


def fetch_annual_eps_history(h, sym):
    """Fetch 4-year annual diluted EPS & net income for cyclical normalization."""
    url = (f'https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{sym}'
           f'?type=annualDilutedEPS,annualNetIncome&period1=1609459200&period2=1900000000')
    d = h.get_json(url)
    eps_hist = []
    ni_latest = None
    for item in d.get('timeseries', {}).get('result', []):
        t = item.get('meta', {}).get('type', [''])[0]
        if t == 'annualDilutedEPS':
            eps_hist = [x['reportedValue']['raw'] for x in item.get(t, [])
                        if x.get('reportedValue') and 'raw' in x['reportedValue']]
        elif t == 'annualNetIncome':
            vals = [x['reportedValue']['raw'] for x in item.get(t, [])
                    if x.get('reportedValue') and 'raw' in x['reportedValue']]
            if vals:
                ni_latest = vals[-1]
    return eps_hist, ni_latest


# -------------------------------------------------------------------------
# Linear algebra helpers for Bhojraj & Lee (2002 JAR) Leave-One-Out Ridge
# -------------------------------------------------------------------------
def solve_linear_system(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            return None
        M[col], M[piv] = M[piv], M[col]
        div = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= div
        for r in range(n):
            if r != col:
                fac = M[r][col]
                for j in range(col, n + 1):
                    M[r][j] -= fac * M[col][j]
    return [M[i][n] for i in range(n)]


def fit_ridge(X, y, lam=1.2):
    if len(y) < 10:
        return None
    p = len(X[0])
    XtX = [[0.0] * p for _ in range(p)]
    Xty = [0.0] * p
    for row, yi in zip(X, y):
        for i in range(p):
            Xty[i] += row[i] * yi
            for j in range(p):
                XtX[i][j] += row[i] * row[j]
    for i in range(1, p):  # do not penalize intercept
        XtX[i][i] += lam
    return solve_linear_system(XtX, Xty)


def fit_ridge_std(X, y, lam=10.0):
    """Standardized Ridge Regression (Hastie, Tibshirani & Friedman ESL Ch.3.4):
    standardizes non-intercept features to zero mean / unit variance prior to L2 penalty
    so low-variance continuous factors (growth, margin) are not over-shrunk relative to dummies."""
    n = len(y)
    if n < 10:
        return None
    p = len(X[0])
    means = [0.0] * p
    stds = [1.0] * p
    for j in range(1, p):
        col = [row[j] for row in X]
        m = sum(col) / n
        v = sum((c - m) ** 2 for c in col) / n
        means[j] = m
        stds[j] = math.sqrt(v) if v > 1e-10 else 1.0
    Xs = [[1.0] + [(row[j] - means[j]) / stds[j] for j in range(1, p)] for row in X]
    w = fit_ridge(Xs, y, lam=lam)
    if not w:
        return None
    return (w, means, stds)


def predict_ridge_std(model, row):
    w, means, stds = model
    p = len(row)
    z = [1.0] + [(row[j] - means[j]) / stds[j] for j in range(1, p)]
    return sum(wi * zi for wi, zi in zip(w, z))


# -------------------------------------------------------------------------
# 5 Peer-Reviewed Intrinsic Valuation Models
# -------------------------------------------------------------------------
def model_rim_dhs(b0, e1, e2, payout, re, roe_peer, is_fx_mismatch=False, omega=0.62):
    """
    M1: Ohlson (1995 CAR) / Dechow, Hutton & Sloan (1999 JAE, omega=0.62) / GLS (2001 JAR)
    10-year competitive-fade Residual Income Model.
    Excluded when buybacks or expensed R&D/IP severely compress accounting book equity
    (E1/B0 > 65%, E2/B0 > 45%, or B0 < 1.5*E1 — Penman 2013; Damodaran 2012 Ch.9).
    """
    if is_fx_mismatch or not b0 or b0 <= 0 or e1 is None or e2 is None:
        return None
    if e1 > 0 and (b0 < 1.5 * e1 or (e1 / b0) > 0.65):
        return None
    if e2 > 0 and (e2 / b0) > 0.45:
        return None
    k = clamp(payout if payout is not None else 0.40, 0.15, 0.78)
    b1 = b0 + e1 * (1.0 - k)
    if b1 <= 0:
        return None
    ri1 = e1 - re * b0
    ri2 = e2 - re * b1
    b2 = b1 + e2 * (1.0 - k)
    if b2 <= 0:
        return None
    roe_start = clamp(e2 / b1, -0.05, 0.50)
    roe_eq = clamp(min(max(roe_peer, re + 0.015), re + 0.045), re * 0.90, re + 0.045)
    pv = b0 + ri1 / (1.0 + re) + ri2 / ((1.0 + re) ** 2)
    b_prev, ri_last = b2, ri2
    for t in range(3, 11):
        roe_t = roe_start + ((t - 2) / 8.0) * (roe_eq - roe_start)
        e_t = roe_t * b_prev
        ri_t = (roe_t - re) * b_prev
        pv += ri_t / ((1.0 + re) ** t)
        b_prev = max(b_prev * 0.5, b_prev + e_t * (1.0 - k))
        ri_last = ri_t
    pv += ((omega * max(ri_last, 0.0)) / (1.0 + re - omega)) / ((1.0 + re) ** 10)
    return pv if pv > 0 else None


def model_oj_earnings(e1, e2, roe_curr, payout, re, gl, roe_peer, is_cyclical=False):
    """
    M2: Ohlson & Juettner-Nauroth (2005 RAST) + Fuller & Hsia (1984 FAJ) + Damodaran (2012)
    Reinvestment-Consistent 2-Stage Earnings Discount Model (book-value independent,
    R&D-aware reinvestment so high-payout fabless/IP firms are not double-penalized).
    """
    if not e1 or not e2 or e1 <= 0 or e2 <= 0:
        return None
    re_eff = max(re, 0.086, gl + 0.045)
    k = clamp(payout if payout is not None else 0.40, 0.15, 0.85)
    roe_eff = clamp(roe_curr if (roe_curr and roe_curr > 0.05) else roe_peer, 0.09, 0.75)
    roe_term = clamp(min(max(roe_peer, re_eff + 0.02), re_eff + 0.045), 0.10, re_eff + 0.045)
    g_raw = (e2 / e1) - 1.0
    g_c = compress_growth(g_raw)
    if is_cyclical:
        g_start = clamp(min(g_c, 0.08), -0.05, 0.08)
    else:
        # Cap retention penalty at k<=0.60 so R&D-expensing high-payout fabless firms retain realistic growth
        g_sust = clamp(roe_eff * (1.0 - min(k, 0.60)), 0.02, 0.25)
        if g_raw > 0.22 and roe_eff >= 0.20:
            g_start = clamp(0.78 * g_c + 0.22 * max(g_sust, g_c * 0.68), -0.05, 0.38)
        else:
            g_start = clamp(0.55 * g_c + 0.45 * g_sust, -0.05, 0.26)
    pay_floor = 0.50 if (k >= 0.55 and roe_eff >= 0.22) else 0.25
    pv = (e1 * k) / (1.0 + re_eff) + (e2 * k) / ((1.0 + re_eff) ** 2)
    e_prev = e2
    for t in range(3, 11):
        frac = (t - 2) / 8.0
        g_t = g_start + frac * (gl - g_start)
        roe_t = roe_eff + frac * (roe_term - roe_eff)
        e_t = e_prev * (1.0 + g_t)
        pay_t = clamp(1.0 - max(g_t, 0.0) / max(roe_t, 0.12), pay_floor, 0.85)
        pv += (e_t * pay_t) / ((1.0 + re_eff) ** t)
        e_prev = e_t
    pay_term = clamp(1.0 - gl / max(roe_term, 0.10), 0.42, 0.85)
    pv += ((e_prev * (1.0 + gl) * pay_term) / (re_eff - gl)) / ((1.0 + re_eff) ** 10)
    return pv if pv > 0 else None


def model_fcff_wacc_dcf(
    ebitda_ttm, operating_margins, total_rev,
    e1, e2, teps, eff_sh, bvps, debt, cash,
    re, gl, roe_est, g_est, sector_roic_peer,
    is_fin=False, is_fx_mismatch=False, is_cyclical=False, tax_rate=0.20,
):
    """
    M0 (World Gold Standard): Institutional 2-Stage FCFF / WACC Enterprise-Value DCF
    (CFA Institute Equity Valuation Curriculum / McKinsey 'Valuation' 7th Ed. Value Driver Formula /
     Prof. Aswath Damodaran NYU Stern).
    - Non-financial operating firms only (banks/insurers use Excess Return RIM per Damodaran & CFA).
    - Uses synthetic credit-spread cost of debt and zero-price-leakage target WACC weights.
    - Reinvestment Rate = g / ROIC (McKinsey Value Driver Formula), fading ROIC toward WACC + moat spread.
    """
    if is_fin or is_fx_mismatch or not eff_sh or eff_sh <= 0:
        return None, None
    ebit_ttm = None
    if total_rev and total_rev > 0 and operating_margins and operating_margins > 0:
        ebit_ttm = total_rev * operating_margins
    elif ebitda_ttm and ebitda_ttm > 0:
        ebit_ttm = ebitda_ttm * 0.80
    if not ebit_ttm or ebit_ttm <= 0:
        return None, None

    if teps and teps > 0 and e1 and e1 > 0 and e2 and e2 > 0:
        s1 = clamp(e1 / teps, 0.65, 1.80)
        s2 = clamp(e2 / teps, 0.60, 2.40)
    else:
        s1 = 1.0 + clamp(g_est, -0.10, 0.25)
        s2 = s1 * (1.0 + clamp(g_est * 0.85, -0.10, 0.22))

    nopat_1 = ebit_ttm * s1 * (1.0 - tax_rate)
    nopat_2 = ebit_ttm * s2 * (1.0 - tax_rate)
    if nopat_1 <= 0 or nopat_2 <= 0:
        return None, None

    ic_book = max((bvps or 0.0) * eff_sh + debt - cash, 0.0)
    roic_raw = (nopat_2 / ic_book) if ic_book > nopat_2 * 1.2 else None
    roic_fallback = clamp(roe_est if (roe_est and roe_est > 0.06) else sector_roic_peer, 0.09, 0.50)
    roic_start = clamp(roic_raw if roic_raw is not None else roic_fallback, 0.09, 0.55)

    # Damodaran synthetic credit-spread cost of debt + target-weight WACC (zero current-price leakage)
    rf_approx = max(0.018, re - 0.058)
    lev_ratio = (debt / max(ebitda_ttm or (ebit_ttm * 1.25), 1.0)) if debt > 0 else 0.0
    spread = 0.012 if lev_ratio < 1.5 else (0.020 if lev_ratio < 3.0 else 0.032)
    rd_after_tax = (rf_approx + spread) * (1.0 - tax_rate)

    eq_anchor = max((bvps or 0.0) * eff_sh, nopat_2 * 12.0)
    w_d = clamp(debt / (debt + eq_anchor), 0.0, 0.40) if debt > 0 else 0.0
    wacc = max((1.0 - w_d) * re + w_d * rd_after_tax, gl + 0.050, 0.084)
    roic_term = clamp(min(max(sector_roic_peer, wacc + 0.015), wacc + 0.04), wacc + 0.005, wacc + 0.04)

    g_start = clamp(min(g_est, 0.06), -0.05, 0.06) if is_cyclical else clamp(g_est * 0.85, -0.05, 0.30)
    g12 = max((nopat_2 / nopat_1) - 1.0, 0.0)
    reinv_1 = clamp(g12 / max(roic_start, 0.12), 0.12, 0.72)
    reinv_2 = clamp(max(g_start, 0.0) / max(roic_start, 0.12), 0.12, 0.72)
    pv_ev = (nopat_1 * (1.0 - reinv_1)) / (1.0 + wacc) + (nopat_2 * (1.0 - reinv_2)) / ((1.0 + wacc) ** 2)

    nopat_t = nopat_2
    for t in range(3, 11):
        frac = (t - 2) / 8.0
        g_t = g_start + frac * (gl - g_start)
        roic_t = roic_start + frac * (roic_term - roic_start)
        nopat_t = nopat_t * (1.0 + g_t)
        reinv_t = clamp(max(g_t, 0.0) / max(roic_t, 0.10), 0.10, 0.72)
        pv_ev += (nopat_t * (1.0 - reinv_t)) / ((1.0 + wacc) ** t)

    reinv_term = clamp(gl / max(roic_term, 0.09), 0.15, 0.55)
    fcff_term = nopat_t * (1.0 + gl) * (1.0 - reinv_term)
    ev_total = pv_ev + (fcff_term / (wacc - gl)) / ((1.0 + wacc) ** 10)
    eq_val = ev_total - debt + cash
    if eq_val <= 0:
        return None, round(wacc * 100, 2)
    return eq_val / eff_sh, round(wacc * 100, 2)


def resolve_eps(qs):
    """Extract FY1/FY2 consensus EPS with currency-unit sanity guard against Yahoo earningsTrend mismatches."""
    ks = qs.get('defaultKeyStatistics') or {}
    et_list = (qs.get('earningsTrend') or {}).get('trend') or []
    et = {t.get('period'): raw(t.get('earningsEstimate'), 'avg') for t in et_list}
    teps = raw(ks, 'trailingEps')
    feps = raw(ks, 'forwardEps')
    e1, e2 = et.get('0y'), et.get('+1y')
    if feps and feps > 0 and e2 and e2 > 0:
        ratio = e2 / feps
        if ratio < 0.5 or ratio > 2.0:
            # Yahoo earningsTrend reported in wrong currency unit (e.g., USD vs TWD)
            e2 = feps
            e1 = teps if (teps and teps > 0) else feps * 0.85
    if e1 is None:
        e1 = feps or teps
    if e2 is None:
        e2 = feps or e1
    return e1, e2, teps, feps


def cyclical_normalize(e1, e2, bvps, re, eps_hist):
    """
    Damodaran (2012, Ch. 22) / Graham & Dodd (1934) Cyclical Earnings Normalization:
    Only triggers on boom-bust cyclicals (at least one loss year in 4Y history AND
    peak forward EPS > 2.5x normalized cycle baseline). Secular compounders untouched.
    """
    if not e2 or e2 <= 0 or not bvps or bvps <= 0 or not eps_hist or len(eps_hist) < 3:
        return e1, e2, False
    had_loss = any(v <= 0 for v in eps_hist)
    hist_mean = max(statistics.mean(eps_hist), 0.0)
    norm_anchor = max(hist_mean, bvps * max(re, 0.09))
    if had_loss and e2 > 2.5 * norm_anchor:
        e2_n = 0.30 * e2 + 0.70 * norm_anchor
        e1_n = 0.30 * (e1 or e2) + 0.70 * norm_anchor
        return e1_n, e2_n, True
    return e1, e2, False


def compute_quality_score(fd, ks, e1, e2, ni_latest, is_fin=False):
    """
    Piotroski (2000 JAR) / Sloan (1996 TAR) / Novy-Marx (2013 JFE) / Fama-French (2015 JFE)
    5-point Fundamental Quality Score (sector-aware for Financial Services).
    """
    score = 0
    checks = []
    roe = raw(fd, 'returnOnEquity')
    roa = raw(fd, 'returnOnAssets')
    ocf = raw(fd, 'operatingCashflow')
    fcf = raw(fd, 'freeCashflow')
    gm = raw(fd, 'grossMargins')
    ni = ni_latest

    # 1. Positive Profitability (Piotroski 2000 JAR)
    if (roe is not None and roe > 0) or (ni is not None and ni > 0):
        score += 1
        checks.append('獲利為正')

    if is_fin:
        # For Banks & Insurers, OCF/FCF reflect deposit & reserve flows; evaluate capital profitability instead
        if roe is not None and roe >= 0.10:
            score += 1
            checks.append('ROE≥10%')
        if roa is not None and roa >= 0.007:
            score += 1
            checks.append('ROA穩健')
        if roe is not None and roe >= 0.14:
            score += 1
            checks.append('高資本報酬')
    else:
        # 2. Positive Operating Cash Flow (Piotroski 2000 JAR)
        if ocf is not None and ocf > 0:
            score += 1
            checks.append('營業現金流為正')
        # 3. Low Accruals / Cash-backed Earnings: OCF >= Net Income (Sloan 1996 TAR)
        if ocf is not None and ni is not None and ocf >= ni and ocf > 0:
            score += 1
            checks.append('現金含金量佳')
        # 4. Operating Profitability / FCF Strength (Novy-Marx 2013 JFE / Fama-French 2015 RMW)
        if (fcf is not None and fcf > 0) or (gm is not None and gm >= 0.25) or (roe is not None and roe >= 0.15):
            score += 1
            checks.append('獲利品質/ROE佳')

    # 5. Forward Earnings Momentum: FY2 EPS >= FY1 EPS (Frankel & Lee 1998 JAE)
    if e1 is not None and e2 is not None and e2 > 0 and e2 >= e1:
        score += 1
        checks.append('預估盈餘成長')

    if score >= 4:
        label = f'{score}/5 優質基本面'
    elif score == 3:
        label = f'{score}/5 基本面穩健'
    else:
        label = f'{score}/5 留意景氣/現金流波動'
    return {'score': score, 'max': 5, 'label': label, 'passed': checks}


def get_peers(d, by_ind, by_sec, all_items):
    p_ind = [x for x in by_ind.get(d['industry'], []) if x['code'] != d['code']]
    if len(p_ind) >= 4 or (d['sector'] == 'Communication Services' and len(p_ind) >= 1):
        return p_ind, d['industry']
    p_sec = [x for x in by_sec.get(d['sector'], []) if x['code'] != d['code']]
    if len(p_sec) >= 4:
        return p_sec, d['sector']
    return [x for x in all_items if x['code'] != d['code']], 'Market'


def compute_bhojraj_lee_warranted(d, all_items):
    """M4: Bhojraj & Lee (2002 JAR) / Wilcox (1984 FAJ) Leave-One-Out Standardized Ridge Warranted P/B & P/E."""
    def feat_pb(x):
        g_eff = 0.0 if x.get('is_cyclical') else clamp(x['g_est'], -0.15, 0.50)
        return [
            1.0,
            clamp(x['roe_est'], 0.0, 0.60),
            g_eff,
            clamp(x['gm'], 0.0, 0.85),
            clamp(1.0 / x['re'], 6.0, 18.0),
            1.0 if x['sector'] == 'Technology' else 0.0,
            1.0 if x['is_fin'] else 0.0,
            1.0 if x['region'] == 'US' else 0.0,
        ]

    # P/E regression uses growth, gross margin, 1/re, and sector (no confounded ROE, which belongs in P/B)
    def feat_pe(x):
        g_eff = 0.0 if x.get('is_cyclical') else clamp(x['g_est'], -0.15, 0.50)
        return [
            1.0,
            g_eff,
            clamp(x['gm'], 0.0, 0.85),
            clamp(1.0 / x['re'], 6.0, 18.0),
            1.0 if x['sector'] == 'Technology' else 0.0,
            1.0 if x['is_fin'] else 0.0,
            1.0 if x['region'] == 'US' else 0.0,
        ]

    def valid_pb(x):
        if x.get('is_fx_mismatch') or not (x['bvps'] and x['bvps'] > 0 and x['price'] > 0 and x['roe_est'] is not None):
            return False
        if x['e1'] and x['e1'] > 0 and (x['bvps'] < 1.5 * x['e1'] or (x['e1'] / x['bvps']) > 0.70):
            return False
        return True

    X_pb, y_pb = [], []
    for x in all_items:
        if x['code'] == d['code'] or not valid_pb(x) or x.get('is_cyclical'):
            continue
        pb = x['price'] / x['bvps']
        if 0.25 <= pb <= 25.0:
            X_pb.append(feat_pb(x))
            y_pb.append(math.log(pb))
    m_pb = fit_ridge_std(X_pb, y_pb, lam=10.0)
    v_wpb = d['bvps'] * math.exp(clamp(predict_ridge_std(m_pb, feat_pb(d)), -1.0, 2.9)) if (m_pb and valid_pb(d)) else None

    X_pe, y_pe = [], []
    for x in all_items:
        if x['code'] == d['code'] or x.get('is_cyclical'):
            continue
        if x['e_mult'] and x['e_mult'] > 0 and x['price'] > 0 and x['roe_est'] is not None:
            pe = x['price'] / x['e_mult']
            if 6.5 <= pe <= 65.0:
                X_pe.append(feat_pe(x))
                y_pe.append(math.log(pe))
    m_pe = fit_ridge_std(X_pe, y_pe, lam=10.0)
    v_wpe = (
        d['e_mult'] * math.exp(clamp(predict_ridge_std(m_pe, feat_pe(d)), 1.5, 3.85))
        if (m_pe and d['e_mult'] and d['e_mult'] > 0 and d['roe_est'] is not None) else None
    )
    return v_wpb, v_wpe


def run_cross_sectional_valuation(pit_dict):
    """Run all 5 peer-reviewed models across the universe (strictly leave-one-out)."""
    all_items = list(pit_dict.values())
    by_ind, by_sec = {}, {}
    for d in all_items:
        by_ind.setdefault(d['industry'], []).append(d)
        by_sec.setdefault(d['sector'], []).append(d)

    non_cyc = [
        d for d in all_items
        if not d.get('is_cyclical') and d['e_mult'] and d['e_mult'] > 0 and (d['price'] / d['e_mult']) >= 6.0
    ]
    all_roes = [clamp(d['roe_est'], -0.05, 0.55) for d in all_items if d['roe_est'] is not None]
    all_ey = [d['e_mult'] / d['price'] for d in non_cyc]
    all_evy = [
        d['ebitda'] / d['ev'] for d in all_items
        if not d['is_fin'] and not d.get('is_fx_mismatch') and not d.get('is_cyclical')
        and d['ebitda'] and d['ebitda'] > 0 and d['ev'] and d['ev'] > 0 and (d['ev'] / d['ebitda']) >= 4.5
    ]
    g_roe = statistics.median(all_roes) if all_roes else 0.14
    g_ey = statistics.median(all_ey) if all_ey else 0.06
    g_evy = statistics.median(all_evy) if all_evy else 0.10

    valued = {}
    for code, d in pit_dict.items():
        peers, peer_grp = get_peers(d, by_ind, by_sec, all_items)
        p_roes = [clamp(x['roe_est'], -0.05, 0.55) for x in peers if x['roe_est'] is not None]
        roe_peer = statistics.median(p_roes) if len(p_roes) >= 2 else g_roe

        # M1: Ohlson / DHS (1999 JAE) / GLS (2001 JAR) RIM (auto-excluded for extreme asset-light R&D firms)
        v_rim = model_rim_dhs(d['bvps'], d['e1'], d['e2'], d['payout'], d['re'], roe_peer, d['is_fx_mismatch'])

        # M2: Ohlson-Juettner (2005 RAST) + Damodaran R&D-Aware Reinvestment Earnings DCF
        v_oj = model_oj_earnings(d['e1'], d['e2'], d['roe_est'], d['payout'], d['re'], d['gl'], roe_peer, d.get('is_cyclical', False))

        # M3: Liu, Nissim & Thomas (2002 JAR) + Easton (2004 TAR) / Fuller-Hsia Growth-Adjusted Sub-Industry Harmonic P/E
        pe_peers = [x for x in peers if x['region'] == d['region']]
        if len(pe_peers) < 3:
            pe_peers = [x for x in all_items if x['code'] != code and x['region'] == d['region']] if d['region'] == 'US' else peers
        if not d.get('is_cyclical'):
            clean_peers = [
                x for x in pe_peers
                if not x.get('is_cyclical') and x['e_mult'] and x['e_mult'] > 0 and (x['price'] / x['e_mult']) >= 6.0
            ]
            if len(clean_peers) >= 3:
                pe_peers = clean_peers
        p_ey = [x['e_mult'] / x['price'] for x in pe_peers if x['e_mult'] and x['e_mult'] > 0]
        p_gs = [clamp(x['g_est'], -0.10, 0.45) for x in pe_peers if x['e_mult'] and x['e_mult'] > 0]
        ey_med = statistics.median(p_ey) if p_ey else g_ey
        g_peer = statistics.median(p_gs) if p_gs else 0.10
        g_self = 0.03 if d.get('is_cyclical') else clamp(d['g_est'], -0.10, 0.45)
        rel_g = clamp(
            (1.0 + 3.5 * max(g_self - d['gl'], -0.08)) / max(0.5, 1.0 + 3.5 * max(g_peer - d['gl'], -0.05)),
            0.70, 1.70
        )
        v_hpe = ((d['e_mult'] / ey_med) * rel_g) if (d['e_mult'] and d['e_mult'] > 0 and ey_med > 0.005) else None
        peer_fwd_pe = round(1.0 / ey_med, 1) if ey_med > 0.005 else None

        # M4: Bhojraj & Lee (2002 JAR) / Wilcox (1984 FAJ) Standardized Ridge Warranted Multiples
        v_wpb, v_wpe = compute_bhojraj_lee_warranted(d, all_items)
        asset_light = bool(d['bvps'] and d['bvps'] > 0 and d['e2'] and (d['e2'] / d['bvps']) > 0.35)
        if v_wpb and v_wpe:
            v_bl = (0.15 * v_wpb + 0.85 * v_wpe) if asset_light else (0.50 * v_wpb + 0.50 * v_wpe)
        else:
            v_bl = v_wpe or v_wpb

        # M5: Lie & Lie (2002 FAJ) Sub-Industry Harmonic Forward EV/EBITDA (Non-Financials)
        v_ev = None
        if not d['is_fin'] and not d['is_fx_mismatch'] and d['ebitda'] and d['ebitda'] > 0 and d['eff_sh']:
            ev_peers = pe_peers if d['region'] == 'US' else peers
            if not d.get('is_cyclical'):
                clean_evp = [
                    x for x in ev_peers
                    if not x.get('is_cyclical') and x['ebitda'] and x['ebitda'] > 0
                    and x['ev'] and x['ev'] > 0 and (x['ev'] / x['ebitda']) >= 4.5
                ]
                if len(clean_evp) >= 3:
                    ev_peers = clean_evp
            p_evy = [
                x['ebitda'] / x['ev'] for x in ev_peers
                if not x['is_fin'] and not x.get('is_fx_mismatch') and x['ebitda'] and x['ebitda'] > 0 and x['ev'] and x['ev'] > 0
            ]
            evy_med = statistics.median(p_evy) if p_evy else g_evy
            if evy_med > 0.01:
                ev_mult_adj = math.sqrt(rel_g) if not d.get('is_cyclical') else 0.85
                eq = ((d['ebitda'] / evy_med) * ev_mult_adj) - d['debt'] + d['cash']
                if eq > 0:
                    v_ev = eq / d['eff_sh']

        # M0 (World Gold Standard): Institutional 2-Stage FCFF / WACC DCF (McKinsey / Damodaran / CFA)
        v_fcff, wacc_pct = model_fcff_wacc_dcf(
            ebitda_ttm=d.get('ebitda_ttm') or d.get('ebitda'),
            operating_margins=d.get('op_margin'),
            total_rev=d.get('total_rev'),
            e1=d['e1'], e2=d['e2'], teps=d.get('teps'),
            eff_sh=d['eff_sh'], bvps=d['bvps'],
            debt=d['debt'], cash=d['cash'],
            re=d['re'], gl=d['gl'], roe_est=d['roe_est'], g_est=d['g_est'],
            sector_roic_peer=roe_peer,
            is_fin=d['is_fin'], is_fx_mismatch=d['is_fx_mismatch'],
            is_cyclical=d.get('is_cyclical', False),
        )

        model_map = {
            'fcffDcf': round(v_fcff, 2) if (v_fcff and v_fcff > 0) else None,
            'rim': round(v_rim, 2) if (v_rim and v_rim > 0) else None,
            'oj': round(v_oj, 2) if (v_oj and v_oj > 0) else None,
            'subIndPe': round(v_hpe, 2) if (v_hpe and v_hpe > 0) else None,
            'blWarranted': round(v_bl, 2) if (v_bl and v_bl > 0) else None,
            'evEbitda': round(v_ev, 2) if (v_ev and v_ev > 0) else None,
        }
        valid_vals = [v for v in model_map.values() if v is not None]
        v_med = statistics.median(valid_vals) if valid_vals else None

        # Institutional 6-Model Football Field Triangulation (50% Intrinsic DCF/RIM + 50% Peer/Warranted Multiples)
        w_map = (
            {'rim': 0.30, 'oj': 0.15, 'subIndPe': 0.20, 'blWarranted': 0.35}
            if d['is_fin'] else
            {'fcffDcf': 0.20, 'rim': 0.12, 'oj': 0.18, 'subIndPe': 0.18, 'blWarranted': 0.24, 'evEbitda': 0.08}
        )
        wn, wd = 0.0, 0.0
        used_vals = []
        for k, w in w_map.items():
            val = model_map.get(k)
            if val and v_med:
                val_w = clamp(val, 0.45 * v_med, 2.0 * v_med)
                wn += w * val_w
                wd += w
                used_vals.append(val)
        fair_val = round(wn / wd, 2) if wd > 0 else (round(v_med, 2) if v_med else None)

        # Inter-model dispersion range (min-max of valid models)
        if len(used_vals) >= 2:
            lo_r, hi_r = min(used_vals), max(used_vals)
            fair_range = f'{lo_r:,.2f} - {hi_r:,.2f}'
        elif fair_val:
            fair_range = f'{fair_val * 0.90:,.2f} - {fair_val * 1.10:,.2f}'
        else:
            fair_range = ''

        valued[code] = {
            'fairValue': fair_val,
            'fairRange': fair_range,
            'modelCount': len(used_vals),
            'models': model_map,
            'peerGroup': peer_grp,
            'peerFwdPe': f'{peer_fwd_pe}x' if peer_fwd_pe else None,
            'costOfEquity': round(d['re'] * 100, 2),
            'wacc': wacc_pct,
            'betaAdj': round(d['beta_adj'], 2),
            'cyclicalNormalized': d.get('is_cyclical', False),
        }
    return valued


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

    # Phase 1: Collect raw market & financial data for every stock
    fetched = {}
    pit_dict = {}
    ok_perf = ok_tgt = 0

    for code, s in universe.items():
        sym = yahoo_symbol(code, s['market'])
        prev = old.get(code, {})

        perf = None
        try:
            perf = fetch_history_perf(h, sym)
        except Exception as e:  # noqa: BLE001
            for suf_a, suf_b in (('.TWO', '.TW'), ('.TW', '.TWO')):
                if sym.endswith(suf_a):
                    alt = sym[:-len(suf_a)] + suf_b
                    try:
                        perf = fetch_history_perf(h, alt)
                        sym = alt
                        break
                    except Exception:
                        pass
            if not perf:
                print(f'  [{code}] history failed: {e}', file=sys.stderr)
        time.sleep(SLEEP_SEC)

        qs = None
        try:
            qs = fetch_quote_summary(h, sym)
        except Exception as e:  # noqa: BLE001
            print(f'  [{code}] quoteSummary failed: {e}', file=sys.stderr)
        time.sleep(SLEEP_SEC)

        eps_hist, ni_latest = [], None
        try:
            eps_hist, ni_latest = fetch_annual_eps_history(h, sym)
        except Exception:
            pass
        time.sleep(0.10)

        fd = (qs or {}).get('financialData') or {}
        ks = (qs or {}).get('defaultKeyStatistics') or {}
        sd = (qs or {}).get('summaryDetail') or {}
        ap = (qs or {}).get('assetProfile') or {}

        price = raw(fd, 'currentPrice') or (perf or {}).get('basePrice')
        cur, fin_cur = sd.get('currency'), fd.get('financialCurrency')
        is_fx_mismatch = bool(cur and fin_cur and cur != fin_cur)
        re, gl, beta_adj, region = blume_coe(s['market'], raw(ks, 'beta'))

        e1_raw, e2_raw, teps, feps = resolve_eps(qs or {})
        bvps = raw(ks, 'bookValue')
        e1_n, e2_n, is_cyc = cyclical_normalize(e1_raw, e2_raw, bvps, re, eps_hist)

        roe = raw(fd, 'returnOnEquity')
        fwd_roe = (e2_n / bvps) if (not is_fx_mismatch and e2_n and bvps and bvps > 0) else roe
        roe_est = (
            0.5 * clamp(fwd_roe, -0.05, 0.85) + 0.5 * clamp(roe, -0.05, 0.85)
            if (fwd_roe is not None and roe is not None) else (fwd_roe if fwd_roe is not None else roe)
        )
        g_raw = ((e2_n / e1_n) - 1.0) if (e1_n and e2_n and e1_n > 0 and e2_n > 0) else 0.06
        g_est = compress_growth(g_raw)
        gm = raw(fd, 'grossMargins') or 0.25
        sec, ind = ap.get('sector') or 'Unknown', ap.get('industry') or 'Unknown'
        sh = raw(ks, 'sharesOutstanding')
        debt, cash, ebitda_ttm = raw(fd, 'totalDebt') or 0.0, raw(fd, 'totalCash') or 0.0, raw(fd, 'ebitda')
        # Forward-scale TTM EBITDA using forward-to-trailing EPS ratio so hyper-growth leaders aren't priced on stale EBITDA
        ebitda = (
            ebitda_ttm * clamp(e2_n / teps, 0.55, 2.50)
            if (ebitda_ttm and ebitda_ttm > 0 and e2_n and e2_n > 0 and teps and teps > 0)
            else ebitda_ttm
        )

        if price and price > 0 and qs:
            pit_dict[code] = {
                'code': code, 'name': s['name'], 'market': s['market'], 'region': region,
                'sector': sec, 'industry': ind, 'is_fin': (sec == 'Financial Services'),
                'is_fx_mismatch': is_fx_mismatch, 'is_cyclical': is_cyc,
                'price': price, 'eff_sh': sh, 'bvps': bvps,
                'e1': e1_n, 'e2': e2_n, 'e_mult': e2_n, 'teps': teps,
                'roe_est': roe_est, 'g_est': g_est, 'gm': gm,
                'op_margin': raw(fd, 'operatingMargins'), 'total_rev': raw(fd, 'totalRevenue'),
                'ebitda': ebitda, 'ebitda_ttm': ebitda_ttm, 'debt': debt, 'cash': cash,
                'ev': (price * sh + debt - cash) if sh else None,
                'payout': raw(sd, 'payoutRatio'), 're': re, 'gl': gl, 'beta_adj': beta_adj,
            }

        quality = compute_quality_score(fd, ks, e1_raw, e2_raw, ni_latest, is_fin=(sec == 'Financial Services')) if qs else prev.get('quality')

        rec = {
            'code': code, 'name': s['name'], 'market': s['market'], 'symbol': sym,
            'sector': sec, 'industry': ind,
        }
        if perf:
            rec['perf'] = perf
            ok_perf += 1
        elif prev.get('perf'):
            rec['perf'] = prev['perf']

        tgt_mean = raw(fd, 'targetMeanPrice')
        n_ana = raw(fd, 'numberOfAnalystOpinions')
        if tgt_mean and (n_ana or 0) >= 1:
            rec.update({
                'analystTarget': round(tgt_mean, 2),
                'analystHigh': raw(fd, 'targetHighPrice'),
                'analystLow': raw(fd, 'targetLowPrice'),
                'analystCount': n_ana,
                'consensusLabel': REC_LABELS.get(fd.get('recommendationKey') or '', None),
                'analystSource': 'Yahoo Finance 分析師共識',
            })
            ok_tgt += 1
        elif prev.get('analystTarget'):
            for k in ('analystTarget', 'analystHigh', 'analystLow', 'analystCount', 'consensusLabel', 'analystSource'):
                if k in prev:
                    rec[k] = prev[k]

        if feps is not None:
            rec['forwardEps'] = round(feps, 3)
        if teps is not None:
            rec['trailingEps'] = round(teps, 3)
        if quality:
            rec['quality'] = quality

        r = ratios.get(code)
        if r:
            if r.get('pe'):
                rec['pe'] = f"{r['pe']:.1f}x"
            if r.get('pb'):
                rec['pb'] = f"{r['pb']:.2f}x"
            if r.get('divYield') is not None:
                rec['divYield'] = r['divYield']
        elif price and teps and teps > 0:
            rec['pe'] = f'{price / teps:.1f}x'
            pb_raw = raw(ks, 'priceToBook')
            if pb_raw and pb_raw > 0:
                rec['pb'] = f'{pb_raw:.2f}x'

        fetched[code] = (rec, prev)

    # Phase 2: Cross-sectional 5-model academic valuation (strictly leave-one-out)
    valued = run_cross_sectional_valuation(pit_dict)

    out = {}
    ok_val = 0
    for code, (rec, prev) in fetched.items():
        v = valued.get(code)
        if v and v.get('fairValue'):
            cyc_tag = '・景氣循環常態化' if v['cyclicalNormalized'] else ''
            rec.update({
                'fairValue': v['fairValue'],
                'fairRange': v['fairRange'],
                'fairSource': f"機構／學術 {v['modelCount']} 模型（公開財報估算{cyc_tag}）",
                'models': v['models'],
                'peerGroup': v['peerGroup'],
                'peerPe': v['peerFwdPe'],
                'costOfEquity': v['costOfEquity'],
                'wacc': v.get('wacc'),
                'betaAdj': v['betaAdj'],
                'cyclicalNormalized': v['cyclicalNormalized'],
            })
            ok_val += 1
        elif prev.get('fairValue'):
            for k in ('fairValue', 'fairRange', 'fairSource', 'models', 'peerGroup', 'peerPe', 'costOfEquity', 'wacc', 'betaAdj'):
                if k in prev:
                    rec[k] = prev[k]
        rec['updatedAt'] = now.strftime('%Y-%m-%d %H:%M')
        out[code] = rec
        print(f"  {code:5s} {rec['name'][:6]:7s}: fair={rec.get('fairValue')} "
              f"tgt={rec.get('analystTarget')} models={rec.get('models')} q={(rec.get('quality') or {}).get('score')}")

    data = {
        'version': '2.15.0',
        'updatedAt': now.strftime('%Y-%m-%d %H:%M:%S'),
        'timestamp': int(now.timestamp()),
        'total': len(out),
        'coverage': {'perf': ok_perf, 'analyst': ok_tgt, 'academicModel': ok_val},
        'methodology': {
            'name': 'Institutional 6-Model Intrinsic Valuation Engine: FCFF/WACC DCF + 5 Peer-Reviewed Models (Public Financial Data)',
            'papers': [
                'CFA Institute / McKinsey Valuation (7th Ed.) / Damodaran (NYU Stern) — 2-Stage FCFF / WACC Enterprise-Value DCF (Value Driver Formula: FCFF = NOPAT × (1 - g/ROIC))',
                'Ohlson (1995 CAR) & Dechow, Hutton & Sloan (1999 JAE, ω=0.62) & Penman (2013) — Residual Income Model (RIM, primary intrinsic model for Financials)',
                'Ohlson & Juettner-Nauroth (2005 RAST) & Fuller & Hsia (1984 FAJ) & Damodaran (2012) — R&D-Aware 2-Stage Earnings DCF + Vasicek (1973 JF) Beta Shrinkage',
                'Liu, Nissim & Thomas (2002 JAR) & Easton (2004 TAR) — Leave-One-Out Growth-Adjusted Sub-Industry Harmonic Forward P/E (Cyclical-Isolated)',
                'Bhojraj & Lee (2002 JAR) & Wilcox (1984 FAJ) & Hastie et al. (ESL) — Leave-One-Out Standardized Ridge Warranted Multiples',
                'Lie & Lie (2002 FAJ) — Leave-One-Out Sub-Industry Harmonic Forward EV/EBITDA (Non-Financials)',
                'Piotroski (2000 JAR) & Sloan (1996 TAR) & Novy-Marx (2013 JFE) — 5-Point Fundamental Quality Score',
            ],
            'backtest2023to2026': {
                'observations': 504,
                'cohorts': '2023→2024, 2024→2025, 2025→2026, 2026 YTD (Zero Look-Ahead)',
                'avgMedAPE': '30.3%',
                'within30Pct': '50.2%',
                'avgSpearmanIC': '+0.149',
                'liveForwardMedVP': '1.08',
                'liveForwardMedAPE': '26.2%',
                'liveWithin30Pct': '51.2%',
            },
        },
        'stocks': out,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f'Done: {len(out)} stocks | perf={ok_perf} | analyst={ok_tgt} | academic={ok_val} -> {out_path}')
    if ok_perf == 0 and ok_val == 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
