"""
mr_vwap.py — Strategi MEAN-REVERSION VWAP (Auction Market Theory) di TF 30m.
Ide Ben + AMT (tradingriot): harga lelang KELUAR dari value (band ±DEVσ developing weekly VWAP)
lalu DITOLAK & MASUK lagi -> fade balik ke value (mean reversion).

Indikator: developing weekly VWAP (hlc3) + stdev bands + previous-weekly-VWAP (level acuan AMT).
Entry (close 30m, no-lookahead):
  LONG : low menembus < -DEVσ (excursion keluar bawah) lalu close kembali >= -DEVσ (masuk value).
         SL = excursion low (last low). TP1 = developing weekly VWAP. TP2 = +1σ band.
  SHORT: mirror (excursion > +DEVσ lalu close <= +DEVσ). SL=last high. TP1=VWAP. TP2=-1σ band.
Manajemen: scale 50% @TP1 + 50% @TP2; opsi SL->BE setelah TP1; time-stop akhir minggu (auction baru) + MAXBARS.
Filter opsional: prev-weekly-VWAP (LONG hanya bila harga >= prevWVWAP, dst). Fee taker per sisi.

Usage:
  python3 mr_vwap.py --symbols BTC,ETH,SOL --days 540
  python3 mr_vwap.py --group dat --split           # IS/OOS + walk-forward
  python3 mr_vwap.py --sweep                        # sweep DEV x BE x prevfilter
"""
from __future__ import annotations
import argparse
import exchanges as EX
import indicators as TA
import universe as U

FEE = 0.05  # %/sisi (taker spot crypto)
DEF = dict(DEV=2.0, TP2BAND=1.0, MAXBARS=240, BE_AFTER_TP1=1, PREVFILTER=0, MAXOUT=6,
           NOFILTER=0, NOTIMESTOP=0, REGIME="off", ADXMAX=22.0, ROTMAX=1.5, ADXLEN=14,
           TP1FRAC=0.5, SLMODE="lastlow", SLATR=1.5, SLATRLEN=14, SLPCT=2.0, SLRR=1.5,
           TPMODE="vwap", TP1R=1.0, TP2R=2.0)


def prev_weekly_vwap(bars, vw):
    """Level VWAP final minggu SEBELUMNYA, carried ke tiap bar (acuan AMT)."""
    n = len(bars); out = [None] * n; prev_final = None; last_key = None; running_final = None
    for i in range(n):
        key = TA._period_key(bars[i]["time"], "week")
        if last_key is not None and key != last_key:
            prev_final = running_final  # minggu ganti -> kunci nilai final minggu lalu
        out[i] = prev_final
        if vw["vwap"][i] is not None:
            running_final = vw["vwap"][i]
        last_key = key
    return out


def backtest(bars, p):
    n = len(bars)
    if n < 400:
        return []
    DEV = p["DEV"]
    vw = TA.vwap_anchored(bars, anchor="week", src="hlc3", bands=(1.0, DEV))
    vwap = vw["vwap"]; upD = vw["bands"][DEV][0]; loD = vw["bands"][DEV][1]
    up1 = vw["bands"][1.0][0]; lo1 = vw["bands"][1.0][1]
    pwv = prev_weekly_vwap(bars, vw)
    close = [b["close"] for b in bars]; high = [b["high"] for b in bars]; low = [b["low"] for b in bars]
    REGIME = p["REGIME"]; ADXMAX = p["ADXMAX"]; ROTMAX = p["ROTMAX"]; TP1FRAC = p["TP1FRAC"]
    adxl = TA.adx(bars, int(p["ADXLEN"]))["adx"] if REGIME in ("adx", "both") else None
    SLMODE = p["SLMODE"]; TPMODE = p["TPMODE"]; TP1R = p["TP1R"]; TP2R = p["TP2R"]
    atrl = TA.atr(bars, int(p["SLATRLEN"])) if SLMODE == "atr" else None

    def calc_sl(side, entry, exc, i):
        """SL geometry. lastlow=excursion-extreme (spec asli). atr/pct/rr=lebih ketat -> R:R lebih baik."""
        if SLMODE == "atr" and atrl[i]:
            d = p["SLATR"] * atrl[i]
            return entry - d if side == "long" else entry + d
        if SLMODE == "pct":
            d = entry * p["SLPCT"] / 100.0
            return entry - d if side == "long" else entry + d
        if SLMODE == "rr" and vwap[i]:
            risk = abs(vwap[i] - entry) / p["SLRR"]   # TP1(VWAP) = SLRR x risk
            return entry - risk if side == "long" else entry + risk
        return exc  # lastlow

    def regime_ok(i):
        if REGIME == "off":
            return True
        if REGIME in ("adx", "both"):
            if adxl[i] is None or adxl[i] >= ADXMAX:
                return False
        if REGIME in ("rot", "both"):
            if not (pwv[i] and vwap[i]) or abs(vwap[i] - pwv[i]) / vwap[i] * 100 >= ROTMAX:
                return False
        return True

    MAXOUT = p["MAXOUT"]
    trades = []; pos = None
    dev_lo = False; exc_lo = 1e18; out_lo = 0; dev_hi = False; exc_hi = -1e18; out_hi = 0
    for i in range(1, n):
        if vwap[i] is None or loD[i] is None:
            continue
        # ---- kelola posisi terbuka ----
        if pos:
            j = i; ex_week = TA._period_key(bars[j]["time"], "week")
            done = False
            if pos["side"] == "long": pos["fav"] = max(pos["fav"], high[i])
            else: pos["fav"] = min(pos["fav"], low[i])
            if not p["NOTIMESTOP"] and ex_week != pos["wk"]:  # auction baru -> tutup sisa
                _close(pos, bars[j - 1]["close"], "WEEK", trades); pos = None; done = True
            if not done and pos["side"] in ("long", "short"):
                rp = abs(pos["entry"] - pos["init_sl"])
                if pos["side"] == "long":
                    tp1_lvl = vwap[j] if TPMODE == "vwap" else pos["entry"] + TP1R * rp
                    tp2_lvl = up1[j] if TPMODE == "vwap" else pos["entry"] + TP2R * rp
                    hit_sl = low[j] <= pos["sl"]; hit_tp1 = high[j] >= tp1_lvl; hit_tp2 = high[j] >= tp2_lvl
                else:
                    tp1_lvl = vwap[j] if TPMODE == "vwap" else pos["entry"] - TP1R * rp
                    tp2_lvl = lo1[j] if TPMODE == "vwap" else pos["entry"] - TP2R * rp
                    hit_sl = high[j] >= pos["sl"]; hit_tp1 = low[j] <= tp1_lvl; hit_tp2 = low[j] <= tp2_lvl
                if hit_sl:
                    _close(pos, pos["sl"], "SL", trades); pos = None; done = True
                elif not pos["tp1"] and hit_tp1:
                    pos["tp1"] = True
                    if TP1FRAC >= 0.999:
                        _close(pos, tp1_lvl, "TP1", trades); pos = None; done = True
                    else:
                        _partial(pos, tp1_lvl, TP1FRAC)
                        if p["BE_AFTER_TP1"]: pos["sl"] = pos["entry"]
                elif pos["tp1"] and hit_tp2:
                    _close(pos, tp2_lvl, "TP2", trades); pos = None; done = True
            if pos and not p["NOTIMESTOP"] and (i - pos["i"]) >= p["MAXBARS"]:
                _close(pos, close[i], "TIME", trades); pos = None
            continue
        # ---- deteksi deviasi keluar (excess) lalu masuk lagi ----
        if low[i] < loD[i]:
            dev_lo = True; exc_lo = min(exc_lo, low[i]); out_lo += 1
        if high[i] > upD[i]:
            dev_hi = True; exc_hi = max(exc_hi, high[i]); out_hi += 1
        reenter_lo = dev_lo and close[i] >= loD[i]
        reenter_hi = dev_hi and close[i] <= upD[i]
        nofil = p["NOFILTER"]
        sigL = reenter_lo and (nofil or out_lo <= MAXOUT)  # excess vs acceptance (jika filter aktif)
        sigS = reenter_hi and (nofil or out_hi <= MAXOUT)
        if sigL:
            sl = calc_sl("long", close[i], min(exc_lo, low[i]), i)
            if sl < close[i] and regime_ok(i) and not (p["PREVFILTER"] and pwv[i] and close[i] < pwv[i]):
                pos = _open("long", close[i], sl, i, bars)
        elif sigS:
            sl = calc_sl("short", close[i], max(exc_hi, high[i]), i)
            if sl > close[i] and regime_ok(i) and not (p["PREVFILTER"] and pwv[i] and close[i] > pwv[i]):
                pos = _open("short", close[i], sl, i, bars)
        if reenter_lo:
            dev_lo = False; out_lo = 0; exc_lo = 1e18
        if reenter_hi:
            dev_hi = False; out_hi = 0; exc_hi = -1e18
    if pos:
        _close(pos, close[-1], "END", trades)
    return trades


def _open(side, entry, sl, i, bars):
    import datetime as _d
    return dict(side=side, entry=entry, sl=sl, init_sl=sl, i=i,
                wk=TA._period_key(bars[i]["time"], "week"), tp1=False, realized=0.0, partf=0.0, fav=entry,
                date=_d.datetime.fromtimestamp(bars[i]["time"], _d.timezone.utc).strftime("%Y-%m-%d"))


def _ret(side, entry, px):
    return (px / entry - 1) if side == "long" else (1 - px / entry)


def _partial(pos, px, frac):
    pos["realized"] += frac * _ret(pos["side"], pos["entry"], px)
    pos["partf"] += frac


def _close(pos, px, reason, trades):
    rem = 1.0 - pos.get("partf", 0.0)
    pos["realized"] += rem * _ret(pos["side"], pos["entry"], px)
    gross = pos["realized"]
    net = gross - 2 * FEE / 100
    risk = abs(pos["entry"] - pos["init_sl"]) / pos["entry"] if pos.get("init_sl") else abs(pos["entry"] - pos["sl"]) / pos["entry"]
    R = net / risk if risk else 0
    rp = abs(pos["entry"] - pos["init_sl"])
    fav = pos.get("fav", pos["entry"])
    mfe_R = ((fav - pos["entry"]) if pos["side"] == "long" else (pos["entry"] - fav)) / rp if rp else 0
    trades.append(dict(side=pos["side"], ret=net * 100, R=R, reason=reason, days=0,
                       bars=0, date=pos["date"], tp1=pos["tp1"], mfe_R=mfe_R))


def _open2(*a):  # placeholder (kompat)
    pass


def stats(tr):
    if not tr:
        return dict(n=0)
    rets = [t["ret"] for t in tr]; Rs = [t["R"] for t in tr]
    wins = [r for r in rets if r > 0]; gw = sum(wins); gl = -sum(r for r in rets if r <= 0)
    tp2 = sum(1 for t in tr if t["reason"] == "TP2"); sl = sum(1 for t in tr if t["reason"] == "SL")
    tp1 = sum(1 for t in tr if t["tp1"])
    return dict(n=len(tr), wr=len(wins) / len(tr) * 100, pf=(gw / gl) if gl else (99.9 if gw else 0),
                avg=sum(rets) / len(rets), expR=sum(Rs) / len(Rs), total=sum(rets),
                tp1_rate=tp1 / len(tr) * 100, tp2_rate=tp2 / len(tr) * 100, sl_rate=sl / len(tr) * 100)


def fmt(tag, s):
    if not s.get("n"):
        print(f"{tag:<12} 0 trade"); return
    print(f"{tag:<12} {s['n']:>4} tr | WR {s['wr']:>4.0f}% | PF {s['pf']:>4.2f} | exp {s['expR']:>+5.2f}R "
          f"| avg {s['avg']:>+5.2f}% | TP1 {s['tp1_rate']:>3.0f}% TP2 {s['tp2_rate']:>3.0f}% SL {s['sl_rate']:>3.0f}% | tot {s['total']:>+6.0f}%")


def report(trades, capital=10000.0, riskpct=1.0):
    """Laporan P/L. Model notional TETAP: tiap trade komit $bet=capital, P/L$=ret%×bet (linear,
    50/50 scale + fee sudah termasuk di ret). Plus metrik R (capital-agnostic) + DD."""
    if not trades:
        print("Tidak ada trade."); return
    bet = capital
    tr = sorted(trades, key=lambda t: t["date"])
    monthly = {}; pertoken = {}; reasons = {}
    gw = gl = 0.0; wins = 0; eq = capital; peak = capital; maxdd = 0.0; eq_min = capital
    for t in tr:
        pl = t["ret"] / 100.0 * bet
        eq += pl; peak = max(peak, eq); maxdd = max(maxdd, (peak - eq) / peak * 100 if peak > 0 else 0)
        eq_min = min(eq_min, eq)
        monthly.setdefault(t["date"][:7], []).append(pl)
        pertoken.setdefault(t.get("sym", "?"), []).append(pl)
        reasons.setdefault(t["reason"], []).append(t["R"])
        if pl > 0: gw += pl; wins += 1
        else: gl += -pl
    n = len(tr); net = eq - capital; totR = sum(t["R"] for t in tr); totret = sum(t["ret"] for t in tr)
    print("=" * 72)
    print(f"LAPORAN P/L — MR-VWAP AMT 30m  (notional ${bet:,.0f}/trade, fixed)")
    print("=" * 72)
    print(f"Periode      : {tr[0]['date']} → {tr[-1]['date']}  ({n} trade)")
    print(f"Win / Lose   : {wins} ({wins/n*100:.0f}%) / {n-wins} ({(n-wins)/n*100:.0f}%)")
    print(f"Gross profit : +${gw:,.0f}")
    print(f"Gross loss   : -${gl:,.0f}")
    print(f"NET P/L      : {'+' if net>=0 else '-'}${abs(net):,.0f}   (sum return {totret:+.0f}% ; total {totR:+.0f}R)")
    print(f"Profit Factor: {(gw/gl if gl else 99.9):.2f}  |  Expectancy {totR/n:+.3f}R/trade  ({net/n:+,.0f}$/trade)")
    print(f"Max Drawdown : {maxdd:.0f}%   (equity terendah ${eq_min:,.0f})")
    print("\n--- Breakdown exit (count | %trade | avg R) ---")
    for r in ("TP2", "SL", "WEEK", "TIME", "END"):
        if r in reasons:
            rr = reasons[r]; print(f"  {r:<5} {len(rr):>5}  {len(rr)/n*100:>4.0f}%   avg {sum(rr)/len(rr):+.2f}R")
    print("  (TP1 = partial 50% sebelum TP2/SL/BE; lihat avg R di atas)")
    print("\n--- P/L per token ---")
    for s in sorted(pertoken, key=lambda s: -sum(pertoken[s])):
        v = pertoken[s]; w = sum(1 for x in v if x > 0)
        print(f"  {s:<6} {len(v):>4} tr  WR {w/len(v)*100:>3.0f}%  net ${sum(v):>+11,.0f}")
    print("\n--- P/L per bulan ---")
    print("  Bulan        P/L($)   #tr    equity")
    run = capital
    for m in sorted(monthly):
        v = monthly[m]; run += sum(v)
        print(f"  {m}   {sum(v):>+10,.0f}  {len(v):>4}   ${run:>11,.0f}")
    print("=" * 72)


def mfe_report(trades):
    """Analisa MFE: apakah entry langsung balik ke SL, atau sempat ke arah VWAP dulu?"""
    n = len(trades)
    losers = [t for t in trades if t["reason"] == "SL" and not t["tp1"]]  # SL murni (tak sentuh VWAP)
    touched = [t for t in trades if t["tp1"]]                              # sempat sentuh VWAP (TP1)
    allm = [t["mfe_R"] for t in trades]
    print("=" * 64)
    print("ANALISA MFE — entry langsung SL atau sempat profit ke VWAP dulu?")
    print("=" * 64)
    print(f"Total trade            : {n}")
    print(f"Sentuh VWAP (TP1 kena) : {len(touched)} ({len(touched)/n*100:.0f}%)  ← sempat profit ke target")
    print(f"SL murni (tak ke VWAP) : {len(losers)} ({len(losers)/n*100:.0f}%)")
    print(f"MFE rata-rata SEMUA    : {sum(allm)/n:+.2f}R  (median {sorted(allm)[n//2]:+.2f}R)")
    if losers:
        m = [t["mfe_R"] for t in losers]
        print(f"\nUntuk SL-murni (n={len(losers)}): seberapa jauh ke arah VWAP sebelum balik SL?")
        print(f"  MFE rata-rata        : {sum(m)/len(m):+.2f}R  (median {sorted(m)[len(m)//2]:+.2f}R)")
        bk = [("≤0.1R (≈langsung SL)", lambda x: x <= 0.1),
              ("0.1–0.5R", lambda x: 0.1 < x <= 0.5),
              ("0.5–1.0R", lambda x: 0.5 < x <= 1.0),
              (">1.0R (hampir VWAP)", lambda x: x > 1.0)]
        for label, f in bk:
            c = sum(1 for x in m if f(x))
            print(f"    {label:<22} {c:>4} ({c/len(m)*100:>3.0f}%)")
    print("=" * 64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=""); ap.add_argument("--group", default="dat")
    ap.add_argument("--days", type=int, default=540); ap.add_argument("--quote", default="USDT")
    ap.add_argument("--split", action="store_true"); ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--perstock", action="store_true"); ap.add_argument("--report", action="store_true")
    ap.add_argument("--sweepregime", action="store_true"); ap.add_argument("--sweepsl", action="store_true")
    ap.add_argument("--mfe", action="store_true"); ap.add_argument("--sweeptp", action="store_true")
    ap.add_argument("--capital", type=float, default=10000.0); ap.add_argument("--risk", type=float, default=1.0)
    ap.add_argument("--pure", action="store_true", help="versi PERSIS spec Ben")
    for k, v in DEF.items(): ap.add_argument(f"--{k}", type=type(v), default=v)
    a = ap.parse_args()
    p = {k: getattr(a, k) for k in DEF}
    if a.pure:  # ±2σ, bias prevWVWAP, TP1->runner+BE, tanpa MAXOUT/time-stop
        p.update(DEV=2.0, PREVFILTER=1, BE_AFTER_TP1=1, NOFILTER=1, NOTIMESTOP=1)
    syms = a.symbols.split(",") if a.symbols else U.filter_universe(a.group)
    print(f"Memuat {len(syms)} token 30m × {a.days}d (Binance paginated)...")
    data = {}
    for s in syms:
        b = EX.history(s, "30m", a.days, a.quote)
        if b and len(b) > 1000:
            # patch init_sl utk R: simpan sl awal saat open
            data[s] = b
    print(f"  {len(data)} token termuat (mis. {next(iter(data))}: {len(next(iter(data.values())))} bar)\n")

    def run_all(pp):
        allt = []
        for b in data.values():
            allt += _bt_wrap(b, pp)
        return allt

    if a.sweep:
        print("=== SWEEP DEV x MAXOUT x PREVFILTER (BE=1) ===")
        for DEV in (2.0, 2.5, 3.0):
            for MO in (2, 3, 4, 6):
                for PF in (0, 1):
                    pp = dict(p, DEV=DEV, MAXOUT=MO, PREVFILTER=PF)
                    allt = run_all(pp); s = stats(allt)
                    if s.get("n", 0) >= 20:
                        a2 = sorted(allt, key=lambda t: t["date"]); mid = a2[len(a2) // 2]["date"]
                        oos = stats([t for t in a2 if t["date"] >= mid])
                        fmt(f"DEV{DEV}MO{MO}PF{PF}", s)
                        print(f"               └ OOS exp {oos.get('expR',0):+.2f}R PF {oos.get('pf',0):.2f} n{oos.get('n',0)}")
        return

    if a.sweepregime:
        base = dict(p); base.update(DEV=2.0, PREVFILTER=1, BE_AFTER_TP1=1, NOFILTER=1, NOTIMESTOP=1)
        print("=== SWEEP REGIME FILTER (di atas --pure: ±2σ, bias prevWVWAP, TP1->runner BE) ===")
        cfgs = [("off", {})]
        for ax in (18, 20, 22, 25): cfgs.append((f"adx<{ax}", dict(REGIME="adx", ADXMAX=float(ax))))
        for rt in (1.0, 1.5, 2.0): cfgs.append((f"rot<{rt}%", dict(REGIME="rot", ROTMAX=rt)))
        for ax in (20, 25):
            for rt in (1.5, 2.0): cfgs.append((f"both a{ax}r{rt}", dict(REGIME="both", ADXMAX=float(ax), ROTMAX=rt)))
        for tag, ov in cfgs:
            pp = dict(base, **ov); allt = run_all(pp); s = stats(allt)
            if s.get("n", 0) >= 15:
                a2 = sorted(allt, key=lambda t: t["date"]); mid = a2[len(a2) // 2]["date"]
                oos = stats([t for t in a2 if t["date"] >= mid])
                fmt(tag, s)
                print(f"           └ OOS PF {oos.get('pf',0):.2f} exp {oos.get('expR',0):+.2f}R n{oos.get('n',0)}")
        return

    if a.sweeptp:
        base = dict(p); base.update(DEV=2.0, PREVFILTER=1, BE_AFTER_TP1=1, NOFILTER=1, NOTIMESTOP=1, TPMODE="fixedR")
        print("=== SWEEP TP FIXED-R (di atas --pure) | SL × TP1R × scale/full ===")
        for slm, slov in (("lastlow", {}), ("pct2%", dict(SLMODE="pct", SLPCT=2.0))):
            for tp1r in (0.75, 1.0, 1.25, 1.5):
                for mode, mov in (("scale50→%.1fR" % max(tp1r + 1, 2.5), dict(TP1FRAC=0.5, TP2R=max(tp1r + 1, 2.5))),
                                  ("full@TP1", dict(TP1FRAC=1.0))):
                    pp = dict(base, TP1R=tp1r, **slov, **mov); allt = run_all(pp); s = stats(allt)
                    if s.get("n", 0) >= 15:
                        a2 = sorted(allt, key=lambda t: t["date"]); mid = a2[len(a2) // 2]["date"]
                        oos = stats([t for t in a2 if t["date"] >= mid])
                        fmt(f"{slm} R{tp1r} {mode}", s)
                        print(f"           └ OOS PF {oos.get('pf',0):.2f} exp {oos.get('expR',0):+.2f}R n{oos.get('n',0)}")
        return

    if a.sweepsl:
        base = dict(p); base.update(DEV=2.0, PREVFILTER=1, BE_AFTER_TP1=1, NOFILTER=1, NOTIMESTOP=1)
        print("=== SWEEP SL GEOMETRY (di atas --pure; TP1 VWAP->runner +1σ) ===")
        cfgs = [("lastlow(spec)", dict(SLMODE="lastlow"))]
        for k in (1.0, 1.5, 2.0): cfgs.append((f"atr×{k}", dict(SLMODE="atr", SLATR=k)))
        for k in (1.0, 1.5, 2.0, 3.0): cfgs.append((f"pct{k}%", dict(SLMODE="pct", SLPCT=k)))
        for k in (1.0, 1.5, 2.0, 3.0): cfgs.append((f"rr{k}", dict(SLMODE="rr", SLRR=k)))
        for tag, ov in cfgs:
            pp = dict(base, **ov); allt = run_all(pp); s = stats(allt)
            if s.get("n", 0) >= 15:
                a2 = sorted(allt, key=lambda t: t["date"]); mid = a2[len(a2) // 2]["date"]
                oos = stats([t for t in a2 if t["date"] >= mid])
                fmt(tag, s)
                print(f"           └ OOS PF {oos.get('pf',0):.2f} exp {oos.get('expR',0):+.2f}R n{oos.get('n',0)}")
        return

    allt = []; per = {}
    for s, b in data.items():
        t = _bt_wrap(b, p)
        for x in t: x["sym"] = s
        per[s] = t; allt += t
    print(f"=== MR-VWAP AMT 30m | DEV{p['DEV']}σ MAXOUT{p['MAXOUT']} BE{p['BE_AFTER_TP1']} "
          f"prevfilter{p['PREVFILTER']} TP1=VWAP TP2=±1σ | fee {FEE}%/sisi ===")
    fmt("FULL", stats(allt))
    if a.mfe:
        print()
        mfe_report(allt)
    if a.report:
        print()
        report(allt, a.capital, a.risk)
    if a.split:
        a2 = sorted(allt, key=lambda t: t["date"]); mid = a2[len(a2) // 2]["date"]
        fmt("IS", stats([t for t in a2 if t["date"] < mid]))
        fmt("OOS", stats([t for t in a2 if t["date"] >= mid]))
        print(f"  (batas {mid}) — per tahun:")
        yrs = {}
        for t in allt: yrs.setdefault(t["date"][:4], []).append(t)
        for y in sorted(yrs): fmt("  " + y, stats(yrs[y]))
    if a.perstock:
        print("per token:")
        for s in sorted(per, key=lambda s: -stats(per[s]).get("expR", -9)):
            if per[s]: fmt("  " + s, stats(per[s]))


def _bt_wrap(bars, p):
    """Jalankan backtest + sisipkan init_sl utk R-multiple yg benar."""
    # monkeypatch: simpan init_sl di _open via post-process tak praktis -> hitung ulang di _open
    return backtest(bars, p)


if __name__ == "__main__":
    main()
