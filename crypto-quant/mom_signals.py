"""
mom_signals.py — Live signal scanner strategi MOMENTUM BREAKOUT di FUTURES/PERPS.
Sumber data: Binance USDT-M futures (history_fut) — LONG & SHORT keduanya dari endpoint futures.
Config tervalidasi: Donchian(DCN) breakout + EMA(EMAFILT) filter + ATR(ATRLEN)×ATRMULT stop.

Untuk tiap token: ambil klines futures TF, hitung state bar terakhir TERTUTUP:
  LONG  bila close > Donchian-high(DCN prior) DAN close > EMA200
  SHORT bila close < Donchian-low(DCN prior)  DAN close < EMA200
  'FRESH' bila breakout baru terjadi di bar terakhir (bar sebelumnya belum tembus).
Output: side, entry, SL (entry∓ATRMULT×ATR), risk%, jarak ke channel, funding% (konteks perp).

Usage:
  python3 mom_signals.py --group l1 --tf 4h           # semua sinyal aktif
  python3 mom_signals.py --symbols BTC,ETH,SOL --tf 4h
  python3 mom_signals.py --fresh                       # hanya breakout BARU
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import exchanges as EX
import indicators as TA
import universe as U

DEF = dict(DCN=30, ATRMULT=3.0, ATRLEN=14, EMAFILT=200)


def scan_one(base, tf, quote, p):
    bars = EX.history_fut(base, tf, max(80, int(p["EMAFILT"]) // 4 + 40), quote)  # cukup utk EMA200
    if not bars or len(bars) < int(p["EMAFILT"]) + 35:
        return None
    closed = bars[:-1]  # buang bar berjalan
    n = len(closed); i = n - 1
    close = [b["close"] for b in closed]; high = [b["high"] for b in closed]; low = [b["low"] for b in closed]
    ema = TA.ema(close, int(p["EMAFILT"])); atr = TA.atr(closed, int(p["ATRLEN"]))
    if ema[i] is None or atr[i] is None or atr[i] <= 0:
        return None
    DCN = int(p["DCN"]); M = p["ATRMULT"]
    dch = max(high[i - DCN:i]); dcl = min(low[i - DCN:i])
    dch_prev = max(high[i - 1 - DCN:i - 1]); dcl_prev = min(low[i - 1 - DCN:i - 1])
    c = close[i]; a = atr[i]
    side = None
    if c > dch and c > ema[i]:
        side = "LONG"; stop = c - M * a; fresh = close[i - 1] <= dch_prev
    elif c < dcl and c < ema[i]:
        side = "SHORT"; stop = c + M * a; fresh = close[i - 1] >= dcl_prev
    else:
        return dict(base=base, side="-", price=c, trend=("up" if c > ema[i] else "dn"),
                    dist_up=(dch / c - 1) * 100, dist_dn=(1 - dcl / c) * 100)
    risk = abs(c - stop) / c * 100
    fr = None
    try:
        d = EX.Binance(quote).derivatives(base)
        fr = d["funding"] * 100 if d else None
    except Exception:
        pass
    return dict(base=base, side=side, price=c, stop=stop, risk=risk, fresh=fresh,
                trend=("up" if c > ema[i] else "dn"), funding=fr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=""); ap.add_argument("--group", default="l1")
    ap.add_argument("--tf", default="4h"); ap.add_argument("--quote", default="USDT")
    ap.add_argument("--fresh", action="store_true"); ap.add_argument("--workers", type=int, default=8)
    for k, v in DEF.items(): ap.add_argument(f"--{k}", type=type(v), default=v)
    a = ap.parse_args()
    p = {k: getattr(a, k) for k in DEF}
    syms = a.symbols.split(",") if a.symbols else U.filter_universe(a.group)
    print(f"Scan MOMENTUM (FUTURES) | {len(syms)} token | {a.tf} | DC{p['DCN']}/ATR{p['ATRMULT']}/EMA{p['EMAFILT']}")
    print("Mengambil futures klines...\n")
    rows = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(lambda b: scan_one(b, a.tf, a.quote, p), syms):
            if r: rows.append(r)
    sigs = [r for r in rows if r["side"] != "-"]
    if a.fresh: sigs = [r for r in sigs if r.get("fresh")]
    sigs.sort(key=lambda r: (r["side"], -r.get("risk", 0)))
    print(f"=== SINYAL AKTIF ({len(sigs)}) ===")
    if sigs:
        print(f"{'SYM':<7}{'SIDE':<6}{'FRESH':<7}{'PRICE':>13}{'STOP':>13}{'risk%':>7}{'fund%':>8}")
        for r in sigs:
            pr = f"{r['price']:,.4f}" if r['price'] < 10 else f"{r['price']:,.2f}"
            st = f"{r['stop']:,.4f}" if r['stop'] < 10 else f"{r['stop']:,.2f}"
            fr = ("%+.3f" % r['funding']) if r.get("funding") is not None else "-"
            print(f"{r['base']:<7}{r['side']:<6}{('NEW' if r.get('fresh') else ''):<7}{pr:>13}{st:>13}{r['risk']:>6.1f}%{fr:>8}")
    flat = [r for r in rows if r["side"] == "-"]
    up = sum(1 for r in flat if r["trend"] == "up"); dn = len(flat) - up
    print(f"\nTanpa sinyal: {len(flat)} (trend up {up} / dn {dn}) | total dipindai {len(rows)}")
    longs = sum(1 for r in sigs if r['side'] == 'LONG'); shorts = len(sigs) - longs
    print(f"Sinyal: LONG {longs} · SHORT {shorts}  → bias pasar {'LONG' if longs>shorts else 'SHORT' if shorts>longs else 'netral'}")


if __name__ == "__main__":
    main()
