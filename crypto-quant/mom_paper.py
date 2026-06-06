"""
mom_paper.py — FORWARD-TEST PAPER engine momentum breakout di FUTURES/PERPS.
Long & short keduanya dari endpoint futures (history_fut). Idempoten: aman dipanggil tiap close 4h
(systemd timer) — kelola ulang dari entry tiap run (tahan run yg terlewat).

Sizing/risk: tiap trade risiko RISKPCT% equity; size_usd = risk$ / (jarak SL fraksi); qty = size/entry.
Entry: fresh Donchian(DCN) breakout + filter EMA(EMAFILT), 1 posisi/simbol.
Stop : ATR(ATRLEN)×ATRMULT chandelier trailing + exit Donchian(DCX) lawan.
State: data/mom_paper_state.json (equity, posisi, bar terakhir di-aksi). Log: data/mom_paper.jsonl.
Notif WA best-effort (waha.env, hanya jalan di CT). Funding diabaikan di paper (terbukti ~negligible).

Usage:
  python3 mom_paper.py --group l1 --tf 4h            # 1 siklus (entry/manage/log/WA)
  python3 mom_paper.py --status                       # tampilkan state saja
"""
from __future__ import annotations
import argparse, json, os, datetime, subprocess, requests
from concurrent.futures import ThreadPoolExecutor
import exchanges as EX
import indicators as TA
import universe as U

DIR = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(DIR, "data"); os.makedirs(DATA, exist_ok=True)
STATE = os.path.join(DATA, "mom_paper_state.json"); LOG = os.path.join(DATA, "mom_paper.jsonl")
P = dict(DCN=30, DCX=10, ATRMULT=3.0, ATRLEN=14, EMAFILT=200)
RISKPCT = 1.0; START = 10000.0


def load():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"equity": START, "positions": {}, "acted": {}, "started": _now()}


def save(s): json.dump(s, open(STATE, "w"), indent=2)
def _now(): return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
def logrow(d):
    with open(LOG, "a") as f: f.write(json.dumps(d) + "\n")


def _waenv():
    e = {}
    for path in ("/opt/mt5-quant/waha.env", os.path.join(DIR, "waha.env")):
        if os.path.exists(path):
            for ln in open(path):
                if "=" in ln and not ln.strip().startswith("#"):
                    k, v = ln.strip().split("=", 1); e[k] = v.strip().strip('"')
            break
    return e
def notify(text):
    e = _waenv()
    if all(e.get(k) for k in ("WAHA_URL", "WAHA_KEY", "WA_CHATID")):
        try: requests.post(f"{e['WAHA_URL']}/api/sendText", headers={"X-Api-Key": e["WAHA_KEY"]},
                           json={"session": "default", "chatId": e["WA_CHATID"], "text": text}, timeout=15)
        except Exception: pass


def manage(closed, pos, p):
    """Simulasi trail dari entry s/d bar terakhir tertutup. Return (exit_price, reason) | (None, cur_stop)."""
    times = [b["time"] for b in closed]
    if pos["entry_time"] not in times: return (None, pos["stop"])
    e = times.index(pos["entry_time"])
    high = [b["high"] for b in closed]; low = [b["low"] for b in closed]; close = [b["close"] for b in closed]
    atr = TA.atr(closed, int(p["ATRLEN"])); M = p["ATRMULT"]; DCX = int(p["DCX"])
    stop = pos["init_stop"]; ext = high[e] if pos["side"] == "long" else low[e]
    for j in range(e + 1, len(closed)):
        a = atr[j]
        if pos["side"] == "long":
            if low[j] <= stop: return (stop, "STOP")
            if j >= DCX and close[j] < min(low[j - DCX:j]): return (close[j], "DCEXIT")
            ext = max(ext, high[j])
            if a: stop = max(stop, ext - M * a)
        else:
            if high[j] >= stop: return (stop, "STOP")
            if j >= DCX and close[j] > max(high[j - DCX:j]): return (close[j], "DCEXIT")
            ext = min(ext, low[j])
            if a: stop = min(stop, ext + M * a)
    return (None, stop)


def scan(base, tf, quote, p):
    bars = EX.history_fut(base, tf, max(80, int(p["EMAFILT"]) // 4 + 50), quote)
    if not bars or len(bars) < int(p["EMAFILT"]) + 35: return base, None
    return base, bars[:-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=""); ap.add_argument("--group", default="l1")
    ap.add_argument("--tf", default="4h"); ap.add_argument("--quote", default="USDT")
    ap.add_argument("--risk", type=float, default=RISKPCT); ap.add_argument("--wa", action="store_true")
    ap.add_argument("--status", action="store_true"); ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    s = load()
    if a.status:
        print(json.dumps(s, indent=2)); return
    syms = a.symbols.split(",") if a.symbols else U.filter_universe(a.group)
    kl = {}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for base, c in ex.map(lambda b: scan(b, a.tf, a.quote, P), syms):
            if c: kl[base] = c
    events = []
    # 1) kelola posisi terbuka
    for sym in list(s["positions"]):
        if sym not in kl: continue
        pos = s["positions"][sym]; closed = kl[sym]
        ex_px, info = manage(closed, pos, P)
        if ex_px is not None:
            pl = pos["qty"] * (ex_px - pos["entry"]) * (1 if pos["side"] == "long" else -1)
            s["equity"] += pl
            row = dict(t=_now(), ev="EXIT", sym=sym, side=pos["side"], entry=pos["entry"],
                       exit=round(ex_px, 6), reason=info, pl=round(pl, 2), R=round(pl / pos["risk_usd"], 2) if pos["risk_usd"] else 0,
                       equity=round(s["equity"], 2))
            logrow(row); events.append(f"{'🟢' if pl>=0 else '🔴'} EXIT {sym} {pos['side']} {info} P/L ${pl:+.0f} ({row['R']:+.2f}R)")
            del s["positions"][sym]
        else:
            pos["stop"] = round(info, 6)
    # 2) entry baru (fresh breakout)
    for sym, closed in kl.items():
        if sym in s["positions"]: continue
        i = len(closed) - 1; bt = closed[i]["time"]
        if s["acted"].get(sym) == bt: continue
        close = [b["close"] for b in closed]; high = [b["high"] for b in closed]; low = [b["low"] for b in closed]
        ema = TA.ema(close, int(P["EMAFILT"])); atr = TA.atr(closed, int(P["ATRLEN"]))
        if ema[i] is None or not atr[i]: continue
        DCN = int(P["DCN"]); M = P["ATRMULT"]; c = close[i]; aatr = atr[i]
        dch = max(high[i - DCN:i]); dcl = min(low[i - DCN:i])
        dch_p = max(high[i - 1 - DCN:i - 1]); dcl_p = min(low[i - 1 - DCN:i - 1])
        side = stop = None
        if c > dch and c > ema[i] and close[i - 1] <= dch_p: side, stop = "long", c - M * aatr
        elif c < dcl and c < ema[i] and close[i - 1] >= dcl_p: side, stop = "short", c + M * aatr
        if not side: continue
        risk_usd = s["equity"] * a.risk / 100.0; sl_dist = abs(c - stop)
        qty = risk_usd / sl_dist if sl_dist else 0
        if qty <= 0: continue
        s["positions"][sym] = dict(side=side, entry=c, init_stop=stop, stop=round(stop, 6),
                                   entry_time=bt, qty=qty, risk_usd=risk_usd,
                                   opened=_now())
        s["acted"][sym] = bt
        row = dict(t=_now(), ev="ENTRY", sym=sym, side=side, entry=round(c, 6), stop=round(stop, 6),
                   risk_usd=round(risk_usd, 2), qty=round(qty, 6))
        logrow(row); events.append(f"🆕 ENTRY {side.upper()} {sym} @ {c:.4g} SL {stop:.4g} risk ${risk_usd:.0f}")
    save(s)
    # ringkasan
    op = s["positions"]; flo9 = 0.0; lines = []; snap_open = []
    for sym, pos in op.items():
        c = kl[sym][-1]["close"] if sym in kl else pos["entry"]
        upl = pos["qty"] * (c - pos["entry"]) * (1 if pos["side"] == "long" else -1); flo9 += upl
        lines.append(f"  {sym} {pos['side']} @{pos['entry']:.4g} SL {pos['stop']:.4g} uPL ${upl:+.0f}")
        snap_open.append(dict(sym=sym, side=pos["side"], entry=pos["entry"], stop=pos["stop"],
                              price=round(c, 6), qty=round(pos["qty"], 6), uPL=round(upl, 2),
                              uR=round(upl / pos["risk_usd"], 2) if pos.get("risk_usd") else 0, opened=pos.get("opened")))
    # snapshot utk bridge/app
    closed = []
    if os.path.exists(LOG):
        for ln in open(LOG).read().splitlines()[-200:]:
            try:
                r = json.loads(ln)
                if r.get("ev") == "EXIT": closed.append(r)
            except Exception: pass
    snap = dict(updated=_now(), tf=a.tf, equity=round(s["equity"], 2), start=START,
                roi_pct=round((s["equity"] / START - 1) * 100, 2), float_upl=round(flo9, 2),
                open=snap_open, closed_recent=closed[-12:][::-1],
                wins=sum(1 for r in closed if r.get("pl", 0) > 0), losses=sum(1 for r in closed if r.get("pl", 0) <= 0))
    json.dump(snap, open(os.path.join(DATA, "crypto_snapshot.json"), "w"), indent=2)
    head = f"📈 MOM-PAPER {a.tf} | equity ${s['equity']:,.0f} | open {len(op)} (float ${flo9:+.0f})"
    print(head)
    for e in events: print("  " + e)
    for ln in lines: print(ln)
    if a.wa and events:  # WA hanya saat ada entry/exit (hindari spam tiap jam)
        notify(head + "\n" + "\n".join(events) + ("\n" + "\n".join(lines) if lines else ""))


if __name__ == "__main__":
    main()
