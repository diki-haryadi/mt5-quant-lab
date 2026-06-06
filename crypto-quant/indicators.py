"""
indicators.py — pustaka indikator teknikal lengkap (pure-python, tanpa numpy/pandas).
Input: list bar dict {time,open,high,low,close,volume} ATAU list harga (float).
Konvensi: fungsi return list sepanjang input (None utk warm-up). compute_all(bars) -> ringkasan terbaru.

Kategori:
  TREND     : sma ema wma hma dema tema vwma  | macd adx(+di) aroon supertrend psar ichimoku
  MOMENTUM  : rsi stoch stochrsi cci willr roc mom mfi tsi cmo uo
  VOLATILITY: stddev bollinger atr natr keltner donchian
  VOLUME    : obv vwap cmf ad cmf force_index eom pvt
"""
from __future__ import annotations
import math
import datetime as _dt

NaN = float("nan")


def _isnum(x): return x is not None and x == x


# ---------- moving averages ----------
def sma(v, p):
    n = len(v); o = [None] * n; s = 0.0
    for i in range(n):
        s += v[i]
        if i >= p: s -= v[i - p]
        if i >= p - 1: o[i] = s / p
    return o


def ema(v, p):
    n = len(v); o = [None] * n
    if n < p: return o
    k = 2 / (p + 1); s = sum(v[:p]) / p; o[p - 1] = s
    for i in range(p, n): s = v[i] * k + s * (1 - k); o[i] = s
    return o


def wma(v, p):
    n = len(v); o = [None] * n; denom = p * (p + 1) / 2
    for i in range(p - 1, n):
        o[i] = sum(v[i - p + 1 + j] * (j + 1) for j in range(p)) / denom
    return o


def hma(v, p):
    half = wma(v, max(1, p // 2)); full = wma(v, p)
    raw = [(2 * half[i] - full[i]) if (_isnum(half[i]) and _isnum(full[i])) else None for i in range(len(v))]
    clean = [x if _isnum(x) else 0.0 for x in raw]
    h = wma(clean, max(1, int(math.sqrt(p))))
    return [h[i] if _isnum(raw[i]) else None for i in range(len(v))]


def dema(v, p):
    e1 = ema(v, p); e1c = [x if _isnum(x) else 0.0 for x in e1]; e2 = ema(e1c, p)
    return [(2 * e1[i] - e2[i]) if (_isnum(e1[i]) and _isnum(e2[i])) else None for i in range(len(v))]


def tema(v, p):
    e1 = ema(v, p); e1c = [x if _isnum(x) else 0.0 for x in e1]; e2 = ema(e1c, p)
    e2c = [x if _isnum(x) else 0.0 for x in e2]; e3 = ema(e2c, p)
    return [(3 * e1[i] - 3 * e2[i] + e3[i]) if all(_isnum(x[i]) for x in (e1, e2, e3)) else None for i in range(len(v))]


def vwma(bars, p):
    n = len(bars); o = [None] * n
    for i in range(p - 1, n):
        pv = sum(bars[j]["close"] * bars[j]["volume"] for j in range(i - p + 1, i + 1))
        vv = sum(bars[j]["volume"] for j in range(i - p + 1, i + 1))
        o[i] = pv / vv if vv else None
    return o


# ---------- helpers ----------
def _rma(v, p):
    n = len(v); o = [None] * n
    seed = [x for x in v[:p] if _isnum(x)]
    if len(seed) < p: return o
    s = sum(v[:p]) / p; o[p - 1] = s
    for i in range(p, n): s = (s * (p - 1) + v[i]) / p; o[i] = s
    return o


def _tr(bars):
    n = len(bars); tr = [None] * n
    for i in range(n):
        h, l = bars[i]["high"], bars[i]["low"]
        tr[i] = (h - l) if i == 0 else max(h - l, abs(h - bars[i - 1]["close"]), abs(l - bars[i - 1]["close"]))
    return tr


# ---------- volatility ----------
def stddev(v, p):
    n = len(v); o = [None] * n
    for i in range(p - 1, n):
        w = v[i - p + 1:i + 1]; m = sum(w) / p
        o[i] = math.sqrt(sum((x - m) ** 2 for x in w) / p)
    return o


def bollinger(close, p=20, mult=2.0):
    mid = sma(close, p); sd = stddev(close, p)
    up = [(mid[i] + mult * sd[i]) if (_isnum(mid[i]) and _isnum(sd[i])) else None for i in range(len(close))]
    lo = [(mid[i] - mult * sd[i]) if (_isnum(mid[i]) and _isnum(sd[i])) else None for i in range(len(close))]
    bw = [((up[i] - lo[i]) / mid[i] * 100) if (_isnum(up[i]) and mid[i]) else None for i in range(len(close))]
    return dict(mid=mid, upper=up, lower=lo, bandwidth=bw)


def atr(bars, p=14): return _rma(_tr(bars), p)


def natr(bars, p=14):
    a = atr(bars, p); return [(a[i] / bars[i]["close"] * 100) if (_isnum(a[i]) and bars[i]["close"]) else None for i in range(len(bars))]


def keltner(bars, p=20, mult=2.0):
    close = [b["close"] for b in bars]; mid = ema(close, p); a = atr(bars, p)
    up = [(mid[i] + mult * a[i]) if (_isnum(mid[i]) and _isnum(a[i])) else None for i in range(len(bars))]
    lo = [(mid[i] - mult * a[i]) if (_isnum(mid[i]) and _isnum(a[i])) else None for i in range(len(bars))]
    return dict(mid=mid, upper=up, lower=lo)


def donchian(bars, p=20):
    n = len(bars); up = [None] * n; lo = [None] * n; mid = [None] * n
    for i in range(p - 1, n):
        hh = max(bars[j]["high"] for j in range(i - p + 1, i + 1))
        ll = min(bars[j]["low"] for j in range(i - p + 1, i + 1))
        up[i], lo[i], mid[i] = hh, ll, (hh + ll) / 2
    return dict(upper=up, lower=lo, mid=mid)


# ---------- momentum ----------
def rsi(close, p=14):
    n = len(close); o = [None] * n
    if n < p + 1: return o
    gains = [0.0] * n; losses = [0.0] * n
    for i in range(1, n):
        d = close[i] - close[i - 1]; gains[i] = max(d, 0); losses[i] = max(-d, 0)
    ag = sum(gains[1:p + 1]) / p; al = sum(losses[1:p + 1]) / p
    o[p] = 100 - 100 / (1 + (ag / al if al else 999))
    for i in range(p + 1, n):
        ag = (ag * (p - 1) + gains[i]) / p; al = (al * (p - 1) + losses[i]) / p
        o[i] = 100 - 100 / (1 + (ag / al if al else 999))
    return o


def stoch(bars, k=14, d=3):
    n = len(bars); kk = [None] * n
    for i in range(k - 1, n):
        hh = max(bars[j]["high"] for j in range(i - k + 1, i + 1))
        ll = min(bars[j]["low"] for j in range(i - k + 1, i + 1))
        kk[i] = (bars[i]["close"] - ll) / (hh - ll) * 100 if hh > ll else 50.0
    kc = [x if _isnum(x) else 0.0 for x in kk]; dd = sma(kc, d)
    return dict(k=kk, d=[dd[i] if _isnum(kk[i]) else None for i in range(n)])


def stochrsi(close, p=14, k=3, d=3):
    r = rsi(close, p); n = len(close); o = [None] * n
    for i in range(n):
        if not _isnum(r[i]): continue
        w = [r[j] for j in range(max(0, i - p + 1), i + 1) if _isnum(r[j])]
        if len(w) < p: continue
        lo, hi = min(w), max(w); o[i] = (r[i] - lo) / (hi - lo) * 100 if hi > lo else 0.0
    oc = [x if _isnum(x) else 0.0 for x in o]; ks = sma(oc, k); kc = [x if _isnum(x) else 0.0 for x in ks]; ds = sma(kc, d)
    return dict(stochrsi=o, k=[ks[i] if _isnum(o[i]) else None for i in range(n)],
                d=[ds[i] if _isnum(o[i]) else None for i in range(n)])


def cci(bars, p=20):
    n = len(bars); o = [None] * n
    tp = [(b["high"] + b["low"] + b["close"]) / 3 for b in bars]
    for i in range(p - 1, n):
        w = tp[i - p + 1:i + 1]; m = sum(w) / p; md = sum(abs(x - m) for x in w) / p
        o[i] = (tp[i] - m) / (0.015 * md) if md else 0.0
    return o


def willr(bars, p=14):
    n = len(bars); o = [None] * n
    for i in range(p - 1, n):
        hh = max(bars[j]["high"] for j in range(i - p + 1, i + 1))
        ll = min(bars[j]["low"] for j in range(i - p + 1, i + 1))
        o[i] = (hh - bars[i]["close"]) / (hh - ll) * -100 if hh > ll else -50.0
    return o


def roc(close, p=12):
    n = len(close); return [((close[i] / close[i - p] - 1) * 100) if i >= p and close[i - p] else None for i in range(n)]


def mom(close, p=10):
    n = len(close); return [(close[i] - close[i - p]) if i >= p else None for i in range(n)]


def cmo(close, p=14):
    n = len(close); o = [None] * n
    for i in range(p, n):
        up = dn = 0.0
        for j in range(i - p + 1, i + 1):
            d = close[j] - close[j - 1]; up += max(d, 0); dn += max(-d, 0)
        o[i] = (up - dn) / (up + dn) * 100 if (up + dn) else 0.0
    return o


def mfi(bars, p=14):
    n = len(bars); o = [None] * n
    tp = [(b["high"] + b["low"] + b["close"]) / 3 for b in bars]
    rf = [tp[i] * bars[i]["volume"] for i in range(n)]
    for i in range(p, n):
        pos = neg = 0.0
        for j in range(i - p + 1, i + 1):
            if tp[j] > tp[j - 1]: pos += rf[j]
            elif tp[j] < tp[j - 1]: neg += rf[j]
        o[i] = 100 - 100 / (1 + pos / neg) if neg else 100.0
    return o


def tsi(close, long=25, short=13):
    n = len(close); m = [0.0] + [close[i] - close[i - 1] for i in range(1, n)]
    am = [abs(x) for x in m]
    e1 = ema(m, long); e1c = [x if _isnum(x) else 0.0 for x in e1]; e2 = ema(e1c, short)
    a1 = ema(am, long); a1c = [x if _isnum(x) else 0.0 for x in a1]; a2 = ema(a1c, short)
    return [(100 * e2[i] / a2[i]) if (_isnum(e2[i]) and a2[i]) else None for i in range(n)]


def uo(bars, s=7, m=14, l=28):
    n = len(bars); o = [None] * n
    bp = [None] * n; tr = [None] * n
    for i in range(1, n):
        pc = bars[i - 1]["close"]; bp[i] = bars[i]["close"] - min(bars[i]["low"], pc)
        tr[i] = max(bars[i]["high"], pc) - min(bars[i]["low"], pc)
    for i in range(l, n):
        def avg(w):
            sbp = sum(bp[i - w + 1:i + 1]); st = sum(tr[i - w + 1:i + 1]); return sbp / st if st else 0
        o[i] = 100 * (4 * avg(s) + 2 * avg(m) + avg(l)) / 7
    return o


# ---------- trend / directional ----------
def macd(close, f=12, s=26, sig=9):
    ef, es = ema(close, f), ema(close, s)
    line = [(ef[i] - es[i]) if (_isnum(ef[i]) and _isnum(es[i])) else None for i in range(len(close))]
    lc = [x if _isnum(x) else 0.0 for x in line]; sgn = ema(lc, sig)
    sg = [sgn[i] if _isnum(line[i]) else None for i in range(len(close))]
    hist = [(line[i] - sg[i]) if (_isnum(line[i]) and _isnum(sg[i])) else None for i in range(len(close))]
    return dict(macd=line, signal=sg, hist=hist)


def adx(bars, p=14):
    n = len(bars); tr = _tr(bars); pdm = [0.0] * n; ndm = [0.0] * n
    for i in range(1, n):
        up = bars[i]["high"] - bars[i - 1]["high"]; dn = bars[i - 1]["low"] - bars[i]["low"]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        ndm[i] = dn if (dn > up and dn > 0) else 0.0
    atrr = _rma(tr, p); pr = _rma(pdm, p); nr = _rma(ndm, p)
    pdi = [(100 * pr[i] / atrr[i]) if (_isnum(pr[i]) and atrr[i]) else None for i in range(n)]
    ndi = [(100 * nr[i] / atrr[i]) if (_isnum(nr[i]) and atrr[i]) else None for i in range(n)]
    dx = [(100 * abs(pdi[i] - ndi[i]) / (pdi[i] + ndi[i])) if (_isnum(pdi[i]) and (pdi[i] + ndi[i])) else None for i in range(n)]
    dxc = [x if _isnum(x) else 0.0 for x in dx]; adxx = _rma(dxc, p)
    return dict(adx=[adxx[i] if _isnum(dx[i]) else None for i in range(n)], pdi=pdi, ndi=ndi)


def aroon(bars, p=25):
    n = len(bars); up = [None] * n; dn = [None] * n
    for i in range(p, n):
        w_h = [bars[j]["high"] for j in range(i - p, i + 1)]; w_l = [bars[j]["low"] for j in range(i - p, i + 1)]
        hh = w_h.index(max(w_h)); ll = w_l.index(min(w_l))
        up[i] = hh / p * 100; dn[i] = ll / p * 100
    osc = [(up[i] - dn[i]) if (_isnum(up[i]) and _isnum(dn[i])) else None for i in range(n)]
    return dict(up=up, down=dn, osc=osc)


def supertrend(bars, p=10, mult=3.0):
    n = len(bars); a = atr(bars, p); st = [None] * n; dirn = [None] * n
    fub = flb = None; prev = None
    for i in range(n):
        if not _isnum(a[i]):
            continue
        hl2 = (bars[i]["high"] + bars[i]["low"]) / 2
        ub = hl2 + mult * a[i]; lb = hl2 - mult * a[i]; c = bars[i]["close"]; pc = bars[i - 1]["close"]
        fub = ub if (fub is None or ub < fub or pc > fub) else fub
        flb = lb if (flb is None or lb > flb or pc < flb) else flb
        if prev is None: prev = True
        if prev and c < flb: prev = False
        elif (not prev) and c > fub: prev = True
        st[i] = flb if prev else fub; dirn[i] = 1 if prev else -1
    return dict(supertrend=st, dir=dirn)


def psar(bars, step=0.02, maxstep=0.2):
    n = len(bars); ps = [None] * n
    if n < 2: return ps
    up = True; af = step; ep = bars[0]["high"]; sar = bars[0]["low"]
    for i in range(1, n):
        sar = sar + af * (ep - sar); h, l = bars[i]["high"], bars[i]["low"]
        if up:
            if l < sar: up = False; sar = ep; ep = l; af = step
            else:
                if h > ep: ep = h; af = min(af + step, maxstep)
        else:
            if h > sar: up = True; sar = ep; ep = h; af = step
            else:
                if l < ep: ep = l; af = min(af + step, maxstep)
        ps[i] = sar
    return ps


def ichimoku(bars, conv=9, base=26, span=52):
    n = len(bars)
    def midhl(p):
        o = [None] * n
        for i in range(p - 1, n):
            o[i] = (max(bars[j]["high"] for j in range(i - p + 1, i + 1)) +
                    min(bars[j]["low"] for j in range(i - p + 1, i + 1))) / 2
        return o
    tenkan = midhl(conv); kijun = midhl(base)
    spanA = [((tenkan[i] + kijun[i]) / 2) if (_isnum(tenkan[i]) and _isnum(kijun[i])) else None for i in range(n)]
    spanB = midhl(span)
    return dict(tenkan=tenkan, kijun=kijun, spanA=spanA, spanB=spanB)


# ---------- volume ----------
def obv(bars):
    n = len(bars); o = [0.0] * n
    for i in range(1, n):
        c, pc = bars[i]["close"], bars[i - 1]["close"]
        o[i] = o[i - 1] + (bars[i]["volume"] if c > pc else (-bars[i]["volume"] if c < pc else 0))
    return o


def vwap(bars):
    """VWAP cumulative all-time (hlc3). Kompat lama. Utk anchored+bands pakai vwap_anchored()."""
    n = len(bars); o = [None] * n; cpv = 0.0; cv = 0.0
    for i in range(n):
        tp = (bars[i]["high"] + bars[i]["low"] + bars[i]["close"]) / 3
        cpv += tp * bars[i]["volume"]; cv += bars[i]["volume"]; o[i] = cpv / cv if cv else None
    return o


def _src_series(bars, src="hlc3"):
    """Source TradingView: close/open/hl2/hlc3/ohlc4/hlcc4."""
    f = {
        "close": lambda b: b["close"], "open": lambda b: b["open"],
        "hl2": lambda b: (b["high"] + b["low"]) / 2,
        "hlc3": lambda b: (b["high"] + b["low"] + b["close"]) / 3,
        "ohlc4": lambda b: (b["open"] + b["high"] + b["low"] + b["close"]) / 4,
        "hlcc4": lambda b: (b["high"] + b["low"] + 2 * b["close"]) / 4,
    }.get(src, lambda b: (b["high"] + b["low"] + b["close"]) / 3)
    return [f(b) for b in bars]


def _period_key(ts, anchor):
    """Kunci periode anchor dari epoch detik (UTC). None = all-time (tak reset)."""
    d = _dt.datetime.fromtimestamp(ts, _dt.timezone.utc); a = (anchor or "").lower()
    if a in ("session", "day", "d"): return (d.year, d.month, d.day)
    if a in ("week", "w"): iso = d.isocalendar(); return (iso[0], iso[1])
    if a in ("month", "m"): return (d.year, d.month)
    if a in ("quarter", "q", "3m"): return (d.year, (d.month - 1) // 3)
    if a in ("year", "y", "12m"): return (d.year,)
    if a == "decade": return (d.year // 10,)
    if a == "century": return (d.year // 100,)
    return None


def vwap_anchored(bars, anchor="week", src="hlc3", bands=(1.0, 2.0, 3.0), mode="stdev"):
    """Anchored VWAP TradingView (konversi vwap.pine). Reset kumulatif tiap periode anchor.
    Bands = volume-weighted stdev (mode 'stdev') atau persen (mode 'percentage', basis=vwap*1%).
    Return dict(vwap=[...], bands={mult:(upper[],lower[])}, anchor, src, mode)."""
    n = len(bars); s = _src_series(bars, src)
    vw = [None] * n
    out = {m: ([None] * n, [None] * n) for m in bands}
    sumPV = sumV = sumPV2 = 0.0; prevkey = None
    for i in range(n):
        key = _period_key(bars[i]["time"], anchor)
        if anchor and key != prevkey:
            sumPV = sumV = sumPV2 = 0.0; prevkey = key
        v = bars[i]["volume"]; p = s[i]
        sumPV += p * v; sumV += v; sumPV2 += p * p * v
        if sumV > 0:
            vv = sumPV / sumV; vw[i] = vv
            var = max(sumPV2 / sumV - vv * vv, 0.0); sd = math.sqrt(var)
            basis = sd if mode == "stdev" else vv * 0.01
            for m in bands:
                out[m][0][i] = vv + basis * m
                out[m][1][i] = vv - basis * m
    return dict(vwap=vw, bands=out, anchor=anchor, src=src, mode=mode)


def cmf(bars, p=20):
    n = len(bars); mfv = [0.0] * n
    for i in range(n):
        h, l, c = bars[i]["high"], bars[i]["low"], bars[i]["close"]
        mult = ((c - l) - (h - c)) / (h - l) if h > l else 0.0
        mfv[i] = mult * bars[i]["volume"]
    o = [None] * n
    for i in range(p - 1, n):
        vv = sum(bars[j]["volume"] for j in range(i - p + 1, i + 1))
        o[i] = sum(mfv[i - p + 1:i + 1]) / vv if vv else 0.0
    return o


def ad(bars):
    n = len(bars); o = [0.0] * n
    for i in range(n):
        h, l, c = bars[i]["high"], bars[i]["low"], bars[i]["close"]
        mult = ((c - l) - (h - c)) / (h - l) if h > l else 0.0
        o[i] = (o[i - 1] if i else 0.0) + mult * bars[i]["volume"]
    return o


def force_index(bars, p=13):
    n = len(bars); fi = [0.0] * n
    for i in range(1, n): fi[i] = (bars[i]["close"] - bars[i - 1]["close"]) * bars[i]["volume"]
    return ema(fi, p)


def eom(bars, p=14):
    n = len(bars); e = [0.0] * n
    for i in range(1, n):
        hl = (bars[i]["high"] + bars[i]["low"]) / 2 - (bars[i - 1]["high"] + bars[i - 1]["low"]) / 2
        box = bars[i]["volume"] / (bars[i]["high"] - bars[i]["low"]) if bars[i]["high"] > bars[i]["low"] else 0
        e[i] = hl / box if box else 0.0
    return sma(e, p)


def pvt(bars):
    n = len(bars); o = [0.0] * n
    for i in range(1, n):
        pc = bars[i - 1]["close"]
        o[i] = o[i - 1] + ((bars[i]["close"] - pc) / pc * bars[i]["volume"] if pc else 0)
    return o


# ---------- ringkasan terbaru ----------
def _last(x): return x[-1] if x and _isnum(x[-1]) else None


def compute_all(bars) -> dict:
    """Hitung semua indikator, return nilai TERBARU (bar terakhir)."""
    if not bars or len(bars) < 30: return {}
    close = [b["close"] for b in bars]
    bb = bollinger(close); md = macd(close); ax = adx(bars); st = stoch(bars)
    srsi = stochrsi(close); ar = aroon(bars); sup = supertrend(bars); ich = ichimoku(bars)
    vw = vwap_anchored(bars, anchor="week", src="hlc3", bands=(1.0, 2.0))  # konversi vwap.pine
    vwv = _last(vw["vwap"]); u1 = _last(vw["bands"][1.0][0]); l1 = _last(vw["bands"][1.0][1])
    u2 = _last(vw["bands"][2.0][0]); l2 = _last(vw["bands"][2.0][1])
    c = close[-1]
    # zona harga vs VWAP mingguan
    vz = "?"
    if vwv:
        if u2 and c >= u2: vz = "≥+2σ (overbought)"
        elif u1 and c >= u1: vz = "+1σ..+2σ"
        elif c >= vwv: vz = "VWAP..+1σ"
        elif l1 and c > l1: vz = "-1σ..VWAP"
        elif l2 and c > l2: vz = "-2σ..-1σ"
        else: vz = "≤-2σ (oversold)"
    return {
        "close": c,
        # trend
        "ema9": _last(ema(close, 9)), "ema20": _last(ema(close, 20)),
        "ema50": _last(ema(close, 50)), "ema200": _last(ema(close, 200)),
        "sma20": _last(sma(close, 20)), "sma50": _last(sma(close, 50)),
        "hma20": _last(hma(close, 20)), "vwma20": _last(vwma(bars, 20)),
        "macd": _last(md["macd"]), "macd_signal": _last(md["signal"]), "macd_hist": _last(md["hist"]),
        "adx": _last(ax["adx"]), "pdi": _last(ax["pdi"]), "ndi": _last(ax["ndi"]),
        "aroon_osc": _last(ar["osc"]),
        "supertrend": _last(sup["supertrend"]), "supertrend_dir": _last(sup["dir"]),
        "psar": _last(psar(bars)),
        "ichimoku_tenkan": _last(ich["tenkan"]), "ichimoku_kijun": _last(ich["kijun"]),
        "ichimoku_spanA": _last(ich["spanA"]), "ichimoku_spanB": _last(ich["spanB"]),
        # momentum
        "rsi": _last(rsi(close)), "stoch_k": _last(st["k"]), "stoch_d": _last(st["d"]),
        "stochrsi_k": _last(srsi["k"]), "cci": _last(cci(bars)), "willr": _last(willr(bars)),
        "roc": _last(roc(close)), "mom": _last(mom(close)), "cmo": _last(cmo(close)),
        "mfi": _last(mfi(bars)), "tsi": _last(tsi(close)), "uo": _last(uo(bars)),
        # volatility
        "atr": _last(atr(bars)), "natr": _last(natr(bars)),
        "bb_upper": _last(bb["upper"]), "bb_lower": _last(bb["lower"]), "bb_bw": _last(bb["bandwidth"]),
        "donchian_up": _last(donchian(bars)["upper"]), "donchian_lo": _last(donchian(bars)["lower"]),
        # volume
        "obv": _last(obv(bars)), "cmf": _last(cmf(bars)),
        "ad": _last(ad(bars)), "force_index": _last(force_index(bars)),
        "eom": _last(eom(bars)), "pvt": _last(pvt(bars)),
        # VWAP anchored mingguan (hlc3) + stdev bands (konversi vwap.pine)
        "vwap_week": vwv, "vwap_w_upper1": u1, "vwap_w_lower1": l1,
        "vwap_w_upper2": u2, "vwap_w_lower2": l2,
        "vwap_dist_pct": ((c / vwv - 1) * 100) if vwv else None,
        "vwap_zone": vz,
    }


if __name__ == "__main__":
    import sys, exchanges
    base = sys.argv[1] if len(sys.argv) > 1 else "BTC"
    bars, ex = exchanges.best_klines(base, "1d", 300)
    if not bars: print("no data"); sys.exit()
    ind = compute_all(bars)
    print(f"{base} ({ex}) — {len(ind)} indikator (nilai terbaru):")
    for k, v in ind.items():
        print(f"  {k:18} {v:.4f}" if isinstance(v, float) else f"  {k:18} {v}")
