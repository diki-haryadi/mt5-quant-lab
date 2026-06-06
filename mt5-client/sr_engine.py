"""sr_engine.py — backtest S/R konfluensi sebagai FUNGSI (dipakai /v1/backtest app).
bt(api, sym, capital, risk, days, rmult) -> {stats, curve, trades} (format app)."""
import math, datetime as dt, bisect
from backtest_lab import atr_series
from mt5_scalper import calc_lot

NEAR, CLUST, ENTRYTOL, SLBUF, MINTF, COOLDOWN, PIVL, ATRP, MAXR = 1.2, 0.30, 0.5, 0.5, 3, 16, 4, 14, 6.0
TFS = ["H2", "H1", "M30", "M15"]

def _ema(c, p):
    n = len(c); o = [float('nan')] * n
    if n < p: return o
    k = 2 / (p + 1); s = sum(c[:p]) / p; o[p - 1] = s
    for i in range(p, n): s = c[i] * k + s * (1 - k); o[i] = s
    return o

def _piv(bars, L=PIVL):
    n = len(bars); hi = [b['high'] for b in bars]; lo = [b['low'] for b in bars]; out = []
    for i in range(L, n - L):
        if hi[i] == max(hi[i - L:i + L + 1]): out.append((bars[i + L]['time'], hi[i]))
        if lo[i] == min(lo[i - L:i + L + 1]): out.append((bars[i + L]['time'], lo[i]))
    out.sort(); return out

def _fetch(api, sym, tf, frm, to):
    d = api._get(f"/api/symbols/{sym}/bars/range", timeframe=tf, from_time=str(frm), to_time=str(to))
    return d.get("bars", []) if isinstance(d, dict) else []

def bt(api, sym, capital=1000.0, risk=0.5, days=540, rmult=2.0):
    end = int(dt.datetime.now().timestamp()); start = int((dt.datetime.now() - dt.timedelta(days=days)).timestamp())
    m15 = _fetch(api, sym, "M15", start, end)
    if len(m15) < 800: raise RuntimeError(f"M15 {len(m15)} bar (kurang)")
    sinfo = api.symbol_info(sym); pt = sinfo["point"]; tk = sinfo.get("trade_tick_size") or pt; tv = sinfo.get("trade_tick_value") or 1.0
    money = lambda d, lot: (d / tk) * tv * lot
    d1 = _fetch(api, sym, "D1", start, end); h4 = _fetch(api, sym, "H4", start, end)
    conf = {"H2": _piv(_fetch(api, sym, "H2", start, end)), "H1": _piv(_fetch(api, sym, "H1", start, end)),
            "M30": _piv(_fetch(api, sym, "M30", start, end)), "M15": _piv(m15)}
    d1e = _ema([b['close'] for b in d1], 50); h4e = _ema([b['close'] for b in h4], 50); atr = atr_series(m15, ATRP)
    ptr = {k: 0 for k in TFS}; active = {k: [] for k in TFS}
    def near(tf, lo, hi):
        a = active[tf]; i = bisect.bisect_left(a, lo); j = bisect.bisect_right(a, hi); return a[i:j]
    def cluster(price, tn, tc):
        pts = []
        for tf in TFS:
            for lv in near(tf, price - tn, price + tn): pts.append((lv, tf))
        if len(pts) < MINTF: return None
        pts.sort(); best = None
        for x in range(len(pts)):
            grp = [pts[x]]
            for y in range(x + 1, len(pts)):
                if pts[y][0] - pts[x][0] <= tc: grp.append(pts[y])
                else: break
            if len(set(g[1] for g in grp)) >= MINTF:
                ctr = sum(g[0] for g in grp) / len(grp); cand = (ctr, grp[0][0], grp[-1][0])
                if best is None or abs(ctr - price) < abs(best[0] - price): best = cand
        return best
    pd_ = ph = 0; bal = capital; peak = capital; ddp = 0.0; T = []; pos = None; leb = -10 ** 9; lz = None
    t0 = m15[0]['time']
    for i in range(60, len(m15)):
        b = m15[i]; t = b['time']
        if pos:
            hit = None
            if pos['side'] == 'buy':
                if b['low'] <= pos['sl']: hit = pos['sl']
                elif b['high'] >= pos['tp']: hit = pos['tp']
            else:
                if b['high'] >= pos['sl']: hit = pos['sl']
                elif b['low'] <= pos['tp']: hit = pos['tp']
            if hit is not None:
                plp = (hit - pos['e']) if pos['side'] == 'buy' else (pos['e'] - hit)
                net = money(plp, pos['lot']) - money(pos['spr'], pos['lot']); bal += net
                peak = max(peak, bal); ddp = max(ddp, (peak - bal) / peak * 100 if peak > 0 else 0)
                T.append({"side": pos['side'], "net": net, "day": (t - t0) // 86400, "bal": bal}); pos = None
        if pos: continue
        a = atr[i]
        if math.isnan(a) or a <= 0: continue
        for tf in TFS:
            piv = conf[tf]; p = ptr[tf]
            while p < len(piv) and piv[p][0] <= t: bisect.insort(active[tf], piv[p][1]); p += 1
            ptr[tf] = p
        if i - leb < COOLDOWN: continue
        while pd_ + 1 < len(d1) and d1[pd_ + 1]['time'] <= t: pd_ += 1
        while ph + 1 < len(h4) and h4[ph + 1]['time'] <= t: ph += 1
        if math.isnan(d1e[pd_]) or math.isnan(h4e[ph]): continue
        bd = d1[pd_]['close'] > d1e[pd_]; bh = h4[ph]['close'] > h4e[ph]
        bias = 1 if (bd and bh) else (-1 if (not bd and not bh) else 0)
        if bias == 0: continue
        price = b['close']; cl = cluster(price, NEAR * a, CLUST * a)
        if cl is None: continue
        ctr, clo, chi = cl
        if abs(ctr - price) > ENTRYTOL * a: continue
        if lz is not None and abs(ctr - lz) < 0.6 * a and i - leb < 80: continue
        rng = b['high'] - b['low']
        if rng <= 0: continue
        if bias == 1:
            if not ((b['low'] <= chi + ENTRYTOL * a) and (b['close'] > b['open']) and (b['close'] > ctr)): continue
            sl = clo - SLBUF * a; rk = price - sl
            if rk <= 0: continue
            tp = price + rmult * rk; side = 'buy'
        else:
            if not ((b['high'] >= clo - ENTRYTOL * a) and (b['close'] < b['open']) and (b['close'] < ctr)): continue
            sl = chi + SLBUF * a; rk = sl - price
            if rk <= 0: continue
            tp = price - rmult * rk; side = 'sell'
        lot, est = calc_lot(bal * risk / 100, rk, sinfo)
        if est > bal * MAXR / 100: continue
        pos = dict(side=side, e=price, lot=lot, spr=b['spread'] * pt, sl=sl, tp=tp); leb = i; lz = ctr
    w = [x for x in T if x['net'] > 0]; gw = sum(x['net'] for x in w); gl = -sum(x['net'] for x in T if x['net'] <= 0)
    curve = [capital] + [x['bal'] for x in T]
    if len(curve) > 60:
        s = len(curve) / 60.0; curve = [curve[min(int(i * s), len(curve) - 1)] for i in range(60)]
    rets = [x['net'] / capital for x in T]
    import statistics
    sharpe = (statistics.mean(rets) / statistics.pstdev(rets) * (len(rets) ** 0.5)) if len(rets) > 1 and statistics.pstdev(rets) > 0 else 0.0
    trades = [{"n": i + 1, "dir": "LONG" if x['side'] == 'buy' else "SHORT", "day": int(x['day']),
               "pnl": round(x['net'], 2), "win": x['net'] > 0} for i, x in enumerate(T)]
    return {"stats": {"totalReturn": round((bal - capital) / capital * 100, 2), "finalEquity": int(bal),
                      "winRate": int(len(w) / len(T) * 100) if T else 0, "profitFactor": round((gw / gl) if gl else 99.0, 2),
                      "maxDD": round(ddp, 2), "sharpe": round(sharpe, 2)},
            "curve": curve, "trades": trades, "source": "sr-engine"}
