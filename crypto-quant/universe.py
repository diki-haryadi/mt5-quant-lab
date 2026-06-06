"""
universe.py — watchlist crypto: LAYER-1 + PANTERA CAPITAL.

LAYER1   : token native blockchain Layer-1 utama (likuid, listed di top exchange).
PANTERA  : token portfolio Pantera Capital (publik/known; holdings berubah -> verifikasi berkala).
  PANTERA_DAT : 8 token "Digital Asset Treasury" Pantera = high-conviction core
                (sumber: CoinMarketCap/CryptoRank Pantera portfolio, Jun 2026).
Catatan: sebagian investasi Pantera berupa EKUITAS/privat (Coinbase, Circle, Bitstamp, dst) -> tak ada token.
"""

# native L1
LAYER1 = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "TRX", "DOT", "TON",
    "ATOM", "NEAR", "APT", "SUI", "ICP", "HBAR", "ALGO", "ETC", "INJ", "SEI",
    "TIA", "KAS", "EGLD", "MINA", "FLOW", "ROSE", "XTZ", "EOS", "NEO", "KAVA",
]

# core treasury (high conviction)
PANTERA_DAT = ["BTC", "ETH", "SOL", "BNB", "TON", "SUI", "ENA", "HYPE"]

# portfolio luas (DAT + token deal publik yg likuid)
PANTERA = PANTERA_DAT + [
    "XRP", "ZEC", "NEAR", "ONDO", "DOT", "MORPHO", "ATOM",
    "GRT", "FIL", "ICP", "ARB", "STX", "API3", "SKL",
]

NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "BNB": "BNB", "SOL": "Solana", "XRP": "XRP",
    "ADA": "Cardano", "AVAX": "Avalanche", "TRX": "Tron", "DOT": "Polkadot", "TON": "Toncoin",
    "ATOM": "Cosmos", "NEAR": "NEAR", "APT": "Aptos", "SUI": "Sui", "ICP": "Internet Computer",
    "HBAR": "Hedera", "ALGO": "Algorand", "ETC": "Ethereum Classic", "INJ": "Injective",
    "SEI": "Sei", "TIA": "Celestia", "KAS": "Kaspa", "EGLD": "MultiversX", "MINA": "Mina",
    "FLOW": "Flow", "ROSE": "Oasis", "XTZ": "Tezos", "EOS": "EOS", "NEO": "Neo", "KAVA": "Kava",
    "ENA": "Ethena", "HYPE": "Hyperliquid", "ZEC": "Zcash", "ONDO": "Ondo", "MORPHO": "Morpho",
    "GRT": "The Graph", "FIL": "Filecoin", "ARB": "Arbitrum", "STX": "Stacks",
    "API3": "API3", "SKL": "SKALE",
}


def universe() -> list[str]:
    return sorted(set(LAYER1) | set(PANTERA))


def tags(base: str) -> list[str]:
    t = []
    if base in LAYER1: t.append("L1")
    if base in PANTERA_DAT: t.append("DAT")
    elif base in PANTERA: t.append("PANT")
    return t


def meta(base: str) -> dict:
    return dict(base=base, name=NAMES.get(base, base), tags=tags(base),
                l1=base in LAYER1, pantera=base in PANTERA, dat=base in PANTERA_DAT)


def filter_universe(group: str | None) -> list[str]:
    g = (group or "").lower()
    if g in ("l1", "layer1"): return sorted(set(LAYER1))
    if g in ("pantera", "pant"): return sorted(set(PANTERA))
    if g == "dat": return list(PANTERA_DAT)
    return universe()


if __name__ == "__main__":
    u = universe()
    print(f"UNIVERSE: {len(u)} token | L1={len(set(LAYER1))} PANTERA={len(set(PANTERA))} (DAT={len(PANTERA_DAT)})")
    print("overlap L1∩PANTERA:", sorted(set(LAYER1) & set(PANTERA)))
    for b in u:
        m = meta(b)
        print(f"  {b:6} {','.join(m['tags']):10} {m['name']}")
