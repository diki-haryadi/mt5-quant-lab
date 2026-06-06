"""sr_mtf.py — S/R konfluensi GENERALIZED (TF entry/bias/konfluensi bisa diatur).
Default = jalan-tengah: entry M5, bias M30+M15 (semua searah), konfluensi >=3 dari {H1,M30,M15,M10}.
IS/OOS + walk-forward. risk 0.5%, RMULT 2.0, no wick-filter. spread riil."""
import math, datetime as dt, bisect, sys
from mt5_scalper import MT5Api, calc_lot
from backtest_lab import atr_series

API = "http://192.168.0.111:8000"
BAL, RISK, MAXR, ATRP = 1000.0, 0.5, 6.0, 14
NEAR, CLUST, ENTRYTOL, SLBUF, MINTF, RMULT, PIVL = 1.2, 0.30, 0.5, 0.5, 3, 2.0, 4
# ── config jalan-tengah ──
ENTRY = "M5"; BIAS = ["M30", "M15"]; CONF = ["H1", "M30", "M15", "M10"]; COOLDOWN = 12; DAYS = 150
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

def runtrades(sym):
    end = int(dt.datetime.now().timestamp()); start = int((dt.datetime.now() - dt.timedelta(days=DAYS)).timestamp())
    em = fetch(sym, ENTRY, start, end)
    if len(em) < 4000: return None, None, len(em)
    sinfo = api.symbol_info(sym); pt = sinfo["point"]; tk = sinfo.get("trade_tick_size") or pt; tv = sinfo.get("trade_tick_value") or 1.0
    money = lambda d, lot: (d / tk) * tv * lot
    biasbars = {tf: fetch(sym, tf, start, end) for tf in BIAS}
    biasema = {tf: ema([b['close'] for b in biasbars[tf]], 50) for tf in BIAS}
    biasptr = {tf: 0 for tf in BIAS}
    conf = {tf: pivots(em if tf == ENTRY else fetch(sym, tf, start, end)) for tf in CONF}
    atr = atr_series(em, ATRP)
    ptr = {k: 0 for k in CONF}; active = {k: [] for k in CONF}
    def near(tf, lo, hi):
        a = active[tf]; i = bisect.bisect_left(a, lo); j = bisect.bisect_right(a, hi); return a[i:j]
    def cluster(price, tn, tc):
        pts = []
        for tf in CONF:
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
    bal = BAL; T = []; pos = None; leb = -10 ** 9; lz = None
    for i in range(60, len(em)):
        b = em[i]; t = b['time']
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
        for tf in CONF:
            piv = conf[tf]; p = ptr[tf]
            while p < len(piv) and piv[p][0] <= t: bisect.insort(active[tf], piv[p][1]); p += 1
            ptr[tf] = p
        if i - leb < COOLDOWN: continue
        # bias: semua TF bias searah
        dirs = []
        ok = True
        for tf in BIAS:
            bb = biasbars[tf]; be = biasema[tf]
            while biasptr[tf] + 1 < len(bb) and bb[biasptr[tf] + 1]['time'] <= t: biasptr[tf] += 1
            j = biasptr[tf]
            if math.isnan(be[j]): ok = False; break
            dirs.append(1 if bb[j]['close'] > be[j] else -1)
        if not ok: continue
        bias = dirs[0] if all(d == dirs[0] for d in dirs) else 0
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
            tp = price + RMULT * rk; side = 'buy'
        else:
            if not ((b['high'] >= clo - ENTRYTOL * a) and (b['close'] < b['open']) and (b['close'] < ctr)): continue
            sl = chi + SLBUF * a; rk = sl - price
            if rk <= 0: continue
            tp = price - RMULT * rk; side = 'sell'
        lot, est = calc_lot(bal * RISK / 100, rk, sinfo)
        if est > bal * MAXR / 100: continue
        pos = dict(side=side, e=price, lot=lot, spr=b['spread'] * pt, sl=sl, tp=tp); leb = i; lz = ctr
    return T, (em[0]['time'], em[-1]['time']), len(em)

def st(tr):
    if not tr: return (0, 0, 0, 0)
    w = [x for x in tr if x['net'] > 0]; gw = sum(x['net'] for x in w); gl = -sum(x['net'] for x in tr if x['net'] <= 0)
    return (len(tr), len(w) / len(tr) * 100, (gw / gl) if gl else 999, sum(x['net'] for x in tr))

if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"
    print(f"MTF {sym} | entry {ENTRY} | bias {'+'.join(BIAS)} | konfluensi>=3/{{{','.join(CONF)}}} | RMULT{RMULT} cd{COOLDOWN} | {DAYS}d")
    print("=" * 72)
    T, span, nb = runtrades(sym)
    if not T: print(f"data kurang (bar {ENTRY}={nb})"); sys.exit()
    print(f"bar {ENTRY}={nb}")
    half = (span[0] + span[1]) // 2
    IS = st([x for x in T if x['t'] < half]); OOS = st([x for x in T if x['t'] >= half]); F = st(T)
    print(f"FULL: {F[0]} tr | WR {F[1]:.0f}% | PF {F[2]:.2f} | net ${F[3]:+.0f}")
    print(f"IS  : {IS[0]} tr | WR {IS[1]:.0f}% | PF {IS[2]:.2f} | net ${IS[3]:+.0f}")
    print(f"OOS : {OOS[0]} tr | WR {OOS[1]:.0f}% | PF {OOS[2]:.2f} | net ${OOS[3]:+.0f}")
    N = 6; edges = [span[0] + (span[1] - span[0]) * k // N for k in range(N + 1)]; pc = 0
    print("walk-forward:")
    for k in range(N):
        seg = st([x for x in T if edges[k] <= x['t'] < edges[k + 1]])
        if seg[0] == 0: print(f"  W{k+1}: 0 tr"); continue
        if seg[3] > 0: pc += 1
        print(f"  W{k+1}: {seg[0]:>4} tr | WR {seg[1]:.0f}% | PF {seg[2]:.2f} | net ${seg[3]:+.0f}")
    print(f">> profit {pc}/{N} {'✅' if pc>=N-1 else ('⚠️' if pc>=N//2 else '❌')}")
