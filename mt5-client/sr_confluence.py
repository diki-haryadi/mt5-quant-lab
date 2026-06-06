"""sr_confluence.py — S/R KONFLUENSI MULTI-TF (ide Ben, versi pragmatis).
Bias  : 1D + 4H EMA50 harus SEARAH (dua-duanya bullish→hanya BUY; bearish→hanya SELL).
Zona  : level pivot-fractal dari H2,H1,M30,M15 (no-lookahead: dikonfirmasi L bar kemudian).
Skor  : berapa TF (dari 4) punya level dalam TOL*ATR(M15) dari harga → butuh >= MINSCORE (3).
Entry : rejection di bar M15 (sumbu tembus zona lalu close balik searah bias) + searah bias.
Exit  : SL di balik level terdekat (- SLBUF*ATR), TP = RMULT * risk. 1 posisi/saat. spread riil.
Split : IS/OOS (paruh waktu). Modal $1000, risk 0.5%."""
import math, datetime as dt, bisect, sys
from mt5_scalper import MT5Api, calc_lot
from backtest_lab import atr_series

API = "http://192.168.0.111:8000"
BAL, RISK, MAXR, ATRP = 1000.0, 0.5, 6.0, 14
TOL = 0.6        # lebar zona = TOL * ATR(M15)
SLBUF = 0.5      # SL = level - SLBUF*ATR (di balik level)
RMULT = 1.5
MINSCORE = 3
PIVL = 4         # fractal lookback/forward
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
    """list (known_time, price) — extreme di i, BARU diketahui di bar i+L (no-lookahead)."""
    n = len(bars); hi = [b['high'] for b in bars]; lo = [b['low'] for b in bars]; out = []
    for i in range(L, n - L):
        if hi[i] == max(hi[i - L:i + L + 1]): out.append((bars[i + L]['time'], hi[i]))
        if lo[i] == min(lo[i - L:i + L + 1]): out.append((bars[i + L]['time'], lo[i]))
    out.sort()  # by known_time
    return out


def fetch(sym, tf, frm, to):
    d = api._get(f"/api/symbols/{sym}/bars/range", timeframe=tf, from_time=str(frm), to_time=str(to))
    return d.get("bars", []) if isinstance(d, dict) else []


def run(sym, verbose=False):
    end = int(dt.datetime.now().timestamp()); start = int((dt.datetime.now() - dt.timedelta(days=DAYS)).timestamp())
    m15 = fetch(sym, "M15", start, end)
    if len(m15) < 1500:
        return {"sym": sym, "err": f"M15 cuma {len(m15)} bar"}
    sinfo = api.symbol_info(sym); pt = sinfo["point"]; tk = sinfo.get("trade_tick_size") or pt; tv = sinfo.get("trade_tick_value") or 1.0
    money = lambda d, lot: (d / tk) * tv * lot
    d1 = fetch(sym, "D1", start, end); h4 = fetch(sym, "H4", start, end)
    confTF = {"H2": pivots(fetch(sym, "H2", start, end)), "H1": pivots(fetch(sym, "H1", start, end)),
              "M30": pivots(fetch(sym, "M30", start, end)), "M15": pivots(m15)}
    d1c = [b['close'] for b in d1]; d1e = ema(d1c, 50)
    h4c = [b['close'] for b in h4]; h4e = ema(h4c, 50)
    atr = atr_series(m15, ATRP)

    # pointer-based active level lists per TF (sorted by price), tambah saat known_time<=t
    ptr = {k: 0 for k in confTF}; active = {k: [] for k in confTF}

    def near_level(tf, price, tol):
        a = active[tf]
        if not a: return None
        i = bisect.bisect_left(a, price)
        best = None
        for j in (i - 1, i):
            if 0 <= j < len(a) and abs(a[j] - price) <= tol:
                if best is None or abs(a[j] - price) < abs(best - price): best = a[j]
        return best

    pd_ = ph = 0
    bal = BAL; peak = BAL; ddp = 0.0; T = []; pos = None
    skip_bias = skip_score = 0
    for i in range(60, len(m15)):
        b = m15[i]; t = b['time']
        # exit posisi dulu (bar-by-bar)
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
                T.append({"net": net, "t": t, "win": net > 0, "side": pos['side']}); pos = None
        if pos: continue
        a = atr[i]
        if math.isnan(a) or a <= 0: continue
        # advance active level lists
        for tf, piv in confTF.items():
            p = ptr[tf]
            while p < len(piv) and piv[p][0] <= t:
                bisect.insort(active[tf], piv[p][1]); p += 1
            ptr[tf] = p
        # bias (last completed D1 & H4)
        while pd_ + 1 < len(d1) and d1[pd_ + 1]['time'] <= t: pd_ += 1
        while ph + 1 < len(h4) and h4[ph + 1]['time'] <= t: ph += 1
        if math.isnan(d1e[pd_]) or math.isnan(h4e[ph]): continue
        bd = d1[pd_]['close'] > d1e[pd_]; bh = h4[ph]['close'] > h4e[ph]
        bias = 1 if (bd and bh) else (-1 if (not bd and not bh) else 0)
        if bias == 0: skip_bias += 1; continue
        # skor konfluensi
        tol = TOL * a; price = b['close']
        lv_hit = [near_level(tf, price, tol) for tf in confTF]
        score = sum(1 for x in lv_hit if x is not None)
        if score < MINSCORE: skip_score += 1; continue
        near = [x for x in lv_hit if x is not None]
        zone = sum(near) / len(near)  # rata-rata level terdekat = pusat zona
        # trigger rejection searah bias
        if bias == 1:
            rej = (b['low'] <= zone + tol) and (b['close'] > b['open']) and (b['close'] > zone)
            if not rej: continue
            sl = min(near) - SLBUF * a; risk = price - sl
            if risk <= 0: continue
            tp = price + RMULT * risk; side = 'buy'
        else:
            rej = (b['high'] >= zone - tol) and (b['close'] < b['open']) and (b['close'] < zone)
            if not rej: continue
            sl = max(near) + SLBUF * a; risk = sl - price
            if risk <= 0: continue
            tp = price - RMULT * risk; side = 'sell'
        lot, est = calc_lot(bal * RISK / 100, risk, sinfo)
        if est > bal * MAXR / 100: continue
        spr = b['spread'] * pt
        pos = dict(side=side, e=price, lot=lot, spr=spr, sl=sl, tp=tp, score=score)

    if not T:
        return {"sym": sym, "n": 0, "skip_bias": skip_bias, "skip_score": skip_score}
    # split IS/OOS by time (paruh)
    half = (T[0]['t'] + T[-1]['t']) // 2
    def stats(tr):
        if not tr: return None
        w = [x for x in tr if x['win']]; l = [x for x in tr if not x['win']]
        gw = sum(x['net'] for x in w); gl = -sum(x['net'] for x in l)
        return dict(n=len(tr), win=len(w) / len(tr) * 100, net=sum(x['net'] for x in tr),
                    plus=gw, minus=gl, pf=(gw / gl) if gl else 999)
    IS = stats([x for x in T if x['t'] < half]); OOS = stats([x for x in T if x['t'] >= half])
    full = stats(T)
    return {"sym": sym, "bars_m15": len(m15), "full": full, "IS": IS, "OOS": OOS,
            "dd": ddp, "skip_bias": skip_bias, "skip_score": skip_score}


if __name__ == "__main__":
    syms = sys.argv[1:] or SYMS
    print(f"S/R KONFLUENSI multi-TF | bias 1D+4H | konfluensi >=3/4 (H2,H1,M30,M15) | TOL{TOL}ATR RMULT{RMULT} | {DAYS}d M15")
    print("=" * 92)
    for s in syms:
        r = run(s)
        if r.get("err"): print(f"{s:8} ERR {r['err']}"); continue
        if r.get("n") == 0: print(f"{s:8} 0 trade (skip_bias={r['skip_bias']} skip_score={r['skip_score']})"); continue
        f = r['full']; I = r['IS']; O = r['OOS']
        print(f"\n{s} | {r['bars_m15']} bar M15 | maxDD {r['dd']:.1f}% | skip_bias {r['skip_bias']} skip_score {r['skip_score']}")
        print(f"  FULL: {f['n']:3} tr | WR {f['win']:.0f}% | PF {f['pf']:.2f} | net ${f['net']:+.0f} (untung ${f['plus']:.0f} / rugi ${f['minus']:.0f})")
        if I: print(f"  IS  : {I['n']:3} tr | WR {I['win']:.0f}% | PF {I['pf']:.2f} | net ${I['net']:+.0f}")
        if O: print(f"  OOS : {O['n']:3} tr | WR {O['win']:.0f}% | PF {O['pf']:.2f} | net ${O['net']:+.0f}")
