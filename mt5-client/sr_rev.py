"""sr_rev.py — uji strategi swing sr-conf NORMAL vs REVERSED (sinyal dibalik) di XAUUSD.
Config swing: bias D1+H4, konfluensi >=3/{H2,H1,M30,M15}, entry M15, RMULT2.0, wick0. 540d.
Reverse: di bar sinyal yg sama, side dibalik + SL/TP dicerminkan (taruhan level JEBOL, bukan mantul)."""
import math, datetime as dt, bisect, sys
from mt5_scalper import MT5Api, calc_lot
from backtest_lab import atr_series

API = "http://192.168.0.111:8000"
BAL, RISK, MAXR, ATRP = 1000.0, 0.5, 6.0, 14
NEAR, CLUST, ENTRYTOL, SLBUF, MINTF, RMULT, PIVL, DAYS = 1.2, 0.30, 0.5, 0.5, 3, 2.0, 4, 540
TFS = ["H2", "H1", "M30", "M15"]
api = MT5Api(API, timeout=120)
def ema(c, p):
    n = len(c); o = [float('nan')] * n
    if n < p: return o
    k = 2 / (p + 1); s = sum(c[:p]) / p; o[p - 1] = s
    for i in range(p, n): s = c[i] * k + s * (1 - k); o[i] = s
    return o
def pivots(bars, L=PIVL):
    n = len(bars); hi = [b['high'] for b in bars]; lo = [b['low'] for b in bars]; out = []
    for i in range(L, n - L):
        if hi[i] == max(hi[i - L:i + L + 1]): out.append((bars[i + L]['time'], hi[i]))
        if lo[i] == min(lo[i - L:i + L + 1]): out.append((bars[i + L]['time'], lo[i]))
    out.sort(); return out
def fetch(sym, tf, frm, to):
    d = api._get(f"/api/symbols/{sym}/bars/range", timeframe=tf, from_time=str(frm), to_time=str(to))
    return d.get("bars", []) if isinstance(d, dict) else []

def runtrades(sym, reverse=False):
    end = int(dt.datetime.now().timestamp()); start = int((dt.datetime.now() - dt.timedelta(days=DAYS)).timestamp())
    m15 = fetch(sym, "M15", start, end)
    if len(m15) < 1500: return None, None
    sinfo = api.symbol_info(sym); pt = sinfo["point"]; tk = sinfo.get("trade_tick_size") or pt; tv = sinfo.get("trade_tick_value") or 1.0
    money = lambda d, lot: (d / tk) * tv * lot
    d1 = fetch(sym, "D1", start, end); h4 = fetch(sym, "H4", start, end)
    conf = {"H2": pivots(fetch(sym, "H2", start, end)), "H1": pivots(fetch(sym, "H1", start, end)),
            "M30": pivots(fetch(sym, "M30", start, end)), "M15": pivots(m15)}
    d1e = ema([b['close'] for b in d1], 50); h4e = ema([b['close'] for b in h4], 50); atr = atr_series(m15, ATRP)
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
    pd_ = ph = 0; bal = BAL; T = []; pos = None; leb = -10 ** 9; lz = None
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
                T.append({"t": t, "net": net}); pos = None
        if pos: continue
        a = atr[i]
        if math.isnan(a) or a <= 0: continue
        for tf in TFS:
            piv = conf[tf]; p = ptr[tf]
            while p < len(piv) and piv[p][0] <= t: bisect.insort(active[tf], piv[p][1]); p += 1
            ptr[tf] = p
        if i - leb < 16: continue
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
        # --- deteksi sinyal asli ---
        sig = None
        if bias == 1 and (b['low'] <= chi + ENTRYTOL * a) and (b['close'] > b['open']) and (b['close'] > ctr): sig = 'buy'
        elif bias == -1 and (b['high'] >= clo - ENTRYTOL * a) and (b['close'] < b['open']) and (b['close'] < ctr): sig = 'sell'
        if not sig: continue
        side = sig
        if reverse: side = 'sell' if sig == 'buy' else 'buy'
        # SL/TP utk arah final (dicerminkan)
        if side == 'buy':
            sl = clo - SLBUF * a; rk = price - sl
        else:
            sl = chi + SLBUF * a; rk = sl - price
        if rk <= 0: continue
        tp = price + RMULT * rk if side == 'buy' else price - RMULT * rk
        lot, est = calc_lot(bal * RISK / 100, rk, sinfo)
        if est > bal * MAXR / 100: continue
        pos = dict(side=side, e=price, lot=lot, spr=b['spread'] * pt, sl=sl, tp=tp); leb = i; lz = ctr
    return T, (m15[0]['time'], m15[-1]['time'])

def st(tr):
    if not tr: return (0, 0, 0, 0)
    w = [x for x in tr if x['net'] > 0]; gw = sum(x['net'] for x in w); gl = -sum(x['net'] for x in tr if x['net'] <= 0)
    return (len(tr), len(w) / len(tr) * 100, (gw / gl) if gl else 999, sum(x['net'] for x in tr))

def report(sym, rev):
    T, span = runtrades(sym, rev)
    tag = "REVERSED" if rev else "NORMAL"
    if not T: print(f"[{tag}] data kurang"); return
    half = (span[0] + span[1]) // 2
    F = st(T); IS = st([x for x in T if x['t'] < half]); OOS = st([x for x in T if x['t'] >= half])
    N = 6; edges = [span[0] + (span[1] - span[0]) * k // N for k in range(N + 1)]
    pc = sum(1 for k in range(N) if st([x for x in T if edges[k] <= x['t'] < edges[k + 1]])[3] > 0)
    print(f"[{tag}] FULL {F[0]}tr WR{F[1]:.0f}% PF{F[2]:.2f} net${F[3]:+.0f} | IS PF{IS[2]:.2f} | OOS PF{OOS[2]:.2f} | profit {pc}/6 window")

if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"
    print(f"SR-CONF SWING — NORMAL vs REVERSED | {sym} | {DAYS}d")
    print("=" * 80)
    report(sym, False)
    report(sym, True)
