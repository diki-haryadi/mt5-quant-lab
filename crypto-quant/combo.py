"""
combo.py — Sistem REGIME-SWITCHING: momentum (trend) + mean-reversion (range), 1 akun.
Gabungan strategi 1 (mr_vwap, gagal di trend) + strategi 2 (mom_breakout, menang di trend).
Tesis: pakai tiap strategi HANYA di regime favoritnya -> lebih konsisten / DD lebih kecil.

Regime per bar (ADX): ADX >= ADXTHR = TREND -> momentum; ADX < ADXTHR = RANGE -> MR.
  TREND/momentum : Donchian breakout(DCN) + EMA(EMAFILT) filter + ATR chandelier trail + DC-exit(DCX).
  RANGE/MR       : fade ±DEVσ weekly-VWAP (deviasi keluar lalu masuk), SL pct-lebar,
                   TP1 VWAP (50%, SL->BE), TP2 +1σ (runner). bias prev-weekly-VWAP.
1 posisi/saat. NO fixed-TP momentum. fee taker. MRON=0 -> momentum-gated saja (range = flat).

Usage:
  python3 combo.py --symbols BTC,ETH,SOL --tf 4h --days 720 --split --report
  python3 combo.py --group l1 --sweep        # sweep ADXTHR x MRON
"""
from __future__ import annotations
import argparse, datetime as _dt
import exchanges as EX
import indicators as TA
import universe as U

FEE = 0.05
DEF = dict(ADXTHR=25.0, ADXLEN=14, MRON=1,
           DCN=30, DCX=10, ATRMULT=3.0, ATRLEN=14, EMAFILT=200,        # momentum
           DEV=2.0, SLPCT=2.0, TP1FRAC=0.5, PREVFILTER=1)              # mean-reversion


def _date(bars, i):
    return _dt.datetime.fromtimestamp(bars[i]["time"], _dt.timezone.utc).strftime("%Y-%m-%d")


def prev_weekly_vwap(bars, vwl):
    n = len(bars); out = [None] * n; prevf = None; lastk = None; runf = None
    for i in range(n):
        k = TA._period_key(bars[i]["time"], "week")
        if lastk is not None and k != lastk: prevf = runf
        out[i] = prevf
        if vwl[i] is not None: runf = vwl[i]
        lastk = k
    return out


def backtest(bars, p):
    n = len(bars)
    if n < 400: return []
    close = [b["close"] for b in bars]; high = [b["high"] for b in bars]; low = [b["low"] for b in bars]
    atr = TA.atr(bars, int(p["ATRLEN"]))
    adxl = TA.adx(bars, int(p["ADXLEN"]))["adx"]
    ema = TA.ema(close, int(p["EMAFILT"])) if p["EMAFILT"] else None
    DEV = p["DEV"]
    vw = TA.vwap_anchored(bars, anchor="week", src="hlc3", bands=(1.0, DEV))
    vwap = vw["vwap"]; upD = vw["bands"][DEV][0]; loD = vw["bands"][DEV][1]
    up1 = vw["bands"][1.0][0]; lo1 = vw["bands"][1.0][1]
    pwv = prev_weekly_vwap(bars, vwap)
    DCN, DCX, M, ADXTHR, MRON = int(p["DCN"]), int(p["DCX"]), p["ATRMULT"], p["ADXTHR"], int(p["MRON"])
    start = max(DCN, DCX, int(p["ATRLEN"]), int(p["EMAFILT"] or 0), int(p["ADXLEN"]), 60) + 1
    trades = []; pos = None
    dev_lo = False; exc_lo = 1e18; dev_hi = False; exc_hi = -1e18

    def rec(px, reason):
        g = (px / pos["entry"] - 1) if pos["side"] == "long" else (1 - px / pos["entry"])
        net = (pos.get("realized", 0.0) + (1 - pos.get("partf", 0.0)) * g) - 2 * FEE / 100
        trades.append(dict(side=pos["side"], kind=pos["kind"], ret=net * 100,
                           R=net / pos["risk"] if pos["risk"] else 0, reason=reason,
                           date=pos["date"], bars=pos.get("_i", 0)))

    for i in range(start, n):
        a = atr[i]
        if a is None or a <= 0 or vwap[i] is None: continue
        # selalu lacak deviasi VWAP (untuk MR)
        if low[i] < loD[i]: dev_lo = True; exc_lo = min(exc_lo, low[i])
        if high[i] > upD[i]: dev_hi = True; exc_hi = max(exc_hi, high[i])
        reenter_lo = dev_lo and close[i] >= loD[i]; reenter_hi = dev_hi and close[i] <= upD[i]

        if pos:
            pos["_i"] = i - pos["i"]; ex = None
            if pos["kind"] == "mom":
                if pos["side"] == "long":
                    if low[i] <= pos["stop"]: ex = (pos["stop"], "STOP")
                    elif close[i] < min(low[i - DCX:i]): ex = (close[i], "DCEXIT")
                    else: pos["ext"] = max(pos["ext"], high[i]); pos["stop"] = max(pos["stop"], pos["ext"] - M * a)
                else:
                    if high[i] >= pos["stop"]: ex = (pos["stop"], "STOP")
                    elif close[i] > max(high[i - DCX:i]): ex = (close[i], "DCEXIT")
                    else: pos["ext"] = min(pos["ext"], low[i]); pos["stop"] = min(pos["stop"], pos["ext"] + M * a)
                if ex: rec(ex[0], ex[1]); pos = None
            else:  # MR
                if pos["side"] == "long":
                    if low[i] <= pos["sl"]: rec(pos["sl"], "SL"); pos = None
                    elif not pos["tp1"] and high[i] >= vwap[i]:
                        pos["tp1"] = True; pos["realized"] += p["TP1FRAC"] * (vwap[i] / pos["entry"] - 1)
                        pos["partf"] += p["TP1FRAC"]; pos["sl"] = pos["entry"]
                    elif pos["tp1"] and high[i] >= up1[i]: rec(up1[i], "TP2"); pos = None
                else:
                    if high[i] >= pos["sl"]: rec(pos["sl"], "SL"); pos = None
                    elif not pos["tp1"] and low[i] <= vwap[i]:
                        pos["tp1"] = True; pos["realized"] += p["TP1FRAC"] * (1 - vwap[i] / pos["entry"])
                        pos["partf"] += p["TP1FRAC"]; pos["sl"] = pos["entry"]
                    elif pos["tp1"] and low[i] <= lo1[i]: rec(lo1[i], "TP2"); pos = None
            if reenter_lo: dev_lo = False; exc_lo = 1e18
            if reenter_hi: dev_hi = False; exc_hi = -1e18
            continue

        regime = "trend" if (adxl[i] is not None and adxl[i] >= ADXTHR) else "range"
        if regime == "trend":  # MOMENTUM breakout
            dch = max(high[i - DCN:i]); dcl = min(low[i - DCN:i])
            if close[i] > dch and (ema is None or (ema[i] and close[i] > ema[i])):
                pos = dict(kind="mom", side="long", entry=close[i], stop=close[i] - M * a, ext=high[i],
                           risk=(M * a) / close[i], i=i, date=_date(bars, i))
            elif close[i] < dcl and (ema is None or (ema[i] and close[i] < ema[i])):
                pos = dict(kind="mom", side="short", entry=close[i], stop=close[i] + M * a, ext=low[i],
                           risk=(M * a) / close[i], i=i, date=_date(bars, i))
        elif MRON:  # RANGE -> MEAN-REVERSION
            if reenter_lo:
                sl = pos_sl = close[i] * (1 - p["SLPCT"] / 100)
                if not (p["PREVFILTER"] and pwv[i] and close[i] < pwv[i]):
                    pos = dict(kind="mr", side="long", entry=close[i], sl=sl, init=sl, tp1=False,
                               realized=0.0, partf=0.0, risk=p["SLPCT"] / 100, i=i, date=_date(bars, i))
            elif reenter_hi:
                sl = close[i] * (1 + p["SLPCT"] / 100)
                if not (p["PREVFILTER"] and pwv[i] and close[i] > pwv[i]):
                    pos = dict(kind="mr", side="short", entry=close[i], sl=sl, init=sl, tp1=False,
                               realized=0.0, partf=0.0, risk=p["SLPCT"] / 100, i=i, date=_date(bars, i))
        if reenter_lo: dev_lo = False; exc_lo = 1e18
        if reenter_hi: dev_hi = False; exc_hi = -1e18
    if pos:
        rec(close[-1], "END")
    return trades


def stats(tr, kind=None):
    t = [x for x in tr if kind is None or x["kind"] == kind]
    if not t: return dict(n=0)
    rets = [x["ret"] for x in t]; Rs = [x["R"] for x in t]; wins = [r for r in rets if r > 0]
    gw = sum(wins); gl = -sum(r for r in rets if r <= 0)
    return dict(n=len(t), wr=len(wins) / len(t) * 100, pf=(gw / gl) if gl else (99.9 if gw else 0),
                expR=sum(Rs) / len(Rs), totR=sum(Rs), total=sum(rets))


def fmt(tag, s):
    if not s.get("n"): print(f"{tag:<12} 0 trade"); return
    print(f"{tag:<12} {s['n']:>4} tr | WR {s['wr']:>4.0f}% | PF {s['pf']:>4.2f} | exp {s['expR']:>+5.2f}R | totR {s['totR']:>+6.0f}")


def report(trades, capital=10000.0):
    if not trades: print("no trades"); return
    tr = sorted(trades, key=lambda t: t["date"]); eq = capital; peak = capital; mdd = 0.0
    monthly = {}; gw = gl = 0.0; wins = 0
    for t in tr:
        pl = t["ret"] / 100 * capital; eq += pl; peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak * 100 if peak > 0 else 0)
        monthly.setdefault(t["date"][:7], []).append(pl)
        if pl > 0: gw += pl; wins += 1
        else: gl += -pl
    n = len(tr); net = eq - capital
    print("=" * 70); print(f"LAPORAN P/L — COMBO regime-switching (notional ${capital:,.0f}/trade)"); print("=" * 70)
    print(f"{tr[0]['date']} → {tr[-1]['date']} | {n} trade | Win {wins} ({wins/n*100:.0f}%)")
    print(f"NET {'+' if net>=0 else '-'}${abs(net):,.0f} (ROI {net/capital*100:+.0f}%) | PF {(gw/gl if gl else 99.9):.2f} | Max DD {mdd:.0f}%")
    print(f"  momentum: " + str(stats(trades, 'mom')))
    print(f"  mean-rev: " + str(stats(trades, 'mr')))
    print("--- per bulan ---"); run = capital
    for m in sorted(monthly):
        v = monthly[m]; run += sum(v); print(f"  {m}  {sum(v):>+10,.0f}  ({len(v)})  eq ${run:>10,.0f}")
    print("=" * 70)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=""); ap.add_argument("--group", default="l1")
    ap.add_argument("--tf", default="4h"); ap.add_argument("--days", type=int, default=720)
    ap.add_argument("--quote", default="USDT"); ap.add_argument("--split", action="store_true")
    ap.add_argument("--sweep", action="store_true"); ap.add_argument("--report", action="store_true")
    ap.add_argument("--capital", type=float, default=10000.0)
    for k, v in DEF.items(): ap.add_argument(f"--{k}", type=type(v), default=v)
    a = ap.parse_args()
    p = {k: getattr(a, k) for k in DEF}
    syms = a.symbols.split(",") if a.symbols else U.filter_universe(a.group)
    print(f"Memuat {len(syms)} token {a.tf} × {a.days}d...")
    data = {}
    for s in syms:
        b = EX.history(s, a.tf, a.days, a.quote)
        if b and len(b) > 400: data[s] = b
    print(f"  {len(data)} token termuat.\n")

    def run_all(pp):
        out = []
        for s, b in data.items():
            t = backtest(b, pp)
            for x in t: x["sym"] = s
            out += t
        return out

    if a.sweep:
        print("=== SWEEP ADXTHR x MRON ===")
        for THR in (18, 22, 25, 30):
            for MR in (0, 1):
                pp = dict(p, ADXTHR=float(THR), MRON=MR); allt = run_all(pp); s = stats(allt)
                if s.get("n", 0) >= 20:
                    a2 = sorted(allt, key=lambda t: t["date"]); mid = a2[len(a2) // 2]["date"]
                    oos = stats([t for t in a2 if t["date"] >= mid])
                    fmt(f"ADX{THR} MR{MR}", s)
                    print(f"           └ OOS PF {oos.get('pf',0):.2f} exp {oos.get('expR',0):+.2f}R | mom {stats(allt,'mom').get('pf',0):.2f} / mr {stats(allt,'mr').get('pf',0):.2f}")
        return

    allt = run_all(p)
    print(f"=== COMBO {a.tf} | ADXthr{p['ADXTHR']} MRon{p['MRON']} | mom(DC{p['DCN']}/ATR{p['ATRMULT']}/EMA{p['EMAFILT']}) "
          f"mr(±{p['DEV']}σ/SL{p['SLPCT']}%) ===")
    fmt("FULL", stats(allt)); fmt("  momentum", stats(allt, "mom")); fmt("  mean-rev", stats(allt, "mr"))
    if a.split:
        a2 = sorted(allt, key=lambda t: t["date"]); mid = a2[len(a2) // 2]["date"]
        fmt("IS", stats([t for t in a2 if t["date"] < mid])); fmt("OOS", stats([t for t in a2 if t["date"] >= mid]))
        yrs = {}
        for t in allt: yrs.setdefault(t["date"][:4], []).append(t)
        for y in sorted(yrs): fmt("  " + y, stats(yrs[y]))
    if a.report:
        print(); report(allt, a.capital)


if __name__ == "__main__":
    main()
