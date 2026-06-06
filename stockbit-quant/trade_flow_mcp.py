# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2.0", "requests"]
# ///
"""
trade_flow_mcp.py — MCP server "trade-flow": aliran dana broker saham IDX (Stockbit).
Expose 4 tool dari modul trade_flow.py (3 endpoint widget "Trade Flow" + ringkasan).
Jalankan stdio: uv run --directory <stockbit-quant> trade_flow_mcp.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP  # noqa: E402
from trade_flow import TradeFlow         # noqa: E402

mcp = FastMCP("trade-flow")
_tf = None


def tf() -> TradeFlow:
    global _tf
    if _tf is None:
        _tf = TradeFlow()
    return _tf


@mcp.tool()
def trade_flow_chart(symbol: str, to: str = "", period: int = 1,
                     market_board: int = 1, investor_type: int = 1) -> dict:
    """Chart Trade Flow intraday: garis harga per-menit + Net Buy/Sell per broker.
    symbol: kode saham IDX (mis. TPIA, BBCA). to: YYYY-MM-DD (kosong=hari ini).
    period 1=1D. Return {from,to,price_chart_data[],broker_chart_data[]}."""
    return tf().broker_flow(symbol.upper(), period=period, market_board=market_board,
                            investor_type=investor_type, to=to or None)


@mcp.tool()
def trade_book(symbol: str, group_by: int = 1, to: str = "") -> dict:
    """Distribusi transaksi per level harga (group_by=1) atau per waktu (group_by=2).
    Tiap baris: price, buy{lot,frequency,value,%}, sell{...}, total{...}.
    Return {symbol, group_by, rows:[...]}"""
    rows = tf().trade_book(symbol.upper(), group_by=group_by, to=to or None)
    return {"symbol": symbol.upper(), "group_by": group_by, "count": len(rows), "rows": rows}


@mcp.tool()
def bandar_detector(symbol: str) -> dict:
    """Bandar detector (gauge akumulasi<->distribusi) + broker_summary net buy/sell harian.
    Return {bandar_detector:{avg,avg5,top1/3/5/10,accdist,...}, broker_summary:{brokers_buy,brokers_sell}}."""
    return tf().bandar_detector(symbol.upper())


@mcp.tool()
def net_flow_summary(symbol: str) -> dict:
    """Ringkasan padat: status accdist (Acc/Dist), persen, top1/3/5, total buyer/seller, value, volume."""
    return tf().net_flow_summary(symbol.upper())


if __name__ == "__main__":
    mcp.run()
