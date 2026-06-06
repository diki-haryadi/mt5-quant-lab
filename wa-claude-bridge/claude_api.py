"""claude_api.py — Bridge API umum (REST + SSE streaming + async job) untuk client Android/PWA.
Jalankan: uvicorn claude_api:app --host 0.0.0.0 --port 8090
Reuse roles.py + permguard.py (lewat .claude/settings.json) + session-resume Claude Code headless.
Claude jalan di server (langganan Pro/Max via `claude /login`); client cuma kirim teks + token.

Auth: header `Authorization: Bearer <token>`; daftar token sah di env DEVICE_TOKENS (csv `nama:token,...`).
"""
import os, json, time, uuid, queue, threading, subprocess, glob
import requests
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
import roles

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state"); os.makedirs(STATE, exist_ok=True)
SESS_DIR = os.path.join(STATE, "sessions"); os.makedirs(SESS_DIR, exist_ok=True)
ART_DIR = os.path.join(STATE, "artifacts"); os.makedirs(ART_DIR, exist_ok=True)
PUSH_FILE = os.path.join(STATE, "push_tokens.json")
QUANT_DIRS = ["/opt/idx-quant", "/opt/mt5-quant"]
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT", "900"))

SYSTEM = (
 "Kamu asisten quant milik Ben, diakses lewat app Android. "
 "Server Proxmox CT108: /opt/idx-quant (saham IDX/Stockbit), /opt/mt5-quant (forex MT5). "
 "Backtest/analisa: PYTHONPATH=/opt/idx-quant /opt/idx-quant/venv/bin/python <skrip>. "
 "Skrip: idx_stock_analysis.py, idx_movers.py, regime_scan.py (forex), bt_*.py. "
 "Saat menghasilkan grafik/CSV, SIMPAN ke folder artifact yang diberikan via env ARTIFACT_DIR "
 "(mis. equity.png, trades.csv) agar bisa ditarik client. "
 "Jawab ringkas, poin, angka penting. Hormati batas ROLE; jangan kirim order broker kecuali role=live & diminta eksplisit."
)

# ---------- auth ----------
def _tokens():
    out = {}
    for kv in os.environ.get("DEVICE_TOKENS", "").split(","):
        kv = kv.strip()
        if ":" in kv:
            name, tok = kv.split(":", 1); out[tok.strip()] = name.strip()
    return out
def require_auth(authorization):
    toks = _tokens()
    if not toks:  # belum dikonfigurasi -> tolak semua (fail-safe)
        raise HTTPException(503, "DEVICE_TOKENS belum diset di .env")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "butuh Bearer token")
    tok = authorization.split(" ", 1)[1].strip()
    if tok not in toks:
        raise HTTPException(403, "token tidak dikenal")
    return toks[tok]

# ---------- session & role state ----------
def _meta_path(sid): return os.path.join(SESS_DIR, f"{sid}.json")
def load_meta(sid):
    try: return json.load(open(_meta_path(sid)))
    except Exception: return None
def save_meta(sid, m): json.dump(m, open(_meta_path(sid), "w"), indent=1)
def new_session(device, title="Sesi baru"):
    sid = uuid.uuid4().hex[:12]
    save_meta(sid, dict(id=sid, device=device, title=title, role=roles.DEFAULT_ROLE,
                        claude_sid=None, confirm_until=0, created=time.time(), updated=time.time()))
    return sid
def list_sessions(device):
    out = []
    for p in glob.glob(os.path.join(SESS_DIR, "*.json")):
        m = json.load(open(p))
        if m.get("device") == device: out.append({k: m[k] for k in ("id","title","role","updated")})
    return sorted(out, key=lambda x: x["updated"], reverse=True)

# ---------- job registry ----------
JOBS = {}  # job_id -> {q:Queue, status, result, session_id}

def _stream_event(t, **kw): return f"data: {json.dumps({'type': t, **kw}, ensure_ascii=False)}\n\n"

def run_job(job_id, sid, prompt):
    m = load_meta(sid); j = JOBS[job_id]; q = j["q"]
    role = m["role"]; confirm = m.get("confirm_until", 0) > time.time()
    art = os.path.join(ART_DIR, job_id); os.makedirs(art, exist_ok=True)
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--model", MODEL, "--append-system-prompt", SYSTEM]
    for d in QUANT_DIRS: cmd += ["--add-dir", d]
    if m.get("claude_sid"): cmd += ["--resume", m["claude_sid"]]
    env = {**os.environ, "CLAUDE_ROLE": role, "CLAUDE_SESSION": sid,
           "CLAUDE_CONFIRM": "1" if confirm else "0", "ARTIFACT_DIR": art}
    q.put(_stream_event("ready", session_id=sid, role=role))
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=env, cwd=DIR, bufsize=1)
        result_text = ""
        for line in proc.stdout:
            line = line.strip()
            if not line: continue
            try: ev = json.loads(line)
            except Exception: continue
            t = ev.get("type")
            if t == "system" and ev.get("session_id"):
                m["claude_sid"] = ev["session_id"]; save_meta(sid, m)
            elif t == "assistant":
                for blk in ev.get("message", {}).get("content", []):
                    if blk.get("type") == "text" and blk.get("text"):
                        q.put(_stream_event("text", delta=blk["text"]))
                    elif blk.get("type") == "tool_use":
                        inp = json.dumps(blk.get("input", {}), ensure_ascii=False)[:200]
                        q.put(_stream_event("tool_use", name=blk.get("name", "?"), input=inp))
            elif t == "user":
                for blk in ev.get("message", {}).get("content", []):
                    if blk.get("type") == "tool_result":
                        c = blk.get("content")
                        s = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
                        q.put(_stream_event("tool_result", summary=(s or "")[:300]))
            elif t == "result":
                result_text = ev.get("result", "") or result_text
                if ev.get("session_id"): m["claude_sid"] = ev["session_id"]
        proc.wait(timeout=TIMEOUT)
        # artifacts yang ditulis Claude
        for f in sorted(glob.glob(os.path.join(art, "*"))):
            if os.path.isfile(f):
                aid = f"{job_id}/{os.path.basename(f)}"
                ext = os.path.splitext(f)[1].lstrip(".").lower()
                q.put(_stream_event("artifact", type=ext, url=f"/v1/artifacts/{aid}", name=os.path.basename(f)))
        if confirm: m["confirm_until"] = 0   # konsumsi 1x
        m["updated"] = time.time(); save_meta(sid, m)
        j["result"] = result_text; j["status"] = "done"
        q.put(_stream_event("done", result=result_text))
    except subprocess.TimeoutExpired:
        j["status"] = "error"; q.put(_stream_event("error", msg="timeout — persempit tugas"))
    except Exception as e:
        j["status"] = "error"; q.put(_stream_event("error", msg=str(e)[:200]))
    finally:
        q.put(None)  # sentinel akhir stream

# ---------- app ----------
app = FastAPI(title="Claude Quant Bridge API")

@app.get("/v1/health")
def health(): return {"ok": True, "model": MODEL, "tokens": len(_tokens())}

@app.get("/v1/sessions")
def sessions(authorization: str = Header(None)):
    dev = require_auth(authorization); return {"sessions": list_sessions(dev)}

@app.post("/v1/sessions")
async def create_session(req: Request, authorization: str = Header(None)):
    dev = require_auth(authorization)
    b = await req.json() if await req.body() else {}
    return {"session_id": new_session(dev, b.get("title", "Sesi baru"))}

@app.delete("/v1/sessions/{sid}")
def del_session(sid: str, authorization: str = Header(None)):
    require_auth(authorization)
    p = _meta_path(sid)
    if os.path.exists(p): os.remove(p)
    return {"ok": True}

@app.post("/v1/role")
async def set_role(req: Request, authorization: str = Header(None)):
    require_auth(authorization); b = await req.json()
    m = load_meta(b["session_id"])
    if not m: raise HTTPException(404, "sesi tak ada")
    if b.get("role") not in roles.ROLES: raise HTTPException(400, "role tak valid")
    m["role"] = b["role"]; save_meta(b["session_id"], m)
    return {"ok": True, "role": m["role"], "label": roles.ROLES[m["role"]]["label"]}

@app.post("/v1/confirm")
async def confirm(req: Request, authorization: str = Header(None)):
    require_auth(authorization); b = await req.json()
    m = load_meta(b["session_id"])
    if not m: raise HTTPException(404, "sesi tak ada")
    m["confirm_until"] = time.time() + 300; save_meta(b["session_id"], m)
    return {"ok": True, "confirm_until": m["confirm_until"]}

@app.post("/v1/chat")
async def chat(req: Request, authorization: str = Header(None)):
    dev = require_auth(authorization); b = await req.json()
    sid = b.get("session_id") or new_session(dev, (b.get("message", "")[:30] or "Sesi"))
    if not load_meta(sid): raise HTTPException(404, "sesi tak ada")
    msg = (b.get("message") or "").strip()
    if not msg: raise HTTPException(400, "message kosong")
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"q": queue.Queue(), "status": "running", "result": "", "session_id": sid}
    threading.Thread(target=run_job, args=(job_id, sid, msg), daemon=True).start()
    return {"job_id": job_id, "session_id": sid}

@app.get("/v1/chat/stream/{job_id}")
def stream(job_id: str, authorization: str = Header(None)):
    require_auth(authorization)
    j = JOBS.get(job_id)
    if not j: raise HTTPException(404, "job tak ada")
    def gen():
        while True:
            item = j["q"].get()
            if item is None: break
            yield item
    return StreamingResponse(gen(), media_type="text/event-stream")

@app.get("/v1/jobs/{job_id}")
def job_status(job_id: str, authorization: str = Header(None)):
    require_auth(authorization); j = JOBS.get(job_id)
    if not j: raise HTTPException(404, "job tak ada")
    return {"status": j["status"], "result": j["result"], "session_id": j["session_id"]}

@app.get("/v1/artifacts/{job_id}/{name}")
def artifact(job_id: str, name: str, authorization: str = Header(None)):
    require_auth(authorization)
    p = os.path.join(ART_DIR, job_id, os.path.basename(name))
    if not os.path.isfile(p): raise HTTPException(404, "artifact tak ada")
    return FileResponse(p)

@app.post("/v1/push/register")
async def push_register(req: Request, authorization: str = Header(None)):
    require_auth(authorization)
    b = await req.json()
    tok = (b.get("fcm_token") or "").strip()
    if not tok: raise HTTPException(400, "fcm_token kosong")
    toks = set()
    if os.path.exists(PUSH_FILE):
        try: toks = set(json.load(open(PUSH_FILE)))
        except Exception: pass
    toks.add(tok)
    json.dump(sorted(toks), open(PUSH_FILE, "w"))
    return {"ok": True, "count": len(toks)}

MT5_API = os.environ.get("MT5_API", "http://192.168.0.111:8000")

@app.get("/v1/live/forex")
def live_forex(authorization: str = Header(None)):
    """PnL forex REAL-TIME langsung dari MT5 API (tanpa Claude, ~ratusan ms)."""
    require_auth(authorization)
    try:
        acc = requests.get(f"{MT5_API}/api/account", timeout=5).json()
        pos = requests.get(f"{MT5_API}/api/positions", timeout=5).json()
    except Exception as e:
        raise HTTPException(503, f"MT5 API: {str(e)[:80]}")
    out = []
    for p in pos.get("items", []):
        op = float(p.get("price_open") or 0); cur = float(p.get("price_current") or 0)
        long = (p.get("type", 0) == 0)
        pct = (((cur / op - 1) if long else (op / cur - 1)) * 100) if op else 0.0
        out.append({"sym": p.get("symbol"), "side": "LONG" if long else "SHORT",
                    "qty": str(p.get("volume")), "entry": op, "mark": cur,
                    "pnl": float(p.get("profit") or 0), "pnlPct": round(pct, 3),
                    "strat": (p.get("comment") or str(p.get("magic")))})
    bal = float(acc.get("equity") or acc.get("balance") or 0)
    profit = float(acc.get("profit") or 0)
    return JSONResponse({"balance": bal, "currency": acc.get("currency", "USD"),
                         "profit": profit, "openPnlPct": round(profit / bal * 100, 3) if bal else 0.0,
                         "positions": out, "ts": int(time.time())})

def _run_regime(BL, bars, sinfo, capital, risk):
    """regime sejati: TREND(trail2.0)@ADX>=25 + MeanRev@ADX<20. Return objek mirip Result."""
    import math, datetime as _dt
    SL_ATR, TRAIL, ATRP, MAXR = 1.5, 2.0, 14, 6.0
    pt = sinfo["point"]; tk = sinfo.get("trade_tick_size") or pt; tv = sinfo.get("trade_tick_value") or 1.0
    money = lambda dd, lot: (dd / tk) * tv * lot
    tr = BL.make_trend(); tp_ = tr.prepare(bars); mr = BL.make_meanrev(); mp = mr.prepare(bars)
    atr = BL.atr_series(bars, ATRP); adx = BL.adx_vals(bars, 14); warm = max(tr.warmup, mr.warmup, 30)
    bal = capital; peak = capital; ddp = 0.0; T = []; pos = None
    for i in range(warm, len(bars)):
        b = bars[i]
        if pos:
            s = pos["s"]; a = pos["a"]; ex = None
            if pos["k"] == "TREND":
                if (s == "buy" and b["low"] <= pos["st"]) or (s == "sell" and b["high"] >= pos["st"]): ex = pos["st"]
            else:
                if s == "buy":
                    if b["low"] <= pos["st"]: ex = pos["st"]
                    elif b["high"] >= pos["tp"]: ex = pos["tp"]
                else:
                    if b["high"] >= pos["st"]: ex = pos["st"]
                    elif b["low"] <= pos["tp"]: ex = pos["tp"]
            if ex is not None:
                plp = (ex - pos["e"]) if s == "buy" else (pos["e"] - ex)
                net = money(plp, pos["lot"]) - money(pos["spr"], pos["lot"]); bal += net
                peak = max(peak, bal); ddp = max(ddp, (peak - bal) / peak * 100 if peak > 0 else 0)
                T.append({"net": net, "side": s, "entry_time": _dt.datetime.fromtimestamp(b["time"]).isoformat(),
                          "balance_after": bal}); pos = None
            elif pos["k"] == "TREND":
                if s == "buy": pos["hh"] = max(pos["hh"], b["high"]); pos["st"] = max(pos["st"], pos["hh"] - TRAIL * a)
                else: pos["ll"] = min(pos["ll"], b["low"]); pos["st"] = min(pos["st"], pos["ll"] + TRAIL * a)
        if pos: continue
        a = atr[i]
        if math.isnan(a) or a <= 0: continue
        ax = adx[i]
        if math.isnan(ax): continue
        k = side = None
        if ax >= 25: side = tr.signal(i, bars, tp_); k = "TREND"
        elif ax < 20: side = mr.signal(i, bars, mp); k = "MR"
        if not side: continue
        spr = b["spread"] * pt
        if a > 0 and spr / a * 100 > 12: continue
        sl_d = SL_ATR * a; lot, est = BL.calc_lot(bal * risk / 100, sl_d, sinfo)
        if est > bal * MAXR / 100: continue
        e = b["close"]
        pos = dict(k=k, s=side, e=e, a=a, lot=lot, spr=spr, st=e - sl_d if side == "buy" else e + sl_d,
                   hh=e, ll=e, tp=(e + 1.5 * a if side == "buy" else e - 1.5 * a))
    w = [x for x in T if x["net"] > 0]; l = [x for x in T if x["net"] <= 0]
    gw = sum(x["net"] for x in w); gl = -sum(x["net"] for x in l)
    class _R: pass
    r = _R()
    r.ret_pct = (bal - capital) / capital * 100; r.end_bal = bal; r.start_bal = capital
    r.win_rate = len(w) / len(T) * 100 if T else 0.0
    r.pf = (gw / gl) if gl else (float("inf") if gw else 0.0); r.max_dd_pct = ddp
    r.trade_log = [{"net": x["net"], "side": x["side"], "entry_time": x["entry_time"], "balance_after": x["balance_after"]} for x in T]
    return r

@app.get("/v1/runs")
def runs(limit: int = 30, authorization: str = Header(None)):
    """riwayat backtest dari RAG (Postgres runs table)."""
    require_auth(authorization)
    import sys as _sys
    if "/opt/mt5-quant" not in _sys.path: _sys.path.insert(0, "/opt/mt5-quant")
    # load PG creds dari mt5-quant/.env (journal butuh PGHOST dll)
    for ln in open("/opt/mt5-quant/.env").read().splitlines() if os.path.exists("/opt/mt5-quant/.env") else []:
        if ln.startswith("PG") and "=" in ln:
            k, v = ln.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
    try:
        import journal
        c = journal.conn() if callable(getattr(journal, "conn", None)) else journal.conn
        cur = c.cursor()
        cur.execute("""SELECT run_id,source,strategy,symbol,timeframe,start_balance,end_balance,
                       trades,win_rate,profit_factor,max_dd_pct,ret_pct,created_at
                       FROM runs ORDER BY created_at DESC LIMIT %s""", (min(int(limit), 100),))
        rows = []
        for r in cur.fetchall():
            d = dict(r) if not isinstance(r, dict) else r
            ret = d.get("ret_pct")
            if ret is None and d.get("start_balance"):
                ret = (float(d["end_balance"]) - float(d["start_balance"])) / float(d["start_balance"]) * 100
            rows.append({"run_id": d["run_id"], "source": d.get("source", ""), "strategy": d.get("strategy", ""),
                         "symbol": d.get("symbol", ""), "tf": d.get("timeframe", ""),
                         "ret": round(float(ret or 0), 2), "trades": d.get("trades", 0),
                         "winRate": round(float(d.get("win_rate") or 0), 1),
                         "pf": round(float(d.get("profit_factor") or 0), 2),
                         "maxDD": round(float(d.get("max_dd_pct") or 0), 1),
                         "at": str(d.get("created_at", ""))[:16]})
        return JSONResponse({"runs": rows})
    except Exception as e:
        raise HTTPException(503, f"runs: {str(e)[:120]}")

@app.get("/v1/meta")
def meta(authorization: str = Header(None)):
    """daftar strategi + pair untuk konfigurasi Backtest (server-driven)."""
    require_auth(authorization)
    return JSONResponse({
        "strategies": [
            {"id": "trend", "name": "Trend / Donchian", "desc": "Donchian20 + SMA50 breakout"},
            {"id": "meanrev", "name": "Mean Reversion", "desc": "Bollinger + RSI oversold"},
            {"id": "maosc", "name": "MA Oscillator", "desc": "EMA cross + RSI filter"},
            {"id": "regime", "name": "Regime-aware", "desc": "TREND@ADX (approx trend)"},
            {"id": "srconf", "name": "S/R Confluence (XAU)", "desc": "Konfluensi multi-TF + bias 1D/4H — tervalidasi XAUUSD"},
        ],
        "pairs": ["XAUUSD", "XAGUSD", "AUDJPY", "CHFJPY", "EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "EURJPY", "NZDUSD"],
        "tfs": ["M15", "H1", "H4", "D1"],
    })

@app.get("/v1/backtest")
def backtest(strategy: str = "trend", pair: str = "XAUUSD", capital: float = 1000,
             risk: float = 1.0, period: int = 90, tf: str = "M15", authorization: str = Header(None)):
    """Backtest CEPAT — jalankan engine backtest_lab langsung (detik, bukan menit via Claude)."""
    require_auth(authorization)
    import sys as _sys, statistics, datetime as _dt
    if "/opt/mt5-quant" not in _sys.path:
        _sys.path.insert(0, "/opt/mt5-quant")
    try:
        import backtest_lab as BL
        api = BL.MT5Api(MT5_API, timeout=120)
        sinfo = api.symbol_info(pair)
        bars, _per = BL.fetch_bars(api, pair, tf, int(period), 4000)
        if strategy == "srconf":
            import sr_engine
            return JSONResponse(sr_engine.bt(api, pair, float(capital), float(risk), int(period), rmult=2.0))
        if strategy == "regime":
            r = _run_regime(BL, bars, sinfo, float(capital), float(risk))
        else:
            mk = {"trend": BL.make_trend, "meanrev": BL.make_meanrev, "maosc": BL.make_maosc}
            strat = mk.get(strategy, BL.make_trend)()
            r = BL.run_backtest(bars, strat, sinfo, balance=float(capital), risk_pct=float(risk))
    except Exception as e:
        raise HTTPException(503, f"backtest engine: {str(e)[:140]}")
    tl = r.trade_log or []
    curve = [r.start_bal] + [t["balance_after"] for t in tl]
    if len(curve) > 60:
        s = len(curve) / 60.0
        curve = [curve[min(int(i * s), len(curve) - 1)] for i in range(60)]
    rets = [t["net"] / float(capital) for t in tl]
    sharpe = (statistics.mean(rets) / statistics.pstdev(rets) * (len(rets) ** 0.5)) if len(rets) > 1 and statistics.pstdev(rets) > 0 else 0.0
    d0 = _dt.datetime.fromisoformat(tl[0]["entry_time"]).date() if tl else None
    trades = []
    for i, t in enumerate(tl):
        day = (_dt.datetime.fromisoformat(t["entry_time"]).date() - d0).days if d0 else i
        trades.append({"n": i + 1, "dir": "LONG" if t["side"] == "buy" else "SHORT",
                       "day": day, "pnl": round(t["net"], 2), "win": t["net"] > 0})
    pf = r.pf if r.pf != float("inf") else 99.0
    return JSONResponse({"stats": {"totalReturn": round(r.ret_pct, 2), "finalEquity": int(r.end_bal),
                                   "winRate": int(r.win_rate), "profitFactor": round(pf, 2),
                                   "maxDD": round(r.max_dd_pct, 2), "sharpe": round(sharpe, 2)},
                         "curve": curve, "trades": trades, "source": "engine"})

@app.get("/v1/cache/{name}")
def cache_get(name: str, authorization: str = Header(None)):
    """snapshot precomputed (snapshot.py) — instan, tanpa Claude."""
    require_auth(authorization)
    p = os.path.join(STATE, f"snap_{os.path.basename(name)}.json")
    if not os.path.exists(p):
        raise HTTPException(404, "snapshot belum siap")
    return JSONResponse(content=json.loads(open(p).read()))
