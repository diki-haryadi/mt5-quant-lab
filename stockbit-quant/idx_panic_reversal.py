"""
idx_panic_reversal.py — Strategi PANIC-SELL CAPITULATION -> FOREIGN ACCUMULATION REVERSAL (LQ45).
Ide Ben (dari widget Trade Flow): saat panic selling (harga drop + asing net JUAL), lalu sideway,
lalu "net buy masuk" (asing flip akumulasi) -> harga naik. Tangkap buyer itu, target +10%.

Backtest historis pakai net_foreign harian (10thn, proxy aliran dana broker besar).
  Entry (di close hari sinyal), semua syarat:
    1. CAPITULATION: drawdown close vs high-DDW hari >= DD (panic, harga drop)
    2. ASING DISTRIBUSI saat crash: Σ net_foreign[crash window, sebelum flip] < 0
    3. BASE/sideway: low hari ini > low minimum BASE hari sebelumnya (berhenti bikin low baru)
    4. AKUMULASI FLIP: Σ net_foreign NFW hari flip dari <=0 ke >0 (asing mulai beli)
    5. KONFIRMASI harga: close > close kemarin (hijau)
  Exit: TP +TP% | SL -SL% | time-stop HOLDMAX hari (mark close). SL didahulukan bila TP&SL sehari.
  Fee 0.2%/sisi, lot 100. 1 posisi/saham (no pyramiding).

Usage:
  python3 idx_panic_reversal.py                      # backtest basket LQ45 full
  python3 idx_panic_reversal.py --split              # + IS/OOS (paruh waktu)
  python3 idx_panic_reversal.py --sweep              # sweep param kunci
  python3 idx_panic_reversal.py --symbols BBCA,BBRI  # subset
  python3 idx_panic_reversal.py --perstock           # rincian per saham
"""
from __future__ import annotations
import argparse
import stockbit_history as H
import idx_indicators as ind

LQ45 = ["BBCA","BBRI","BMRI","BBNI","BRIS","BBTN","ARTO","TLKM","EXCL","ISAT","TOWR",
        "ASII","UNTR","ADRO","PTBA","ITMG","HRUM","ANTM","INCO","MDKA","TINS","MEDC",
        "PGAS","AKRA","ELSA","SMGR","INTP","INKP","TKIM","BRPT","ESSA","UNVR","ICBP",
        "INDF","MYOR","KLBF","SIDO","CPIN","JPFA","AMRT","ACES","MAPI","JSMR","TPIA","BRMS"]

FEE = 0.2  # %/sisi

DEF = dict(DDW=20, DD=0.08, DROPW=10, NFW=3, BASE=3, TP=0.10, SL=0.07, HOLDMAX=40,
           RSIMAX=100.0, VOLX=0.0, ACCFRAC=0.0)


def signals(bars, p):
    """Return list index entry-day (sinyal di close hari itu)."""
    n = len(bars)
    close = [b["close"] for b in bars]; high = [b["high"] for b in bars]; low = [b["low"] for b in bars]
    vol = [b.get("volume", 0) for b in bars]; nf = [b["net_foreign"] for b in bars]
    DDW, DD, DROPW, NFW, BASE = p["DDW"], p["DD"], p["DROPW"], p["NFW"], p["BASE"]
    RSIMAX, VOLX, ACCFRAC = p["RSIMAX"], p["VOLX"], p["ACCFRAC"]
    rsi = ind.rsi(close, 14) if RSIMAX < 100 else [None] * n
    vsma = ind.sma(vol, 20) if VOLX > 0 else [None] * n
    out = []
    start = max(DDW, DROPW + NFW, BASE, 20) + 1
    for i in range(start, n):
        # 1. capitulation: drawdown dari high DDW hari
        peak = max(high[i - DDW:i + 1])
        if peak <= 0: continue
        dd = close[i] / peak - 1.0
        if dd > -DD: continue
        # 2. asing distribusi saat crash (window sblm flip)
        distrib = sum(nf[i - DROPW + 1:i - NFW + 1])
        if distrib >= 0: continue
        # 4. akumulasi flip: Σnf NFW hari flip <=0 -> >0
        nf_now = sum(nf[i - NFW + 1:i + 1])
        nf_prev = sum(nf[i - NFW:i])
        if not (nf_now > 0 and nf_prev <= 0): continue
        # 4b. kekuatan akumulasi: inflow >= ACCFRAC * |outflow saat crash|
        if ACCFRAC > 0 and nf_now < ACCFRAC * abs(distrib): continue
        # 3. base/sideway: berhenti bikin low baru
        base_low = min(low[i - BASE:i])
        if low[i] <= base_low: continue
        # 5. konfirmasi hijau
        if close[i] <= close[i - 1]: continue
        # 6. RSI oversold (capitulation asli)
        if RSIMAX < 100:
            if rsi[i] is None or rsi[i] > RSIMAX: continue
        # 7. volume climax: ada hari volume >= VOLX*SMA20 dlm window crash
        if VOLX > 0:
            climax = False
            for k in range(i - DROPW + 1, i + 1):
                if vsma[k] and vsma[k] > 0 and vol[k] >= VOLX * vsma[k]: climax = True; break
            if not climax: continue
        out.append(i)
    return out


def run(bars, p):
    """Trade list dari sinyal; entry close hari sinyal, exit TP/SL/time."""
    sig = set(signals(bars, p))
    n = len(bars); TP, SL, HM = p["TP"], p["SL"], p["HOLDMAX"]
    trades = []; i = 0
    while i < n:
        if i not in sig:
            i += 1; continue
        entry = bars[i]["close"]; tp = entry * (1 + TP); sl = entry * (1 - SL)
        exitp = None; exiti = None; reason = None
        for j in range(i + 1, min(i + 1 + HM, n)):
            lo, hi = bars[j]["low"], bars[j]["high"]
            if lo <= sl:  # SL didahulukan (konservatif)
                exitp, exiti, reason = sl, j, "SL"; break
            if hi >= tp:
                exitp, exiti, reason = tp, j, "TP"; break
        if exitp is None:
            exiti = min(i + HM, n - 1); exitp = bars[exiti]["close"]; reason = "TIME"
        gross = exitp / entry - 1.0
        net = gross - 2 * FEE / 100  # fee 2 sisi (approx pada return)
        trades.append(dict(entry_i=i, exit_i=exiti, days=exiti - i, ret=net * 100,
                           reason=reason, entry=entry, exit=exitp,
                           date=bars[i]["date"], xdate=bars[exiti]["date"]))
        i = exiti + 1  # 1 posisi/saham, lanjut setelah exit
    return trades


def stats(trades):
    if not trades: return dict(n=0)
    rets = [t["ret"] for t in trades]
    wins = [r for r in rets if r > 0]
    gw = sum(wins); gl = -sum(r for r in rets if r <= 0)
    tp = sum(1 for t in trades if t["reason"] == "TP")
    return dict(n=len(trades), wr=len(wins) / len(trades) * 100,
                tp_rate=tp / len(trades) * 100,
                avg=sum(rets) / len(rets), med=sorted(rets)[len(rets) // 2],
                pf=(gw / gl) if gl else (99.9 if gw else 0),
                exp=sum(rets) / len(rets),
                avgdays=sum(t["days"] for t in trades) / len(trades),
                total=sum(rets))


def load(symbols, years):
    data = {}
    for s in symbols:
        try:
            b = H.historical(s, years=years)
            if len(b) > 300: data[s] = b
        except Exception as e:
            print(f"  ! {s}: {type(e).__name__}")
    return data


def fmt(tag, st):
    if not st.get("n"):
        print(f"{tag:<10} 0 trade"); return
    print(f"{tag:<10} {st['n']:>4} tr | WR {st['wr']:>4.0f}% | TP+10% {st['tp_rate']:>4.0f}% | "
          f"avg {st['avg']:>+5.1f}% | med {st['med']:>+5.1f}% | PF {st['pf']:>4.2f} | "
          f"exp {st['exp']:>+5.2f}% | hold {st['avgdays']:>4.0f}d")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=""); ap.add_argument("--years", type=float, default=10)
    ap.add_argument("--split", action="store_true"); ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--sweep2", action="store_true"); ap.add_argument("--perstock", action="store_true")
    ap.add_argument("--monthly", action="store_true")
    ap.add_argument("--modal", type=float, default=100_000_000); ap.add_argument("--bet", type=float, default=20_000_000)
    for k, v in DEF.items(): ap.add_argument(f"--{k}", type=type(v), default=v)
    a = ap.parse_args()
    p = {k: getattr(a, k) for k in DEF}
    syms = a.symbols.split(",") if a.symbols else LQ45
    print(f"Memuat {len(syms)} saham LQ45 ({a.years}thn harga+net_foreign)...")
    data = load(syms, a.years)
    print(f"  {len(data)} saham termuat.\n")

    if a.sweep:
        print("=== SWEEP param (DD x NFW x SL) ===")
        for DD in (0.06, 0.08, 0.10, 0.12):
            for NFW in (2, 3, 5):
                for SL in (0.05, 0.07, 0.10):
                    pp = dict(p, DD=DD, NFW=NFW, SL=SL)
                    allt = []
                    for b in data.values(): allt += run(b, pp)
                    st = stats(allt)
                    if st.get("n", 0) >= 30:
                        fmt(f"DD{DD:.2f}N{NFW}SL{SL:.2f}", st)
        return

    if a.sweep2:
        print("=== SWEEP2 filter kualitas (RSIMAX x VOLX x ACCFRAC), DD/SL default ===")
        for RSIMAX in (100.0, 40.0, 35.0, 30.0):
            for VOLX in (0.0, 1.5, 2.0):
                for ACCFRAC in (0.0, 0.3, 0.5):
                    pp = dict(p, RSIMAX=RSIMAX, VOLX=VOLX, ACCFRAC=ACCFRAC)
                    allt = []
                    for b in data.values(): allt += run(b, pp)
                    st = stats(allt)
                    if st.get("n", 0) >= 25:
                        # IS/OOS cek robust
                        a2 = sorted(allt, key=lambda t: t["date"]); mid = a2[len(a2) // 2]["date"]
                        oos = stats([t for t in a2 if t["date"] >= mid])
                        fmt(f"R{RSIMAX:.0f}V{VOLX:.1f}A{ACCFRAC:.1f}", st)
                        print(f"             └ OOS: PF {oos.get('pf',0):.2f} exp {oos.get('exp',0):+.2f}% n{oos.get('n',0)}")
        return

    allt = []; perstock = {}
    for s, b in data.items():
        t = run(b, p); allt += t; perstock[s] = t
    print(f"=== PANIC-REVERSAL LQ45 | DD{p['DD']} DROPW{p['DROPW']} NFW{p['NFW']} BASE{p['BASE']} "
          f"TP{p['TP']} SL{p['SL']} HOLD{p['HOLDMAX']} | fee {FEE}%/sisi ===")
    fmt("FULL", stats(allt))

    if a.split:
        # IS/OOS by entry calendar (paruh tanggal)
        allt2 = sorted(allt, key=lambda t: t["date"])
        if allt2:
            mid = allt2[len(allt2) // 2]["date"]
            IS = [t for t in allt2 if t["date"] < mid]; OOS = [t for t in allt2 if t["date"] >= mid]
            print(f"  (batas IS/OOS: {mid})")
            fmt("IS", stats(IS)); fmt("OOS", stats(OOS))
        # per tahun
        print("  per tahun masuk:")
        yrs = {}
        for t in allt:
            yrs.setdefault(t["date"][:4], []).append(t)
        for y in sorted(yrs):
            fmt("  " + y, stats(yrs[y]))

    if a.monthly:
        MON = ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"]
        # realisasi per bulan EXIT
        grid = {}  # (yr,mo) -> [rupiah,...]
        for t in allt:
            y, m = int(t["xdate"][:4]), int(t["xdate"][5:7])
            grid.setdefault((y, m), []).append(t["ret"] / 100 * a.bet)
        years = sorted({y for y, _ in grid})
        print(f"\n=== PROFIT PER BULAN (Rp) | modal {a.modal/1e6:.0f}jt · alokasi {a.bet/1e6:.0f}jt/sinyal · realisasi saat exit ===")
        print("Thn  " + "".join(f"{x:>8}" for x in MON) + f"{'TOTAL':>11}{'#tr':>5}")
        eq = a.modal; equ_start = a.modal
        for y in years:
            cells = []; ytot = 0; ytr = 0
            for m in range(1, 13):
                v = grid.get((y, m), [])
                s = sum(v); ytot += s; ytr += len(v)
                cells.append(f"{s/1e6:>+8.1f}" if v else f"{'·':>8}")
            eq += ytot
            print(f"{y} " + "".join(cells) + f"{ytot/1e6:>+10.1f}M{ytr:>5}")
        tot = eq - equ_start
        yrs_span = (years[-1] - years[0] + 1) if years else 1
        roi = tot / equ_start * 100
        print("-" * 110)
        print(f"TOTAL realisasi: Rp {tot/1e6:+.1f}jt  | equity {equ_start/1e6:.0f}jt → {eq/1e6:.1f}jt  "
              f"| ROI {roi:+.1f}% / {yrs_span}thn (≈{roi/yrs_span:+.1f}%/thn, non-compound)")
        # seasonality kalender (agregat 10thn) dalam net% rata2
        print("\n=== SEASONALITY (agregat semua tahun, net% rata-rata per bulan masuk) ===")
        bymon = {}
        for t in allt: bymon.setdefault(int(t["date"][5:7]), []).append(t["ret"])
        print("Bln   " + "".join(f"{MON[m-1]:>7}" for m in range(1, 13)))
        print("avg%  " + "".join((f"{sum(bymon[m])/len(bymon[m]):>+7.1f}" if bymon.get(m) else f"{'·':>7}") for m in range(1, 13)))
        print("#tr   " + "".join((f"{len(bymon[m]):>7}" if bymon.get(m) else f"{'·':>7}") for m in range(1, 13)))

    if a.perstock:
        print("\n=== per saham (>=3 trade), urut expectancy ===")
        rows = [(s, stats(t)) for s, t in perstock.items() if len(t) >= 3]
        rows.sort(key=lambda r: -r[1]["exp"])
        for s, st in rows: fmt(s, st)


if __name__ == "__main__":
    main()
