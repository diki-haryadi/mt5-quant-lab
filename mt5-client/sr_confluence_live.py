"""sr_confluence_live.py — FORWARD-TEST live S/R konfluensi XAUUSD (tervalidasi walk-forward 6/6).
Magic 770010. Bias 1D+4H EMA50, konfluensi cluster >=3/4 TF (H2,H1,M30,M15), rejection M15,
SL di balik cluster -0.5ATR, TP=RMULT*R. 1 posisi/magic + cooldown. risk 0.5%.
Default PAPER (order_check saja). Pakai --live untuk eksekusi demo. Loop poll detik."""
import argparse, math, time, datetime as dt, bisect, subprocess, requests, json, os
from mt5_scalper import MT5Api, calc_lot
from backtest_lab import atr_series

MAGIC = 770010
STUDY_FILE = "/opt/mt5-quant/data/sr_sl_study.jsonl"
STUDY_BARS = 24   # bar M15 setelah SL utk ukur MFE (=6 jam)
NAME = "SRCONF"
TFS = ["H2", "H1", "M30", "M15"]
NEAR, CLUST, ENTRYTOL, SLBUF, MINTF, RMULT, ATRP = 1.2, 0.30, 0.5, 0.5, 3, 2.0, 14
COOLDOWN_S = 16 * 900   # 16 bar M15

def log(m): print(f"[{dt.datetime.now():%m-%d %H:%M:%S}] {m}", flush=True)

def _waenv():
    e = {}
    try:
        for ln in open("/opt/mt5-quant/waha.env"):
            ln = ln.strip()
            if "=" in ln and not ln.startswith("#"): k, v = ln.split("=", 1); e[k.strip()] = v.strip().strip('"')
    except Exception: pass
    return e

def notify(text):
    e = _waenv()
    if all(e.get(k) for k in ("WAHA_URL", "WAHA_KEY", "WA_CHATID")):
        try:
            requests.post(f"{e['WAHA_URL']}/api/sendText", headers={"X-Api-Key": e["WAHA_KEY"], "Content-Type": "application/json"},
                          json={"session": "default", "chatId": e["WA_CHATID"], "text": text}, timeout=15)
        except Exception: pass
    parts = text.split("\n", 1)
    try:
        subprocess.Popen(["/opt/wa-claude-bridge/venv/bin/python", "/opt/wa-claude-bridge/push_send.py",
                          parts[0], parts[1] if len(parts) > 1 else ""], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

def check_exits(api, sym, state):
    """deteksi posisi SR-Conf yg baru ditutup (SL/TP) via deals → notif P/L."""
    try:
        deals = api._get("/api/deals", days=1).get("items", [])
    except Exception:
        return
    seen = state.setdefault("seen_deals", set())
    for d in deals:
        if d.get("magic") != MAGIC: continue
        pr = d.get("profit", 0) or 0
        if abs(pr) < 1e-9: continue  # deal pembukaan (profit 0) → lewati
        did = d.get("ticket") or d.get("deal") or d.get("order")
        if did in seen: continue
        seen.add(did)
        if state.get("primed"):
            notify(f"{'🟢' if pr >= 0 else '🔴'} SR-Conf EXIT {sym} ${pr:+.2f}")
    state["primed"] = True

def study(api, sym):
    """SL-study: tiap trade rugi (SL), ukur MFE N bar setelahnya (satuan R) → wick-stopout vs SL valid.
    Pakai deals (entry+exit price), retroaktif & idempotent (id deal close)."""
    try:
        deals = [d for d in api._get("/api/deals", days=14).get("items", []) if d.get("magic") == MAGIC]
    except Exception:
        return
    deals.sort(key=lambda d: d.get("time", 0))
    done = set()
    if os.path.exists(STUDY_FILE):
        for ln in open(STUDY_FILE):
            try: done.add(json.loads(ln)["id"])
            except Exception: pass
    opens = []; trades = []
    for d in deals:
        if d.get("entry") == 0: opens.append(d)
        elif d.get("entry") == 1 and opens: trades.append((opens.pop(0), d))
    now = int(dt.datetime.now().timestamp()); bars = api.bars(sym, "M15", 250)
    for o, c in trades:
        cid = c.get("ticket") or c.get("deal")
        if cid in done or (c.get("profit", 0) or 0) >= 0: continue
        et = c.get("time", 0)
        if now - et < STUDY_BARS * 900: continue       # tunggu cukup bar
        side = "sell" if o.get("type") == 1 else "buy"
        entry = o.get("price"); slx = c.get("price"); R = abs(slx - entry)
        if R <= 0: continue
        post = [b for b in bars if b['time'] > et][:STUDY_BARS]
        if len(post) < STUDY_BARS: continue
        mfe = (entry - min(b['low'] for b in post)) if side == "sell" else (max(b['high'] for b in post) - entry)
        mfeR = mfe / R
        rec = dict(id=cid, exit_t=dt.datetime.fromtimestamp(et).isoformat(), side=side, entry=round(entry, 3),
                   sl=round(slx, 3), R=round(R, 3), mfe_R=round(mfeR, 2), hit_tp=mfeR >= 2.0,
                   back_to_entry=mfeR >= 0.0, profit=round(c.get('profit', 0), 2))
        with open(STUDY_FILE, "a") as f: f.write(json.dumps(rec) + "\n")
        verd = "WICK-STOPOUT (harusnya kena TP!)" if mfeR >= 2.0 else ("balik ke entry" if mfeR >= 0.0 else "SL VALID (lanjut lawan)")
        log(f"📊 SL-study {side} entry {entry:.2f} SL {slx:.2f} → MFE {mfeR:+.2f}R | {verd}")

def study_report():
    if not os.path.exists(STUDY_FILE): print("belum ada data SL-study."); return
    rows = [json.loads(l) for l in open(STUDY_FILE) if l.strip()]
    n = len(rows); wick = sum(1 for r in rows if r["hit_tp"]); back = sum(1 for r in rows if r["back_to_entry"] and not r["hit_tp"])
    valid = n - wick - back
    print(f"SL-STUDY ({n} SL): wick-stopout(MFE≥2R)={wick} ({wick*100//max(n,1)}%) | balik-ke-entry={back} | SL-valid(MFE<0)={valid}")
    print(f"  rata2 MFE {sum(r['mfe_R'] for r in rows)/max(n,1):.2f}R")
    if n and wick / n > 0.35: print("  ⚠️ wick-stopout tinggi → pertimbangkan lebarkan SL buffer (setelah cukup sampel!)")
    for r in rows[-12:]: print(f"  {r['exit_t'][:16]} {r['side']:4} MFE {r['mfe_R']:+.2f}R ${r['profit']:+.2f}")

def ema(c, p):
    n = len(c); o = [float('nan')] * n
    if n < p: return o
    k = 2 / (p + 1); s = sum(c[:p]) / p; o[p - 1] = s
    for i in range(p, n): s = c[i] * k + s * (1 - k); o[i] = s
    return o

def pivots(bars, L=4):
    n = len(bars); hi = [b['high'] for b in bars]; lo = [b['low'] for b in bars]; out = []
    for i in range(L, n - L):
        if hi[i] == max(hi[i - L:i + L + 1]): out.append(hi[i])
        if lo[i] == min(lo[i - L:i + L + 1]): out.append(lo[i])
    return sorted(out)

def cluster(levels_by_tf, price, tn, tc):
    pts = []
    for tf, arr in levels_by_tf.items():
        i = bisect.bisect_left(arr, price - tn); j = bisect.bisect_right(arr, price + tn)
        for lv in arr[i:j]: pts.append((lv, tf))
    if len(pts) < MINTF: return None
    pts.sort(); best = None
    for x in range(len(pts)):
        grp = [pts[x]]
        for y in range(x + 1, len(pts)):
            if pts[y][0] - pts[x][0] <= tc: grp.append(pts[y])
            else: break
        if len(set(g[1] for g in grp)) >= MINTF:
            ctr = sum(g[0] for g in grp) / len(grp); cand = (ctr, grp[0][0], grp[-1][0], len(set(g[1] for g in grp)))
            if best is None or abs(ctr - price) < abs(best[0] - price): best = cand
    return best

def step(api, sym, cfg, state):
    digits = cfg["digits"]
    m15 = api.bars(sym, "M15", 320); closed = m15[:-1]
    if len(closed) < 80: log("bars M15 kurang"); return
    i = len(closed) - 1; last_t = closed[i]["time"]; b = closed[i]
    if state.get("last_bar") == last_t: return
    state["last_bar"] = last_t
    atr = atr_series(closed, ATRP); a = atr[i]
    if not (a == a) or a <= 0: return
    # bias
    d1 = api.bars(sym, "D1", 80)[:-1]; h4 = api.bars(sym, "H4", 80)[:-1]
    d1e = ema([x['close'] for x in d1], 50); h4e = ema([x['close'] for x in h4], 50)
    if math.isnan(d1e[-1]) or math.isnan(h4e[-1]): return
    bd = d1[-1]['close'] > d1e[-1]; bh = h4[-1]['close'] > h4e[-1]
    bias = 1 if (bd and bh) else (-1 if (not bd and not bh) else 0)
    # levels
    lv = {"H2": pivots(api.bars(sym, "H2", 320)[:-1]), "H1": pivots(api.bars(sym, "H1", 320)[:-1]),
          "M30": pivots(api.bars(sym, "M30", 320)[:-1]), "M15": pivots(closed)}
    price = b['close']; cl = cluster(lv, price, NEAR * a, CLUST * a)
    score = cl[3] if cl else 0
    bias_s = {1: "BULL", -1: "BEAR", 0: "netral"}[bias]
    clstr = f"{cl[0]:.{digits}f}({cl[3]}TF)" if cl else "none"
    log(f"bar {dt.datetime.fromtimestamp(last_t):%m-%d %H:%M} close={price:.{digits}f} ATR={a:.{digits}f} bias={bias_s} cluster={clstr}")
    if bias == 0 or cl is None: return
    ctr, clo, chi, _ = cl
    if abs(ctr - price) > ENTRYTOL * a: return
    if last_t - state.get("last_entry_t", 0) < COOLDOWN_S:
        log("  cooldown aktif, skip"); return
    rng = b['high'] - b['low']
    if rng <= 0: return
    if bias == 1:
        lw = min(b['open'], b['close']) - b['low']
        if not ((b['low'] <= chi + ENTRYTOL * a) and (b['close'] > b['open']) and (b['close'] > ctr)): return
        side = "buy"; sl_lvl = clo - SLBUF * a
    else:
        if not ((b['high'] >= clo - ENTRYTOL * a) and (b['close'] < b['open']) and (b['close'] < ctr)): return
        side = "sell"; sl_lvl = chi + SLBUF * a
    # cek posisi existing
    poss = [p for p in api.positions(sym) if p.get("magic") == MAGIC]
    if poss: log(f"  ✗ sudah ada {len(poss)} posisi {NAME}"); return
    tick = api.tick(sym); entry = tick["ask"] if side == "buy" else tick["bid"]
    risk = abs(entry - sl_lvl)
    if risk <= 0: return
    sl = round(sl_lvl, digits); tp = round(entry + RMULT * risk if side == "buy" else entry - RMULT * risk, digits)
    acc = api.account(); lot, est = calc_lot(acc["balance"] * cfg["risk"] / 100, risk, cfg["sinfo"])
    if est > acc["balance"] * 6.0 / 100: log("  ✗ risk>cap"); return
    log(f"➤ SINYAL {side.upper()} {sym} @ {entry:.{digits}f} | SL {sl} TP {tp} | konfluensi {score}TF | lot {lot} risk ${est:.2f}")
    if not cfg["live"]:
        log("  [PAPER] tidak dikirim (pakai --live untuk demo eksekusi)."); state["last_entry_t"] = last_t; return
    try:
        out = api._post("/api/orders/send", dict(symbol=sym, side=side, volume=lot, sl=sl, tp=tp,
                        deviation=20, magic=MAGIC, comment=NAME))
        res = out.get("result", {})
        log(f"  ✓ LIVE retcode={res.get('retcode')} deal={res.get('deal')} price={res.get('price')}")
        state["last_entry_t"] = last_t
        notify(f"🟢 SR-Conf ENTRY {side.upper()} {sym} @ {res.get('price', entry):.{digits}f}\n"
               f"SL {sl} · TP {tp} · konfluensi {score}TF · lot {lot} · risk ${est:.2f}")
    except Exception as e:
        log(f"  ✗ order GAGAL: {e}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://192.168.0.111:8000")
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--risk", type=float, default=0.5)
    p.add_argument("--poll", type=int, default=30)
    p.add_argument("--live", action="store_true")
    p.add_argument("--once", action="store_true")
    p.add_argument("--study", action="store_true", help="cetak ringkasan SL-study lalu keluar")
    args = p.parse_args()
    if args.study: study_report(); return
    api = MT5Api(args.api, timeout=60)
    sinfo = api.symbol_info(args.symbol)
    cfg = dict(symbol=args.symbol, risk=args.risk, live=args.live, digits=sinfo["digits"], sinfo=sinfo)
    state = {}
    log(f"SR-Confluence forward-test | {args.symbol} M15 | magic {MAGIC} | {'🔴 LIVE demo' if args.live else '🟢 PAPER'} | risk {args.risk}%")
    if args.once:
        step(api, args.symbol, cfg, state); return
    loops = 0
    while True:
        try:
            check_exits(api, args.symbol, state)
            step(api, args.symbol, cfg, state)
            if loops % 10 == 0: study(api, args.symbol)   # cek SL-study tiap ~10 loop
        except Exception as e: log(f"err {type(e).__name__}: {str(e)[:100]}")
        loops += 1
        time.sleep(args.poll)

if __name__ == "__main__":
    main()
