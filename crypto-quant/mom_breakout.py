"""
mom_breakout.py — Strategi MOMENTUM / TREND-FOLLOWING (Donchian breakout + ATR chandelier trail).
Kebalikan MR-VWAP: ikut ACCEPTANCE (harga tembus range & diterima) = trend continuation.
Pelajaran MR: crypto majors 2024-26 TREND kuat -> sisi breakout yg punya edge.

Entry (no-lookahead, di close):
  LONG : close[i] > Donchian-high(DCN) dari bar i-DCN..i-1 (tembus range atas).
  SHORT: close[i] < Donchian-low(DCN).
Stop : awal = ATRMULT×ATR dari entry; lalu TRAIL (chandelier: extreme-since-entry ∓ ATRMULT×ATR).
Exit tambahan: close menembus Donchian-exit(DCX) sisi lawan (turtle-style).
NO fixed TP (winner dibiarkan lari). Filter trend opsional: EMA(EMAFILT). fee taker per sisi.

Usage:
  python3 mom_breakout.py --symbols BTC,ETH,SOL --tf 4h --days 720 --report
  python3 mom_breakout.py --group l1 --split
  python3 mom_breakout.py --sweep
"""
from __future__ import annotations
import argparse, datetime as _dt
import exchanges as EX
import indicators as TA
import universe as U

FEE = 0.05  # %/sisi taker
DEF = dict(DCN=20, DCX=10, ATRMULT=3.0, ATRLEN=14, EMAFILT=0, DIR="both")


def backtest(bars, p, fund=None):
    n = len(bars)
    if n < 300: return []
    close = [b["close"] for b in bars]; high = [b["high"] for b in bars]; low = [b["low"] for b in bars]
    atr = TA.atr(bars, int(p["ATRLEN"]))
    ema = TA.ema(close, int(p["EMAFILT"])) if p["EMAFILT"] else None
    DCN, DCX, M, DIR = int(p["DCN"]), int(p["DCX"]), p["ATRMULT"], p["DIR"]
    start = max(DCN, DCX, int(p["ATRLEN"]), int(p["EMAFILT"] or 0)) + 1
    trades = []; pos = None
    for i in range(start, n):
        a = atr[i]
        if a is None or a <= 0: continue
        if pos:
            if fund is not None: pos["fund"] = pos.get("fund", 0.0) + fund[i]
            ex = None
            if pos["side"] == "long":
                if low[i] <= pos["stop"]: ex = (pos["stop"], "STOP")
                elif close[i] < min(low[i - DCX:i]): ex = (close[i], "DCEXIT")
                else:
                    pos["ext"] = max(pos["ext"], high[i]); pos["stop"] = max(pos["stop"], pos["ext"] - M * a)
            else:
                if high[i] >= pos["stop"]: ex = (pos["stop"], "STOP")
                elif close[i] > max(high[i - DCX:i]): ex = (close[i], "DCEXIT")
                else:
                    pos["ext"] = min(pos["ext"], low[i]); pos["stop"] = min(pos["stop"], pos["ext"] + M * a)
            if ex:
                px, reason = ex
                g = (px / pos["entry"] - 1) if pos["side"] == "long" else (1 - px / pos["entry"])
                fr = (-pos.get("fund", 0.0)) if pos["side"] == "long" else pos.get("fund", 0.0)
                net = g - 2 * FEE / 100 + fr
                trades.append(dict(side=pos["side"], ret=net * 100, R=net / pos["risk"] if pos["risk"] else 0,
                                   reason=reason, date=pos["date"], bars=i - pos["i"]))
                pos = None
        if pos is None:
            dch = max(high[i - DCN:i]); dcl = min(low[i - DCN:i])
            up = close[i] > dch; dn = close[i] < dcl
            if DIR in ("both", "long") and up and (ema is None or (ema[i] and close[i] > ema[i])):
                stop = close[i] - M * a
                pos = dict(side="long", entry=close[i], stop=stop, ext=high[i], risk=(M * a) / close[i],
                           i=i, date=_dt.datetime.fromtimestamp(bars[i]["time"], _dt.timezone.utc).strftime("%Y-%m-%d"))
            elif DIR in ("both", "short") and dn and (ema is None or (ema[i] and close[i] < ema[i])):
                stop = close[i] + M * a
                pos = dict(side="short", entry=close[i], stop=stop, ext=low[i], risk=(M * a) / close[i],
                           i=i, date=_dt.datetime.fromtimestamp(bars[i]["time"], _dt.timezone.utc).strftime("%Y-%m-%d"))
    if pos:
        px = close[-1]; g = (px / pos["entry"] - 1) if pos["side"] == "long" else (1 - px / pos["entry"])
        fr = (-pos.get("fund", 0.0)) if pos["side"] == "long" else pos.get("fund", 0.0)
        net = g - 2 * FEE / 100 + fr
        trades.append(dict(side=pos["side"], ret=net * 100, R=net / pos["risk"] if pos["risk"] else 0,
                           reason="END", date=pos["date"], bars=n - 1 - pos["i"]))
    return trades


def stats(tr):
    if not tr: return dict(n=0)
    rets = [t["ret"] for t in tr]; Rs = [t["R"] for t in tr]
    wins = [r for r in rets if r > 0]; gw = sum(wins); gl = -sum(r for r in rets if r <= 0)
    wR = [t["R"] for t in tr if t["R"] > 0]; lR = [t["R"] for t in tr if t["R"] <= 0]
    return dict(n=len(tr), wr=len(wins) / len(tr) * 100, pf=(gw / gl) if gl else (99.9 if gw else 0),
                expR=sum(Rs) / len(Rs), total=sum(rets), totR=sum(Rs),
                avgwin=sum(wR) / len(wR) if wR else 0, avgloss=sum(lR) / len(lR) if lR else 0,
                avgbars=sum(t["bars"] for t in tr) / len(tr))


def fmt(tag, s):
    if not s.get("n"): print(f"{tag:<12} 0 trade"); return
    print(f"{tag:<12} {s['n']:>4} tr | WR {s['wr']:>4.0f}% | PF {s['pf']:>4.2f} | exp {s['expR']:>+5.2f}R "
          f"| win {s['avgwin']:>+4.1f}R loss {s['avgloss']:>+4.1f}R | totR {s['totR']:>+6.0f} | hold {s['avgbars']:>4.0f}b")


def report(trades, capital=10000.0):
    if not trades: print("no trades"); return
    tr = sorted(trades, key=lambda t: t["date"]); bet = capital
    eq = capital; peak = capital; maxdd = 0.0; monthly = {}; pertoken = {}; gw = gl = 0.0; wins = 0
    for t in tr:
        pl = t["ret"] / 100 * bet; eq += pl; peak = max(peak, eq); maxdd = max(maxdd, (peak - eq) / peak * 100 if peak > 0 else 0)
        monthly.setdefault(t["date"][:7], []).append(pl); pertoken.setdefault(t.get("sym", "?"), []).append(pl)
        if pl > 0: gw += pl; wins += 1
        else: gl += -pl
    n = len(tr); net = eq - capital
    print("=" * 70); print(f"LAPORAN P/L — MOMENTUM BREAKOUT (notional ${bet:,.0f}/trade)"); print("=" * 70)
    print(f"Periode {tr[0]['date']} → {tr[-1]['date']} | {n} trade | Win {wins} ({wins/n*100:.0f}%)")
    print(f"Gross +${gw:,.0f} / -${gl:,.0f}  | NET {'+' if net>=0 else '-'}${abs(net):,.0f} (ROI {net/capital*100:+.0f}%)")
    print(f"Profit Factor {(gw/gl if gl else 99.9):.2f} | total {sum(t['R'] for t in tr):+.0f}R | Max DD {maxdd:.0f}%")
    print("--- per token ---")
    for s in sorted(pertoken, key=lambda s: -sum(pertoken[s])):
        v = pertoken[s]; print(f"  {s:<6} {len(v):>3} tr  net ${sum(v):>+10,.0f}")
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
    ap.add_argument("--capital", type=float, default=10000.0); ap.add_argument("--futures", action="store_true")
    for k, v in DEF.items(): ap.add_argument(f"--{k}", type=type(v), default=v)
    a = ap.parse_args()
    p = {k: getattr(a, k) for k in DEF}
    syms = a.symbols.split(",") if a.symbols else U.filter_universe(a.group)
    src = "FUTURES+funding" if a.futures else "SPOT"
    print(f"Memuat {len(syms)} token {a.tf} × {a.days}d ({src})...")
    data = {}
    for s in syms:
        if a.futures:
            b = EX.history_fut(s, a.tf, a.days, a.quote)
            if b and len(b) > 300: data[s] = (b, EX.fund_per_bar(b, EX.funding_history(s, a.days, a.quote)))
        else:
            b = EX.history(s, a.tf, a.days, a.quote)
            if b and len(b) > 300: data[s] = (b, None)
    print(f"  {len(data)} token termuat.\n")

    def run_all(pp):
        out = []
        for s, (b, fb) in data.items():
            t = backtest(b, pp, fb)
            for x in t: x["sym"] = s
            out += t
        return out

    if a.sweep:
        print("=== SWEEP DCN x ATRMULT x EMAFILT ===")
        for DCN in (10, 20, 30, 55):
            for M in (2.0, 3.0, 4.0):
                for EF in (0, 100, 200):
                    pp = dict(p, DCN=DCN, ATRMULT=M, EMAFILT=EF); allt = run_all(pp); s = stats(allt)
                    if s.get("n", 0) >= 20:
                        a2 = sorted(allt, key=lambda t: t["date"]); mid = a2[len(a2) // 2]["date"]
                        oos = stats([t for t in a2 if t["date"] >= mid])
                        fmt(f"DC{DCN}M{M}E{EF}", s)
                        print(f"           └ OOS PF {oos.get('pf',0):.2f} exp {oos.get('expR',0):+.2f}R n{oos.get('n',0)}")
        return

    allt = run_all(p)
    print(f"=== MOMENTUM BREAKOUT {a.tf} | DCN{p['DCN']} DCX{p['DCX']} ATR×{p['ATRMULT']} "
          f"EMA{p['EMAFILT']} dir={p['DIR']} | fee {FEE}%/sisi ===")
    fmt("FULL", stats(allt))
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
