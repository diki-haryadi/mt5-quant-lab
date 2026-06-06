"""sr_compare.py — perbandingan 3 forward-test S/R-confluence XAUUSD (live + baseline backtest).
770010 swing | 770011 M5 | 770012 swing+MFI-divergence. Tampilkan tabel; --wa kirim ke WhatsApp."""
import argparse, datetime as dt, requests
from mt5_scalper import MT5Api

API = "http://192.168.0.111:8000"
SYM = "XAUUSD"
STRAT = {  # magic: (nama, baseline backtest)
    770010: ("SWING (M15)",      "PF 1.39 · WR 42% · WF 6/6 · 540d"),
    770011: ("M5 (jalan-tengah)", "PF 1.29 · WR ~40% · WF 6/6 · 150d"),
    770012: ("SWING+MFI-div",    "PF 1.99 · WR 48% · WF 6/6 · 540d"),
}

def live_stats(api, magic, days):
    try: deals = [d for d in api._get("/api/deals", days=days).get("items", []) if d.get("magic") == magic]
    except Exception: deals = []
    closed = [d for d in deals if d.get("entry") == 1]
    nets = [(d.get("profit", 0) or 0) + (d.get("swap", 0) or 0) + (d.get("commission", 0) or 0) for d in closed]
    n = len(nets); wins = [x for x in nets if x > 0]
    gw = sum(wins); gl = -sum(x for x in nets if x <= 0)
    wr = (len(wins) / n * 100) if n else 0
    pf = (gw / gl) if gl else (999 if gw else 0)
    return n, wr, pf, sum(nets)

def open_pos(api, magic):
    try: pos = [p for p in api.positions(SYM) if p.get("magic") == magic]
    except Exception: pos = []
    return pos

def build(days):
    api = MT5Api(API, timeout=60)
    L = [f"📊 SR-CONFLUENCE — 3 FORWARD-TEST XAUUSD",
         f"   {dt.datetime.now():%d %b %Y %H:%M} · akun demo · live {days}h terakhir", ""]
    tot_open = 0.0
    for mg, (name, base) in STRAT.items():
        n, wr, pf, net = live_stats(api, mg, days)
        pos = open_pos(api, mg)
        flt = sum(p.get("profit", 0) or 0 for p in pos); tot_open += flt
        L.append(f"▸ {name}  [{mg}]")
        L.append(f"   backtest: {base}")
        if n: L.append(f"   live: {n} tutup · WR {wr:.0f}% · PF {pf:.2f} · net ${net:+.2f}")
        else: L.append(f"   live: belum ada trade tertutup")
        if pos:
            for p in pos:
                sd = "BUY" if p.get("type") == 0 else "SELL"
                L.append(f"   ◦ {sd} {p.get('volume')} @ {p.get('price_open')} → uPL ${p.get('profit', 0):+.2f}")
        L.append("")
    L.append(f"💰 total floating (3 strategi): ${tot_open:+.2f}")
    return "\n".join(L)

def _waenv():
    e = {}
    try:
        for ln in open("/opt/mt5-quant/waha.env"):
            ln = ln.strip()
            if "=" in ln and not ln.startswith("#"): k, v = ln.split("=", 1); e[k.strip()] = v.strip().strip('"')
    except Exception: pass
    return e
def send_wa(text):
    e = _waenv()
    if not all(e.get(k) for k in ("WAHA_URL", "WAHA_KEY", "WA_CHATID")): return "waha.env tak lengkap"
    r = requests.post(f"{e['WAHA_URL']}/api/sendText", headers={"X-Api-Key": e["WAHA_KEY"], "Content-Type": "application/json"},
                      json={"session": "default", "chatId": e["WA_CHATID"], "text": text}, timeout=20)
    return f"WA {r.status_code}"

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--days", type=int, default=14); p.add_argument("--wa", action="store_true")
    a = p.parse_args()
    msg = build(a.days)
    print(msg)
    if a.wa: print("\n[" + send_wa(msg) + "]")
