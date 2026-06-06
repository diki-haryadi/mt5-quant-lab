"""sr_mtf_live.py — FORWARD-TEST live S/R konfluensi M5 (jalan-tengah, tervalidasi 6/6).
Magic 770011. Bias M30+M15 EMA50 (searah), konfluensi >=3/{H1,M30,M15,M10}, entry/rejection M5,
SL balik cluster -0.5ATR(M5), TP=RMULT*R. 1 posisi/magic + cooldown. risk 0.5%. notif WA+push + SL-study."""
import argparse, math, time, datetime as dt, bisect, subprocess, requests, json, os
from mt5_scalper import MT5Api, calc_lot
from backtest_lab import atr_series

MAGIC, NAME, ENTRY = 770011, "SRCONF5", "M5"
BIAS = ["M30", "M15"]; CONF = ["H1", "M30", "M15", "M10"]
NEAR, CLUST, ENTRYTOL, SLBUF, MINTF, RMULT, ATRP = 1.2, 0.30, 0.5, 0.5, 3, 2.0, 14
COOLDOWN_S = 12 * 300   # 12 bar M5 = 1 jam
STUDY_FILE = "/opt/mt5-quant/data/sr5_sl_study.jsonl"; STUDY_BARS = 24

def log(m): print(f"[{dt.datetime.now():%m-%d %H:%M:%S}] {m}", flush=True)
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
def cluster(lv, price, tn, tc):
    pts = []
    for tf, arr in lv.items():
        i = bisect.bisect_left(arr, price - tn); j = bisect.bisect_right(arr, price + tn)
        for x in arr[i:j]: pts.append((x, tf))
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
        try: requests.post(f"{e['WAHA_URL']}/api/sendText", headers={"X-Api-Key": e["WAHA_KEY"], "Content-Type": "application/json"},
                           json={"session": "default", "chatId": e["WA_CHATID"], "text": text}, timeout=15)
        except Exception: pass
    parts = text.split("\n", 1)
    try: subprocess.Popen(["/opt/wa-claude-bridge/venv/bin/python", "/opt/wa-claude-bridge/push_send.py",
                          parts[0], parts[1] if len(parts) > 1 else ""], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

def check_exits(api, sym, state):
    try: deals = api._get("/api/deals", days=1).get("items", [])
    except Exception: return
    seen = state.setdefault("seen_deals", set())
    for d in deals:
        if d.get("magic") != MAGIC: continue
        pr = d.get("profit", 0) or 0
        if abs(pr) < 1e-9: continue
        did = d.get("ticket") or d.get("deal")
        if did in seen: continue
        seen.add(did)
        if state.get("primed"): notify(f"{'🟢' if pr >= 0 else '🔴'} {NAME} EXIT {sym} ${pr:+.2f}")
    state["primed"] = True

def study(api, sym):
    try: deals = [d for d in api._get("/api/deals", days=14).get("items", []) if d.get("magic") == MAGIC]
    except Exception: return
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
    now = int(dt.datetime.now().timestamp()); bars = api.bars(sym, ENTRY, 300)
    for o, c in trades:
        cid = c.get("ticket") or c.get("deal")
        if cid in done or (c.get("profit", 0) or 0) >= 0: continue
        et = c.get("time", 0)
        if now - et < STUDY_BARS * 300: continue
        side = "sell" if o.get("type") == 1 else "buy"; entry = o.get("price"); slx = c.get("price"); R = abs(slx - entry)
        if R <= 0: continue
        post = [b for b in bars if b['time'] > et][:STUDY_BARS]
        if len(post) < STUDY_BARS: continue
        mfe = (entry - min(b['low'] for b in post)) if side == "sell" else (max(b['high'] for b in post) - entry)
        mfeR = mfe / R
        with open(STUDY_FILE, "a") as f:
            f.write(json.dumps(dict(id=cid, exit_t=dt.datetime.fromtimestamp(et).isoformat(), side=side,
                    entry=round(entry, 3), sl=round(slx, 3), R=round(R, 3), mfe_R=round(mfeR, 2),
                    hit_tp=mfeR >= 2.0, profit=round(c.get('profit', 0), 2))) + "\n")

def step(api, sym, cfg, state):
    digits = cfg["digits"]
    em = api.bars(sym, ENTRY, 320); closed = em[:-1]
    if len(closed) < 80: return
    i = len(closed) - 1; b = closed[i]; last_t = b["time"]
    if state.get("last_bar") == last_t: return
    state["last_bar"] = last_t
    atr = atr_series(closed, ATRP); a = atr[i]
    if not (a == a) or a <= 0: return
    # bias M30+M15 searah
    dirs = []
    for tf in BIAS:
        bb = api.bars(sym, tf, 80)[:-1]; be = ema([x['close'] for x in bb], 50)
        if math.isnan(be[-1]): return
        dirs.append(1 if bb[-1]['close'] > be[-1] else -1)
    bias = dirs[0] if all(d == dirs[0] for d in dirs) else 0
    lv = {tf: pivots(closed if tf == ENTRY else api.bars(sym, tf, 320)[:-1]) for tf in CONF}
    price = b['close']; cl = cluster(lv, price, NEAR * a, CLUST * a)
    bs = {1: "BULL", -1: "BEAR", 0: "netral"}[bias]
    log(f"bar {dt.datetime.fromtimestamp(last_t):%m-%d %H:%M} close={price:.{digits}f} ATR={a:.{digits}f} bias={bs} cluster={f'{cl[0]:.{digits}f}({cl[3]}TF)' if cl else 'none'}")
    if bias == 0 or cl is None: return
    ctr, clo, chi, score = cl
    if abs(ctr - price) > ENTRYTOL * a: return
    if last_t - state.get("last_entry_t", 0) < COOLDOWN_S: return
    rng = b['high'] - b['low']
    if rng <= 0: return
    if bias == 1:
        if not ((b['low'] <= chi + ENTRYTOL * a) and (b['close'] > b['open']) and (b['close'] > ctr)): return
        side = "buy"; sl_lvl = clo - SLBUF * a
    else:
        if not ((b['high'] >= clo - ENTRYTOL * a) and (b['close'] < b['open']) and (b['close'] < ctr)): return
        side = "sell"; sl_lvl = chi + SLBUF * a
    if [p for p in api.positions(sym) if p.get("magic") == MAGIC]: log(f"  ✗ sudah ada posisi {NAME}"); return
    tick = api.tick(sym); entry = tick["ask"] if side == "buy" else tick["bid"]; risk = abs(entry - sl_lvl)
    if risk <= 0: return
    sl = round(sl_lvl, digits); tp = round(entry + RMULT * risk if side == "buy" else entry - RMULT * risk, digits)
    acc = api.account(); lot, est = calc_lot(acc["balance"] * cfg["risk"] / 100, risk, cfg["sinfo"])
    if est > acc["balance"] * 6.0 / 100: return
    log(f"➤ SINYAL {side.upper()} {sym} @ {entry:.{digits}f} | SL {sl} TP {tp} | {score}TF | lot {lot} risk ${est:.2f}")
    if not cfg["live"]: log("  [PAPER]"); state["last_entry_t"] = last_t; return
    try:
        out = api._post("/api/orders/send", dict(symbol=sym, side=side, volume=lot, sl=sl, tp=tp, deviation=20, magic=MAGIC, comment=NAME))
        res = out.get("result", {}); log(f"  ✓ LIVE retcode={res.get('retcode')} price={res.get('price')}")
        state["last_entry_t"] = last_t
        notify(f"🟢 {NAME} ENTRY {side.upper()} {sym} @ {res.get('price', entry):.{digits}f}\nSL {sl} · TP {tp} · {score}TF · lot {lot} · risk ${est:.2f}")
    except Exception as e: log(f"  ✗ order GAGAL: {e}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="XAUUSD"); p.add_argument("--risk", type=float, default=0.5)
    p.add_argument("--poll", type=int, default=20); p.add_argument("--live", action="store_true"); p.add_argument("--once", action="store_true")
    a = p.parse_args()
    api = MT5Api("http://192.168.0.111:8000", timeout=60); sinfo = api.symbol_info(a.symbol)
    cfg = dict(risk=a.risk, live=a.live, digits=sinfo["digits"], sinfo=sinfo); state = {}
    log(f"{NAME} forward-test | {a.symbol} {ENTRY} | magic {MAGIC} | {'🔴 LIVE demo' if a.live else '🟢 PAPER'} | risk {a.risk}%")
    if a.once: step(api, a.symbol, cfg, state); return
    loops = 0
    while True:
        try:
            check_exits(api, a.symbol, state); step(api, a.symbol, cfg, state)
            if loops % 10 == 0: study(api, a.symbol)
        except Exception as e: log(f"err {type(e).__name__}: {str(e)[:100]}")
        loops += 1; time.sleep(a.poll)

if __name__ == "__main__": main()
