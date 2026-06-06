"""
exchanges.py — client market-data terpadu 3 exchange spot teratas: Binance, Bybit, OKX.
Hanya endpoint PUBLIK (tanpa API key). Simbol dinormalisasi: base (mis. 'BTC') + quote ('USDT').

API seragam tiap exchange:
  .ticker(base)          -> dict {ex,base,last,pct24,high24,low24,vol_base,vol_quote,bid,ask} | None
  .klines(base,tf,limit) -> list[{time,open,high,low,close,volume}] urut naik | None
tf normalisasi: 1m,5m,15m,1h,4h,1d
"""
from __future__ import annotations
import socket
import time
import requests

# ── Bypass blokir DNS Indonesia (Kominfo) untuk exchange via DoH Cloudflare ──
# ISP me-resolve api.binance.com dsb ke block-page (aduankonten.id). Koneksi/IP/SNI TIDAK
# diblok, hanya DNS. Kita resolve hostname lewat DoH (1.1.1.1) lalu patch getaddrinfo
# agar urllib3 connect ke IP benar (SNI tetap hostname asli = setara curl --resolve).
_DOH = "https://1.1.1.1/dns-query"
_DOH_HOSTS = ("api.binance.com", "fapi.binance.com", "api.bybit.com", "www.okx.com", "api.hyperliquid.xyz")
_dns_cache: dict[str, str] = {}


def _doh_resolve(host: str):
    if host in _dns_cache:
        return _dns_cache[host]
    try:
        r = requests.get(_DOH, params={"name": host, "type": "A"},
                         headers={"accept": "application/dns-json"}, timeout=8)
        ips = [a["data"] for a in r.json().get("Answer", []) if a.get("type") == 1]
        if ips:
            _dns_cache[host] = ips[0]
            return ips[0]
    except Exception:
        pass
    return None


_orig_getaddrinfo = socket.getaddrinfo


def _patched_getaddrinfo(host, *args, **kwargs):
    if host in _DOH_HOSTS:
        ip = _doh_resolve(host)
        if ip:
            return _orig_getaddrinfo(ip, *args, **kwargs)
    return _orig_getaddrinfo(host, *args, **kwargs)


if socket.getaddrinfo is not _patched_getaddrinfo:
    socket.getaddrinfo = _patched_getaddrinfo

TF = {  # tf -> kode per-exchange
    "1m":  {"binance": "1m",  "bybit": "1",   "okx": "1m"},
    "5m":  {"binance": "5m",  "bybit": "5",   "okx": "5m"},
    "15m": {"binance": "15m", "bybit": "15",  "okx": "15m"},
    "1h":  {"binance": "1h",  "bybit": "60",  "okx": "1H"},
    "4h":  {"binance": "4h",  "bybit": "240", "okx": "4H"},
    "1d":  {"binance": "1d",  "bybit": "D",   "okx": "1D"},
}


class _Base:
    name = "base"

    def __init__(self, quote: str = "USDT"):
        self.quote = quote
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "crypto-mw/1.0"

    def _get(self, url, params=None):
        r = self.s.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def sym(self, base: str) -> str: raise NotImplementedError
    def ticker(self, base: str): raise NotImplementedError
    def klines(self, base: str, tf: str = "1d", limit: int = 300): raise NotImplementedError
    # default: belum didukung exchange ybs
    def orderbook(self, base: str, depth: int = 20): return None
    def trades(self, base: str, limit: int = 50): return None
    def derivatives(self, base: str): return None  # {oi_base, oi_usd, funding}


class Binance(_Base):
    name = "binance"
    BASE = "https://api.binance.com"

    def sym(self, base): return f"{base}{self.quote}"

    def ticker(self, base):
        try:
            d = self._get(f"{self.BASE}/api/v3/ticker/24hr", {"symbol": self.sym(base)})
            return dict(ex=self.name, base=base, last=float(d["lastPrice"]),
                        pct24=float(d["priceChangePercent"]), high24=float(d["highPrice"]),
                        low24=float(d["lowPrice"]), vol_base=float(d["volume"]),
                        vol_quote=float(d["quoteVolume"]), bid=float(d["bidPrice"]),
                        ask=float(d["askPrice"]))
        except Exception:
            return None

    def klines(self, base, tf="1d", limit=300):
        try:
            d = self._get(f"{self.BASE}/api/v3/klines",
                          {"symbol": self.sym(base), "interval": TF[tf][self.name], "limit": limit})
            return [dict(time=int(k[0]) // 1000, open=float(k[1]), high=float(k[2]),
                         low=float(k[3]), close=float(k[4]), volume=float(k[5])) for k in d]
        except Exception:
            return None

    FBASE = "https://fapi.binance.com"  # USDT-M futures (OI/funding)

    def orderbook(self, base, depth=20):
        try:
            d = self._get(f"{self.BASE}/api/v3/depth", {"symbol": self.sym(base), "limit": depth})
            return dict(ex=self.name, bids=[(float(p), float(q)) for p, q in d["bids"]],
                        asks=[(float(p), float(q)) for p, q in d["asks"]])
        except Exception:
            return None

    def trades(self, base, limit=50):
        try:
            d = self._get(f"{self.BASE}/api/v3/trades", {"symbol": self.sym(base), "limit": limit})
            return [dict(time=int(t["time"]) // 1000, price=float(t["price"]), qty=float(t["qty"]),
                         side=("sell" if t["isBuyerMaker"] else "buy")) for t in d]
        except Exception:
            return None

    def derivatives(self, base):
        try:
            sym = self.sym(base)
            oi = self._get(f"{self.FBASE}/fapi/v1/openInterest", {"symbol": sym})
            pi = self._get(f"{self.FBASE}/fapi/v1/premiumIndex", {"symbol": sym})
            oib = float(oi["openInterest"]); mark = float(pi["markPrice"])
            return dict(ex=self.name, oi_base=oib, oi_usd=oib * mark, funding=float(pi["lastFundingRate"]))
        except Exception:
            return None


class Bybit(_Base):
    name = "bybit"
    BASE = "https://api.bybit.com"

    def sym(self, base): return f"{base}{self.quote}"

    def ticker(self, base):
        try:
            d = self._get(f"{self.BASE}/v5/market/tickers",
                          {"category": "spot", "symbol": self.sym(base)})
            lst = d.get("result", {}).get("list", [])
            if not lst: return None
            t = lst[0]
            return dict(ex=self.name, base=base, last=float(t["lastPrice"]),
                        pct24=float(t["price24hPcnt"]) * 100, high24=float(t["highPrice24h"]),
                        low24=float(t["lowPrice24h"]), vol_base=float(t["volume24h"]),
                        vol_quote=float(t["turnover24h"]), bid=float(t["bid1Price"]),
                        ask=float(t["ask1Price"]))
        except Exception:
            return None

    def klines(self, base, tf="1d", limit=300):
        try:
            d = self._get(f"{self.BASE}/v5/market/kline",
                          {"category": "spot", "symbol": self.sym(base),
                           "interval": TF[tf][self.name], "limit": min(limit, 1000)})
            lst = d.get("result", {}).get("list", [])
            out = [dict(time=int(k[0]) // 1000, open=float(k[1]), high=float(k[2]),
                        low=float(k[3]), close=float(k[4]), volume=float(k[5])) for k in lst]
            return out[::-1]  # bybit newest-first -> ascending
        except Exception:
            return None

    def orderbook(self, base, depth=25):
        try:
            d = self._get(f"{self.BASE}/v5/market/orderbook",
                          {"category": "spot", "symbol": self.sym(base), "limit": min(depth, 200)})
            r = d.get("result", {})
            return dict(ex=self.name, bids=[(float(p), float(q)) for p, q in r.get("b", [])],
                        asks=[(float(p), float(q)) for p, q in r.get("a", [])])
        except Exception:
            return None

    def trades(self, base, limit=50):
        try:
            d = self._get(f"{self.BASE}/v5/market/recent-trade",
                          {"category": "spot", "symbol": self.sym(base), "limit": min(limit, 60)})
            return [dict(time=int(t["time"]) // 1000, price=float(t["price"]), qty=float(t["size"]),
                         side=("buy" if t["side"] == "Buy" else "sell"))
                    for t in d.get("result", {}).get("list", [])]
        except Exception:
            return None

    def derivatives(self, base):
        try:
            d = self._get(f"{self.BASE}/v5/market/tickers", {"category": "linear", "symbol": self.sym(base)})
            lst = d.get("result", {}).get("list", [])
            if not lst: return None
            t = lst[0]
            return dict(ex=self.name, oi_base=float(t.get("openInterest") or 0),
                        oi_usd=float(t.get("openInterestValue") or 0), funding=float(t.get("fundingRate") or 0))
        except Exception:
            return None


class OKX(_Base):
    name = "okx"
    BASE = "https://www.okx.com"

    def sym(self, base): return f"{base}-{self.quote}"

    def ticker(self, base):
        try:
            d = self._get(f"{self.BASE}/api/v5/market/ticker", {"instId": self.sym(base)})
            data = d.get("data", [])
            if not data: return None
            t = data[0]; last = float(t["last"]); op = float(t["open24h"])
            return dict(ex=self.name, base=base, last=last,
                        pct24=(last / op - 1) * 100 if op else 0.0,
                        high24=float(t["high24h"]), low24=float(t["low24h"]),
                        vol_base=float(t["vol24h"]), vol_quote=float(t["volCcy24h"]),
                        bid=float(t["bidPx"] or 0), ask=float(t["askPx"] or 0))
        except Exception:
            return None

    def klines(self, base, tf="1d", limit=300):
        try:
            d = self._get(f"{self.BASE}/api/v5/market/candles",
                          {"instId": self.sym(base), "bar": TF[tf][self.name],
                           "limit": min(limit, 300)})
            data = d.get("data", [])
            out = [dict(time=int(k[0]) // 1000, open=float(k[1]), high=float(k[2]),
                        low=float(k[3]), close=float(k[4]), volume=float(k[5])) for k in data]
            return out[::-1]  # okx newest-first -> ascending
        except Exception:
            return None

    def orderbook(self, base, depth=25):
        try:
            d = self._get(f"{self.BASE}/api/v5/market/books", {"instId": self.sym(base), "sz": min(depth, 400)})
            data = d.get("data", [])
            if not data: return None
            b = data[0]
            return dict(ex=self.name, bids=[(float(x[0]), float(x[1])) for x in b.get("bids", [])],
                        asks=[(float(x[0]), float(x[1])) for x in b.get("asks", [])])
        except Exception:
            return None

    def trades(self, base, limit=50):
        try:
            d = self._get(f"{self.BASE}/api/v5/market/trades", {"instId": self.sym(base), "limit": min(limit, 100)})
            return [dict(time=int(t["ts"]) // 1000, price=float(t["px"]), qty=float(t["sz"]),
                         side=t["side"]) for t in d.get("data", [])]
        except Exception:
            return None

    def derivatives(self, base):
        try:
            inst = f"{base}-{self.quote}-SWAP"
            oi = self._get(f"{self.BASE}/api/v5/public/open-interest",
                           {"instType": "SWAP", "instId": inst}).get("data", [])
            if not oi: return None
            fr = self._get(f"{self.BASE}/api/v5/public/funding-rate", {"instId": inst}).get("data", [])
            oiccy = float(oi[0].get("oiCcy") or 0)
            t = self.ticker(base); px = t["last"] if t else 0
            return dict(ex=self.name, oi_base=oiccy, oi_usd=oiccy * px,
                        funding=float(fr[0]["fundingRate"]) if fr else 0.0)
        except Exception:
            return None


class Hyperliquid(_Base):
    """Hyperliquid (perp DEX). POST /info. Simbol = nama coin (mis. 'BTC'), tanpa quote.
    Bonus: ctx punya funding & openInterest (perp). high24/low24 tak disediakan API -> 0."""
    name = "hyperliquid"
    BASE = "https://api.hyperliquid.xyz"
    _IV = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
    _SEC = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
    _ctx_cache = {"t": 0.0, "data": None}  # cache lvl-class (TTL 10s) — hemat POST

    def sym(self, base): return base

    def _info(self, body):
        r = self.s.post(f"{self.BASE}/info", json=body, timeout=15)
        r.raise_for_status()
        return r.json()

    def _ctxs(self) -> dict:
        c = Hyperliquid._ctx_cache
        if c["data"] is not None and (time.time() - c["t"]) < 10:
            return c["data"]
        d = self._info({"type": "metaAndAssetCtxs"})
        meta, ctxs = d[0], d[1]
        out = {u["name"]: ctxs[i] for i, u in enumerate(meta["universe"])}
        Hyperliquid._ctx_cache = {"t": time.time(), "data": out}
        return out

    def ticker(self, base):
        try:
            c = self._ctxs().get(base)
            if not c: return None
            last = float(c.get("markPx") or c.get("midPx") or 0)
            prev = float(c.get("prevDayPx") or 0)
            vq = float(c.get("dayNtlVlm") or 0); vb = float(c.get("dayBaseVlm") or 0)
            return dict(ex=self.name, base=base, last=last,
                        pct24=(last / prev - 1) * 100 if prev else 0.0,
                        high24=0.0, low24=0.0, vol_base=vb, vol_quote=vq,
                        bid=last, ask=last,
                        funding=float(c.get("funding") or 0), oi=float(c.get("openInterest") or 0))
        except Exception:
            return None

    def klines(self, base, tf="1d", limit=300):
        try:
            iv = self._IV[tf]; sec = self._SEC[tf]
            end = int(time.time() * 1000); start = end - limit * sec * 1000
            d = self._info({"type": "candleSnapshot",
                            "req": {"coin": base, "interval": iv, "startTime": start, "endTime": end}})
            return [dict(time=int(k["t"]) // 1000, open=float(k["o"]), high=float(k["h"]),
                         low=float(k["l"]), close=float(k["c"]), volume=float(k["v"])) for k in d]
        except Exception:
            return None

    def orderbook(self, base, depth=20):
        try:
            d = self._info({"type": "l2Book", "coin": base})
            lv = d.get("levels", [[], []])
            return dict(ex=self.name,
                        bids=[(float(x["px"]), float(x["sz"])) for x in lv[0][:depth]],
                        asks=[(float(x["px"]), float(x["sz"])) for x in lv[1][:depth]])
        except Exception:
            return None

    # trades: HL recent-trade hanya via WebSocket, bukan REST /info -> None (default)

    def derivatives(self, base):
        try:
            c = self._ctxs().get(base)
            if not c: return None
            oi = float(c.get("openInterest") or 0); mark = float(c.get("markPx") or 0)
            return dict(ex=self.name, oi_base=oi, oi_usd=oi * mark, funding=float(c.get("funding") or 0))
        except Exception:
            return None


EXCHANGES = {"binance": Binance, "bybit": Bybit, "okx": OKX, "hyperliquid": Hyperliquid}


def make(name: str, quote: str = "USDT") -> _Base:
    return EXCHANGES[name](quote)


def all_clients(quote: str = "USDT") -> dict:
    return {n: c(quote) for n, c in EXCHANGES.items()}


def best_klines(base: str, tf: str = "1d", limit: int = 300,
                order=("binance", "bybit", "okx", "hyperliquid"), quote: str = "USDT"):
    """Ambil klines dari exchange pertama yg punya simbol (fallback berurutan). Return (bars, ex)."""
    for n in order:
        b = EXCHANGES[n](quote).klines(base, tf, limit)
        if b and len(b) > 20:
            return b, n
    return None, None


if __name__ == "__main__":
    import sys
    base = sys.argv[1] if len(sys.argv) > 1 else "BTC"
    for n, c in all_clients().items():
        t = c.ticker(base)
        print(f"{n:8} {('last %-12.4f pct %+6.2f%% volQ %.0f' % (t['last'], t['pct24'], t['vol_quote'])) if t else 'N/A'}")
    bars, ex = best_klines(base, "1d", 60)
    print(f"klines {base} 1d via {ex}: {len(bars) if bars else 0} bar (last close {bars[-1]['close'] if bars else '-'})")
