"""sr_confluence2.py — S/R KONFLUENSI v2 (cluster sejati + cooldown + trigger ketat).
Beda dari v1: 'konfluensi' = level dari >=3 TF BERBEDA berkumpul rapat (cluster), bukan sekadar
masing-masing TF punya level dekat harga. + cooldown (anti re-entry zona sama) + rejection wick ketat.
Bias 1D+4H EMA50 searah. SL di balik cluster, TP=RMULT*R. IS/OOS. Modal $1000 risk 0.5%."""
import math, datetime as dt, bisect, sys
from mt5_scalper import MT5Api, calc_lot
from backtest_lab import atr_series

API = "http://192.168.0.111:8000"
BAL, RISK, MAXR, ATRP = 1000.0, 0.5, 6.0, 14
NEAR = 1.2        # window cari level di sekitar harga (×ATR)
CLUST = 0.30      # lebar cluster (level dianggap "sama") (×ATR)
ENTRYTOL = 0.5    # harga harus dalam ENTRYTOL×ATR dari pusat cluster
SLBUF = 0.5
RMULT = 1.8
MINTF = 3         # minimal TF berbeda dalam 1 cluster
COOLDOWN = 16     # bar M15 jeda antar entry (16 = 4 jam)
PIVL = 4
DAYS = 540
SYMS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
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
    out.sort()
    return out


def fetch(sym, tf, frm, to):
    d = api._get(f"/api/symbols/{sym}/bars/range", timeframe=tf, from_time=str(frm), to_time=str(to))
    return d.get("bars", []) if isinstance(d, dict) else []


def run(sym):
    end = int(dt.datetime.now().timestamp()); start = int((dt.datetime.now() - dt.timedelta(days=DAYS)).timestamp())
    m15 = fetch(sym, "M15", start, end)
    if len(m15) < 1500: return {"sym": sym, "err": f"M15 {len(m15)} bar"}
    sinfo = api.symbol_info(sym); pt = sinfo["point"]; tk = sinfo.get("trade_tick_size") or pt; tv = sinfo.get("trade_tick_value") or 1.0
    money = lambda d, lot: (d / tk) * tv * lot
    d1 = fetch(sym, "D1", start, end); h4 = fetch(sym, "H4", start, end)
    TFS = ["H2", "H1", "M30", "M15"]
    confTF = {"H2": pivots(fetch(sym, "H2", start, end)), "H1": pivots(fetch(sym, "H1", start, end)),
              "M30": pivots(fetch(sym, "M30", start, end)), "M15": pivots(m15)}
    d1c = [b['close'] for b in d1]; d1e = ema(d1c, 50)
    h4c = [b['close'] for b in h4]; h4e = ema(h4c, 50)
    atr = atr_series(m15, ATRP)
    ptr = {k: 0 for k in TFS}; active = {k: [] for k in TFS}

    def levels_near(tf, lo, hi):
        a = active[tf]
        i = bisect.bisect_left(a, lo); j = bisect.bisect_right(a, hi)
        return a[i:j]

    def best_cluster(price, tol_near, tol_clust):
        """cari cluster level (>=MINTF TF berbeda) terdekat ke harga. return (center,lo,hi,ntf) | None."""
        pts = []  # (level, tf)
        for tf in TFS:
            for lv in levels_near(tf, price - tol_near, price + tol_near):
                pts.append((lv, tf))
        if len(pts) < MINTF: return None
        pts.sort()
        best = None
        for a in range(len(pts)):
            grp = [pts[a]]
            for b in range(a + 1, len(pts)):
                if pts[b][0] - pts[a][0] <= tol_clust: grp.append(pts[b])
                else: break
            tfs = set(x[1] for x in grp)
            if len(tfs) >= MINTF:
                ctr = sum(x[0] for x in grp) / len(grp)
                cand = (ctr, grp[0][0], grp[-1][0], len(tfs))
                if best is None or abs(ctr - price) < abs(best[0] - price): best = cand
        return best

    pd_ = ph = 0
    bal = BAL; peak = BAL; ddp = 0.0; T = []; pos = None
    last_entry_bar = -10 ** 9; last_zone = None
    skip_bias = skip_clust = skip_cd = 0
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
                T.append({"net": net, "t": t, "win": net > 0, "score": pos['score']}); pos = None
        if pos: continue
        a = atr[i]
        if math.isnan(a) or a <= 0: continue
        for tf in TFS:
            piv = confTF[tf]; p = ptr[tf]
            while p < len(piv) and piv[p][0] <= t:
                bisect.insort(active[tf], piv[p][1]); p += 1
            ptr[tf] = p
        if i - last_entry_bar < COOLDOWN: skip_cd += 1; continue
        while pd_ + 1 < len(d1) and d1[pd_ + 1]['time'] <= t: pd_ += 1
        while ph + 1 < len(h4) and h4[ph + 1]['time'] <= t: ph += 1
        if math.isnan(d1e[pd_]) or math.isnan(h4e[ph]): continue
        bd = d1[pd_]['close'] > d1e[pd_]; bh = h4[ph]['close'] > h4e[ph]
        bias = 1 if (bd and bh) else (-1 if (not bd and not bh) else 0)
        if bias == 0: skip_bias += 1; continue
        price = b['close']
        cl = best_cluster(price, NEAR * a, CLUST * a)
        if cl is None: skip_clust += 1; continue
        ctr, clo, chi, ntf = cl
        if abs(ctr - price) > ENTRYTOL * a: skip_clust += 1; continue
        if last_zone is not None and abs(ctr - last_zone) < 0.6 * a and i - last_entry_bar < 80:
            skip_cd += 1; continue
        rng = b['high'] - b['low']
        if rng <= 0: continue
        if bias == 1:
            lwick = min(b['open'], b['close']) - b['low']
            rej = (b['low'] <= chi + ENTRYTOL * a) and (b['close'] > b['open']) and (b['close'] > ctr) and (lwick / rng >= 0.4)
            if not rej: continue
            sl = clo - SLBUF * a; risk = price - sl
            if risk <= 0: continue
            tp = price + RMULT * risk; side = 'buy'
        else:
            uwick = b['high'] - max(b['open'], b['close'])
            rej = (b['high'] >= clo - ENTRYTOL * a) and (b['close'] < b['open']) and (b['close'] < ctr) and (uwick / rng >= 0.4)
            if not rej: continue
            sl = chi + SLBUF * a; risk = sl - price
            if risk <= 0: continue
            tp = price - RMULT * risk; side = 'sell'
        lot, est = calc_lot(bal * RISK / 100, risk, sinfo)
        if est > bal * MAXR / 100: continue
        pos = dict(side=side, e=price, lot=lot, spr=b['spread'] * pt, sl=sl, tp=tp, score=ntf)
        last_entry_bar = i; last_zone = ctr

    if not T: return {"sym": sym, "n": 0, "skip_bias": skip_bias, "skip_clust": skip_clust, "skip_cd": skip_cd}
    half = (T[0]['t'] + T[-1]['t']) // 2
    def stats(tr):
        if not tr: return None
        w = [x for x in tr if x['win']]; gw = sum(x['net'] for x in w); gl = -sum(x['net'] for x in tr if not x['win'])
        return dict(n=len(tr), win=len(w) / len(tr) * 100, net=sum(x['net'] for x in tr), pf=(gw / gl) if gl else 999)
    return {"sym": sym, "bars": len(m15), "dd": ddp, "full": stats(T),
            "IS": stats([x for x in T if x['t'] < half]), "OOS": stats([x for x in T if x['t'] >= half])}


if __name__ == "__main__":
    syms = sys.argv[1:] or SYMS
    print(f"S/R KONFLUENSI v2 (cluster>={MINTF}TF, cooldown{COOLDOWN}, rejWick0.4, RMULT{RMULT}) | {DAYS}d M15")
    print("=" * 92)
    for s in syms:
        r = run(s)
        if r.get("err"): print(f"{s:8} ERR {r['err']}"); continue
        if r.get("n") == 0: print(f"{s:8} 0 trade (bias{r['skip_bias']} clust{r['skip_clust']} cd{r['skip_cd']})"); continue
        f, I, O = r['full'], r['IS'], r['OOS']
        print(f"\n{s} | {r['bars']} bar | maxDD {r['dd']:.1f}%")
        print(f"  FULL: {f['n']:3} tr | WR {f['win']:.0f}% | PF {f['pf']:.2f} | net ${f['net']:+.0f}")
        if I: print(f"  IS  : {I['n']:3} tr | WR {I['win']:.0f}% | PF {I['pf']:.2f} | net ${I['net']:+.0f}")
        if O: print(f"  OOS : {O['n']:3} tr | WR {O['win']:.0f}% | PF {O['pf']:.2f} | net ${O['net']:+.0f}")
