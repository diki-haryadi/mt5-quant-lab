# crypto-quant — Crypto Market Watch Engine

Engine pantau pasar crypto multi-exchange (Binance + Bybit + OKX), watchlist **Layer-1 + Pantera Capital**, indikator teknikal lengkap. Pure-python, hanya endpoint publik (tanpa API key).

## Modul
| File | Isi |
|---|---|
| `exchanges.py` | Client terpadu **Binance/Bybit/OKX/Hyperliquid**. `ticker(base)`, `klines(base,tf,limit)`, `best_klines()` (fallback). Spot base+quote(USDT); Hyperliquid=perp DEX (coin-only, bonus `funding`+`oi`). TF: 1m,5m,15m,1h,4h,1d. **Bypass blokir DNS Indonesia (Kominfo) via DoH Cloudflare** — wajib utk akses exchange dari infra ID. |
| `universe.py` | Watchlist: `LAYER1` (30), `PANTERA` (22, incl `PANTERA_DAT` 8 high-conviction). `tags()`, `meta()`, `filter_universe(group)` |
| `indicators.py` | ~40 indikator pure-python. `compute_all(bars)` → 49 nilai terbaru. Kategori: trend (SMA/EMA/WMA/HMA/DEMA/TEMA/VWMA, MACD, ADX, Aroon, SuperTrend, PSAR, Ichimoku), momentum (RSI, Stoch, StochRSI, CCI, Williams%R, ROC, MOM, CMO, MFI, TSI, UO), volatilitas (StdDev, Bollinger, ATR, NATR, Keltner, Donchian), volume (OBV, VWAP, CMF, A/D, Force Index, EOM, PVT) |
| `market_watch.py` | Engine: tarik universe paralel lintas-3-exchange, skor sinyal komposit (−6..+6), tabel watchlist, mode arbitrase, dump indikator |

## Pakai
```bash
python3 market_watch.py                       # semua universe, TF 1d, tabel + skor
python3 market_watch.py --group dat --tf 4h   # Pantera-DAT core, TF 4h
python3 market_watch.py --group l1 --sort pct # Layer-1 urut %24h
python3 market_watch.py --signals             # hanya sinyal kuat / RSI ekstrem
python3 market_watch.py --arb                 # spread harga antar-exchange
python3 market_watch.py --full BTC            # dump SEMUA indikator 1 simbol
python3 market_watch.py --book BTC            # orderbook depth + imbalance (4 exchange)
python3 market_watch.py --trades BTC          # running-trade/tape + rasio buy/sell agresif
python3 market_watch.py --deriv --group dat   # open interest + funding rate (perp, 4 exchange)
python3 market_watch.py --vwap BTC --anchor week  # anchored VWAP + stdev bands (konversi vwap.pine)
```

## VWAP (konversi `vwap.pine` TradingView)
`indicators.vwap_anchored(bars, anchor, src, bands, mode)` — anchored VWAP + volume-weighted stdev bands, setara indikator VWAP TradingView. Default: **anchor=week, src=hlc3 (H+L+C)/3, bands ±1/±2/±3σ, mode=stdev** (sesuai screenshot setting). Anchor: session/week/month/quarter/year/decade/century. Mode bands: `stdev` | `percentage`. `compute_all()` memuat `vwap_week`, band ±1/±2σ, `vwap_dist_pct`, `vwap_zone` (overbought ≥+2σ ... oversold ≤−2σ).

## Data terintegrasi
- 📊 **Candlestick** (OHLCV) — `klines()` 4 exchange
- 📖 **Orderbook** (depth + imbalance + spread) — `orderbook()` 4 exchange (`--book`)
- 🎞️ **Running trade** (tape + agresif buy/sell) — `trades()` spot 3 exchange (`--trades`; HL via WS, tak ada di REST)
- 📈 **Open Interest + Funding** (perp) — `derivatives()` 4 exchange (`--deriv`)
`group: all|l1|pantera|dat` · `tf: 1m,5m,15m,1h,4h,1d` · `sort: score|pct|vol|rsi|sym`

## Skor sinyal komposit
+1/−1 dari tiap: close vs EMA50, close vs EMA200, RSI zone, MACD-hist, ADX+DI/−DI, SuperTrend dir.
`≥+4` STRONG-BULL · `≥+2` bull · `≤−4` STRONG-BEAR · `≤−2` bear · else netral.

## Watchlist
- **Layer-1 (30):** BTC ETH BNB SOL XRP ADA AVAX TRX DOT TON ATOM NEAR APT SUI ICP HBAR ALGO ETC INJ SEI TIA KAS EGLD MINA FLOW ROSE XTZ EOS NEO KAVA
- **Pantera DAT (8, core):** BTC ETH SOL BNB TON SUI ENA HYPE
- **Pantera luas (+):** XRP ZEC NEAR ONDO DOT MORPHO ATOM GRT FIL ICP ARB STX API3 SKL

> Catatan: holdings Pantera berubah & sebagian privat/ekuitas (tak ada token). Verifikasi berkala di CoinMarketCap/CryptoRank portfolio.
