"""
trade_flow.py — modul "Trade Flow" Stockbit (3 endpoint penyusun widget Trade Flow).
Dipakai untuk strategi berbasis aliran dana broker (bandarmology intraday).

Widget "Trade Flow" Stockbit = gabungan 3 endpoint:
  1. broker_flow()     GET order-trade/running-trade/chart/{symbol}
                       -> price_chart_data (garis harga per-menit) + broker_chart_data (Net Buy/Sell per broker per-menit)
  2. trade_book()      GET order-trade/trade-book?group_by=...
                       -> book[] distribusi buy/sell per level harga (tab "Price") atau per waktu (tab "Time")
  3. bandar_detector() GET marketdetectors/{symbol}
                       -> bandar_detector (gauge Dist<->Acc) + broker_summary (net buy/sell per broker harian)

Auth & headers reuse stockbit_client.Stockbit (token dari ../stockbit-docs/stockbit_token.env).
CATATAN: data intraday (broker_flow / trade_book) bersifat realtime/harian; history terbatas.
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional

from stockbit_client import Stockbit


class TradeFlow:
    def __init__(self, sb: Optional[Stockbit] = None):
        self.sb = sb or Stockbit()

    def _get(self, path: str, params: dict, _retried: bool = False) -> dict:
        url = f"{self.sb.base}/{path.lstrip('/')}"
        r = self.sb.s.get(url, headers=self.sb.h, params=params, timeout=20)
        if r.status_code == 401 and not _retried:
            # token expired -> coba refresh chain lalu ulang sekali
            try:
                import stockbit_history as _H
                new = _H.refresh_access() or _H.login()
            except Exception:
                new = None
            if new:
                self.sb.token = new
                self.sb.h["Authorization"] = f"Bearer {new}"
                return self._get(path, params, _retried=True)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _today() -> str:
        return _dt.date.today().isoformat()

    # 1) CHART utama (garis harga + bar Net Buy/Net Sell per broker, intraday) ----------
    def broker_flow(self, symbol: str, period: int = 1, market_board: int = 1,
                    investor_type: int = 1, to: Optional[str] = None,
                    broker_code: Optional[str] = None) -> dict:
        """Return {from,to,price_chart_data:[...], broker_chart_data:[...]}.
        period 1=1D. market_board 1=Reguler. investor_type 1=all. to=YYYY-MM-DD."""
        params = {"period": period, "market_board": market_board,
                  "investor_type": investor_type, "to": to or self._today()}
        if broker_code:
            params["broker_code"] = broker_code
        d = self._get(f"order-trade/running-trade/chart/{symbol}", params)
        return d.get("data", d)

    # 2) TRADE BOOK (distribusi per harga / per waktu) ---------------------------------
    def trade_book(self, symbol: str, group_by: int = 1, sort_by: int = 1,
                   sort_direction: int = 1, time_interval: int = 1,
                   to: Optional[str] = None) -> list[dict]:
        """book[] per level harga (group_by=1) atau per waktu (group_by=2).
        Tiap baris: price, buy{lot,frequency,value,...}, sell{...}, total{...}."""
        params = {"symbol": symbol, "group_by": group_by, "sort_by": sort_by,
                  "sort_direction": sort_direction, "time_interval": time_interval,
                  "to": to or self._today()}
        d = self._get("order-trade/trade-book", params)
        return d.get("data", {}).get("book", [])

    # 3) BANDAR DETECTOR (gauge Dist<->Acc + ringkasan broker harian) ------------------
    def bandar_detector(self, symbol: str, transaction_type: str = "TRANSACTION_TYPE_NET",
                        market_board: str = "MARKET_BOARD_REGULER",
                        investor_type: str = "INVESTOR_TYPE_ALL", limit: int = 25,
                        period: str = "BROKER_SUMMARY_PERIOD_LATEST") -> dict:
        """Return {bandar_detector:{...accdist...}, broker_summary:{brokers_buy,brokers_sell}, from, to}."""
        params = {"transaction_type": transaction_type, "market_board": market_board,
                  "investor_type": investor_type, "limit": limit, "period": period}
        d = self._get(f"marketdetectors/{symbol}", params)
        return d.get("data", d)

    # ringkasan turunan: net flow harian (dari broker_summary) -------------------------
    def net_flow_summary(self, symbol: str) -> dict:
        """Ringkas accdist + total net value beli-jual broker (dari bandar_detector)."""
        d = self.bandar_detector(symbol)
        bd = d.get("bandar_detector", {})
        bs = bd.get("broker_summary", d.get("bandar_detector", {})) if isinstance(bd, dict) else {}
        avg = bd.get("avg", {}) if isinstance(bd, dict) else {}
        return {
            "symbol": symbol,
            "accdist": avg.get("accdist") or bd.get("broker_accdist"),
            "avg_percent": avg.get("percent"),
            "avg_amount": avg.get("amount"),
            "top1": bd.get("top1"), "top3": bd.get("top3"), "top5": bd.get("top5"),
            "total_buyer": bd.get("total_buyer"), "total_seller": bd.get("total_seller"),
            "value": bd.get("value"), "volume": bd.get("volume"),
            "from": d.get("from"), "to": d.get("to"),
        }


if __name__ == "__main__":
    import sys, json
    tf = TradeFlow()
    sym = sys.argv[1] if len(sys.argv) > 1 else "TPIA"
    print(f"=== broker_flow {sym} ===")
    bf = tf.broker_flow(sym)
    pc = bf.get("price_chart_data", []); bc = bf.get("broker_chart_data", [])
    print(f"price_chart_data: {len(pc)} titik (mis. {pc[0]['time']}={pc[0]['value']['formatted']} .. {pc[-1]['time']}={pc[-1]['value']['formatted']})" if pc else "kosong")
    print(f"broker_chart_data: {len(bc)} seri; brokers={bc[0].get('brokers') if bc else None}")
    print(f"\n=== trade_book {sym} (per harga) ===")
    tb = tf.trade_book(sym)
    print(f"{len(tb)} level; top: " + ", ".join(f"{b['price']}(buy {b['buy']['lot']}/sell {b['sell']['lot']})" for b in tb[:3]))
    print(f"\n=== net_flow_summary {sym} ===")
    print(json.dumps(tf.net_flow_summary(sym), indent=2))
