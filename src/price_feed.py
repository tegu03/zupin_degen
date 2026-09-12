"""Ambil harga/MC/liquidity live per contract address dari DexScreener API.

DexScreener API bersifat publik, tidak perlu API key:
https://api.dexscreener.com/latest/dex/tokens/<contract_address>
"""
import logging

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_pair_data(session: aiohttp.ClientSession, contract_address: str, chain: str) -> dict | None:
    url = DEXSCREENER_URL.format(address=contract_address)
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
        if resp.status != 200:
            logger.warning("DexScreener status %s untuk %s", resp.status, contract_address)
            return None
        data = await resp.json()

    pairs = data.get("pairs") or []
    matching = [p for p in pairs if p.get("chainId", "").lower() == chain.lower()]
    candidates = matching or pairs
    if not candidates:
        return None

    # Pilih pair dengan liquidity terbesar (paling representatif)
    best = max(candidates, key=lambda p: (p.get("liquidity") or {}).get("usd", 0) or 0)

    return {
        "mc_usd": best.get("fdv") or best.get("marketCap"),
        "liq_usd": (best.get("liquidity") or {}).get("usd"),
        "price_usd": best.get("priceUsd"),
        "volume_1h_usd": (best.get("volume") or {}).get("h1"),
    }
