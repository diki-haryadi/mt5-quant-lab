"""
market_watch.py — engine crypto market watch (Binance + Bybit + OKX).
Tarik watchlist (LAYER1 + PANTERA) paralel lintas-3-exchange, hitung indikator teknikal,
tampilkan tabel watchlist + skor sinyal komposit + cek spread antar-exchange (arbitrase).

Usage:
  python3 market_watch.py                         # semua universe, TF 1d
  python3 market_watch.py --group dat --tf 4h     # subset Pantera-DAT, TF 4h
  python3 market_watch.py --group l1 --sort pct   # Layer-1, urut %24h
  python3 market_watch.py --signals               # hanya yg sinyal kuat / ekstrem
  python3 market_watch.py --arb                    # spread harga antar-exchange
  python3 market_watch.py --full BTC               # dump SEMUA indikator 1 simbol
  group: all|l1|pantera|dat   tf: 1m,5m,15m,1h,4h,1d   sort: score|pct|vol|rsi|sym
"""
from __future__ import annotations
import argparse
import datetime
from concurrent.futures import ThreadPoolExecutor

import exchanges as EX
import indicators as TA
import universe as U

PRIMARY = ("binance", "bybit", "okx", "hyperliquid")
ARB_EX = ("binance", "bybit", "okx", "hyperliquid")


def score(ind: dict) -> tuple[int, str]:
    """Skor sinyal komposit -6..+6 dari beberapa indikator independen."""
    if not ind: return 0, "?"
    c = ind.get("close"); s = 0
    def g(k): return ind.get(k)
    if c and g("ema50") and c > g("ema50"): s += 1
    elif c and g("ema50"): s -= 1
    if c and g("ema200") and c > g("ema200"): s += 1
    elif c and g("ema200"): s -= 1
    r = g("rsi")
    if r is not None:
        if 50 <= r <= 70: s += 1
        elif r > 70: s -= 1
        elif r < 30: s += 1            # oversold = potensi bounce
        elif r < 50: s -= 1
    if g("macd_hist") is not None: s += 1 if g("macd_hist") > 0 else -1
    if g("adx") and g("pdi") is not None and g("ndi") is not None and g("adx") > 20:
        s += 1 if g("pdi") > g("ndi") else -1
    if g("supertrend_dir") is not None: s += 1 if g("supertrend_dir") > 0 else -1
    label = ("🟢🟢 STRONG-BULL" if s >= 4 else "🟢 bull" if s >= 2 else
             "🔴🔴 STRONG-BEAR" if s <= -4 else "🔴 bear" if s <= -2 else "⚪ netral")
    return s, label


def trend_arrows(ind: dict) -> str:
    c = ind.get("close")
    a = "↑" if (c and ind.get("ema50") and c > ind["ema50"]) else "↓"
    b = "↑" if (c and ind.get("ema200") and c > ind["ema200"]) else "↓"
    return a + b


def fetch_row(base, tf, quote):
    bars, ex = EX.best_klines(base, tf, 300, PRIMARY, quote)
    ind = TA.compute_all(bars) if bars else {}
    # ticker agregat lintas exchange (volume + harga utk arb)
    vol_q = 0.0; px = {}; pct = None
    for n, cl in EX.all_clients(quote).items():
        t = cl.ticker(base)
        if t:
            vol_q += t["vol_quote"]; px[n] = t["last"]
            if pct is None: pct = t["pct24"]
    sc, lab = score(ind)
    last = ind.get("close") or (list(px.values())[0] if px else None)
    return dict(base=base, tags=U.tags(base), ex=ex, last=last, pct=pct, vol_q=vol_q,
                rsi=ind.get("rsi"), adx=ind.get("adx"), trend=trend_arrows(ind),
                macdh=ind.get("macd_hist"), st_dir=ind.get("supertrend_dir"),
                natr=ind.get("natr"), score=sc, label=lab, px=px, ind=ind)


def build(bases, tf, quote, workers=12):
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as exr:
        for r in exr.map(lambda b: fetch_row(b, tf, quote), bases):
            rows.append(r)
    return rows


def fmt_vol(v):
    if not v: return "-"
    for u, d in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if v >= d: return f"{v/d:.1f}{u}"
    return f"{v:.0f}"


def print_table(rows, sort="score"):
    keyf = {"score": lambda r: -(r["score"] or -9), "pct": lambda r: -(r["pct"] or -999),
            "vol": lambda r: -(r["vol_q"] or 0), "rsi": lambda r: -(r["rsi"] or 0),
            "sym": lambda r: r["base"]}.get(sort, lambda r: -(r["score"] or -9))
    rows = sorted(rows, key=keyf)
    print(f"{'SYM':<7}{'TAG':<10}{'PRICE':>13}{'%24h':>8}{'VOL$':>9}{'RSI':>6}"
          f"{'ADX':>6}{'TR':>4}{'MACD':>6}{'ST':>4}{'NATR':>6}{'SCORE':>7}  SINYAL")
    print("-" * 104)
    for r in rows:
        price = (f"{r['last']:,.4f}" if r['last'] and r['last'] < 10 else f"{r['last']:,.2f}") if r['last'] else "-"
        macd = ("+" if (r['macdh'] or 0) > 0 else "-") if r['macdh'] is not None else "·"
        st = ("↑" if (r['st_dir'] or 0) > 0 else "↓") if r['st_dir'] is not None else "·"
        pct = ("%+.1f" % r['pct']) if r['pct'] is not None else "-"
        rsi = ("%.0f" % r['rsi']) if r['rsi'] is not None else "-"
        adx = ("%.0f" % r['adx']) if r['adx'] is not None else "-"
        natr = ("%.1f" % r['natr']) if r['natr'] is not None else "-"
        sc = ("%+d" % r['score']) if r['score'] is not None else "-"
        tg = ",".join(r['tags'])
        print(f"{r['base']:<7}{tg:<10}{price:>13}{pct:>8}{fmt_vol(r['vol_q']):>9}"
              f"{rsi:>6}{adx:>6}{r['trend']:>4}{macd:>6}{st:>4}{natr:>6}{sc:>7}  {r['label']}")


def print_arb(rows):
    print(f"{'SYM':<7}{'binance':>13}{'bybit':>13}{'okx':>13}{'hyperliq':>13}{'SPREAD%':>9}  arah (perp HL vs spot)")
    print("-" * 84)
    for r in sorted(rows, key=lambda r: -(_spread(r['px']) or 0)):
        px = r['px']
        if len(px) < 2: continue
        sp = _spread(px); lo = min(px, key=px.get); hi = max(px, key=px.get)
        cells = "".join(("%13.4f" % px[n]) if px.get(n) else f"{'-':>13}" for n in ARB_EX)
        print(f"{r['base']:<7}{cells}{sp:>8.2f}%  beli@{lo}→jual@{hi}")


def _spread(px):
    if len(px) < 2: return None
    lo, hi = min(px.values()), max(px.values())
    return (hi / lo - 1) * 100 if lo else None


def show_book(base, quote, depth=15):
    cl = EX.all_clients(quote)
    print(f"=== ORDERBOOK {base} (depth {depth}) ===")
    for n in ("binance", "bybit", "okx", "hyperliquid"):
        ob = cl[n].orderbook(base, depth)
        if not ob or not ob["bids"] or not ob["asks"]:
            print(f"\n[{n}] N/A"); continue
        bids, asks = ob["bids"][:depth], ob["asks"][:depth]
        bidv = sum(q for _, q in bids); askv = sum(q for _, q in asks)
        imb = bidv / (bidv + askv) * 100 if (bidv + askv) else 50
        spread = (asks[0][0] / bids[0][0] - 1) * 100
        bias = "🟢 beli" if imb > 55 else "🔴 jual" if imb < 45 else "⚪ seimbang"
        print(f"\n[{n}] spread {spread:.3f}% | imbalance {imb:.0f}% {bias} (bidVol {bidv:.3f} / askVol {askv:.3f})")
        print(f"  {'BID':>16}{'size':>14}    |  {'ASK':>16}{'size':>14}")
        for i in range(min(10, max(len(bids), len(asks)))):
            bs = ("%16.6f%14.4f" % bids[i]) if i < len(bids) else " " * 30
            ak = ("%16.6f%14.4f" % asks[i]) if i < len(asks) else ""
            print(f"  {bs}    |  {ak}")


def show_trades(base, quote, limit=25):
    cl = EX.all_clients(quote); allt = []
    for n in ("binance", "bybit", "okx"):
        t = cl[n].trades(base, 60)
        if t:
            for x in t: x["ex"] = n
            allt += t
    if not allt:
        print(f"running-trade {base}: N/A"); return
    allt.sort(key=lambda x: -x["time"])
    buyv = sum(x["qty"] for x in allt if x["side"] == "buy")
    sellv = sum(x["qty"] for x in allt if x["side"] == "sell"); tot = buyv + sellv or 1
    print(f"=== RUNNING TRADE {base} (gabungan spot Binance+Bybit+OKX, {len(allt)} trade) ===")
    print(f"agresif BUY {buyv:.3f} ({buyv/tot*100:.0f}%) vs SELL {sellv:.3f} ({sellv/tot*100:.0f}%)\n")
    for x in allt[:limit]:
        ts = datetime.datetime.fromtimestamp(x["time"]).strftime("%H:%M:%S")
        arrow = "🟢" if x["side"] == "buy" else "🔴"
        print(f"  {ts} {arrow} {x['side']:>4} {x['price']:>15.6f} x {x['qty']:>13.4f}  [{x['ex']}]")


def show_vwap(base, tf, quote, anchor="week"):
    bars, ex = EX.best_klines(base, tf, 300, PRIMARY, quote)
    if not bars:
        print(f"VWAP {base}: no data"); return
    vw = TA.vwap_anchored(bars, anchor=anchor, src="hlc3", bands=(1.0, 2.0, 3.0))
    c = bars[-1]["close"]; v = vw["vwap"][-1]
    print(f"=== VWAP anchored ({anchor}, src hlc3, stdev bands) {base} | {ex} | TF {tf} ===")
    if not v:
        print("  data kurang"); return
    print(f"  close   {c:,.6g}")
    print(f"  VWAP    {v:,.6g}   (dist {(c/v-1)*100:+.2f}%)")
    for m in (1.0, 2.0, 3.0):
        u = vw["bands"][m][0][-1]; l = vw["bands"][m][1][-1]
        mark = ""
        if u and c >= u: mark = "  ← harga ≥ upper"
        elif l and c <= l: mark = "  ← harga ≤ lower"
        print(f"  +{m:.0f}σ {u:,.6g}   -{m:.0f}σ {l:,.6g}{mark}")
    zone = TA.compute_all(bars).get("vwap_zone", "?")
    print(f"  zona: {zone}")


def show_deriv(bases, quote, workers=12):
    def row(base):
        cl = EX.all_clients(quote); d = {}
        for n in ("binance", "bybit", "okx", "hyperliquid"):
            r = cl[n].derivatives(base)
            if r: d[n] = r
        return base, d
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as exr:
        for base, d in exr.map(row, bases):
            if d: rows.append((base, d))
    rows.sort(key=lambda r: -sum(v["oi_usd"] for v in r[1].values()))
    print(f"=== OPEN INTEREST + FUNDING (perp) | {len(rows)} token ===")
    print(f"{'SYM':<7}{'OI bin':>11}{'OI byb':>11}{'OI okx':>11}{'OI hl':>11}{'OI TOTAL$':>12}{'fund%avg':>10}")
    print("-" * 73)
    for base, d in rows:
        tot = sum(v["oi_usd"] for v in d.values())
        fund = [v["funding"] for v in d.values() if v.get("funding") is not None]
        favg = sum(fund) / len(fund) * 100 if fund else 0.0
        def cell(n): return fmt_vol(d[n]["oi_usd"]) if n in d else "-"
        print(f"{base:<7}{cell('binance'):>11}{cell('bybit'):>11}{cell('okx'):>11}"
              f"{cell('hyperliquid'):>11}{fmt_vol(tot):>12}{('%+.4f' % favg):>10}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="all"); ap.add_argument("--tf", default="1d")
    ap.add_argument("--quote", default="USDT"); ap.add_argument("--sort", default="score")
    ap.add_argument("--signals", action="store_true"); ap.add_argument("--arb", action="store_true")
    ap.add_argument("--full", default=""); ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--book", default=""); ap.add_argument("--trades", default=""); ap.add_argument("--deriv", action="store_true")
    ap.add_argument("--vwap", default=""); ap.add_argument("--anchor", default="week")
    a = ap.parse_args()

    if a.book:
        show_book(a.book.upper(), a.quote); return
    if a.trades:
        show_trades(a.trades.upper(), a.quote); return
    if a.vwap:
        show_vwap(a.vwap.upper(), a.tf, a.quote, a.anchor); return

    if a.full:
        base = a.full.upper(); bars, ex = EX.best_klines(base, a.tf, 300, PRIMARY, a.quote)
        if not bars: print(f"{base}: no data"); return
        ind = TA.compute_all(bars); sc, lab = score(ind)
        print(f"=== {base} ({U.NAMES.get(base, base)}) | {ex} | TF {a.tf} | SKOR {sc:+d} {lab} ===")
        for k, v in ind.items():
            print(f"  {k:18} {v:,.6f}" if isinstance(v, float) else f"  {k:18} {v}")
        return

    bases = U.filter_universe(a.group)
    if a.deriv:
        show_deriv(bases, a.quote, a.workers); return
    print(f"Crypto Market Watch | group={a.group} ({len(bases)} token) | TF {a.tf} | quote {a.quote} | "
          f"Binance+Bybit+OKX+Hyperliquid")
    print("Mengambil data paralel...\n")
    rows = build(bases, a.tf, a.quote, a.workers)
    rows = [r for r in rows if r["last"]]

    if a.arb:
        print_arb(rows); return
    if a.signals:
        rows = [r for r in rows if abs(r["score"] or 0) >= 3 or (r["rsi"] is not None and (r["rsi"] < 30 or r["rsi"] > 75))]
        print(f"[FILTER sinyal kuat / RSI ekstrem: {len(rows)} token]")
    print_table(rows, a.sort)
    # ringkasan
    bull = sum(1 for r in rows if (r["score"] or 0) >= 2); bear = sum(1 for r in rows if (r["score"] or 0) <= -2)
    print("-" * 104)
    print(f"Ringkas: {len(rows)} token | 🟢 bull {bull} | 🔴 bear {bear} | ⚪ netral {len(rows)-bull-bear}")


if __name__ == "__main__":
    main()
