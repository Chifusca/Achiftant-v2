import aiohttp
from typing import Optional, Dict, Any

POE_NINJA_BASE = "https://poe.ninja/api/data"
POE_WIKI_API = "https://www.poewiki.net/w/api.php"

headers = {"User-Agent": "MyDiscordAssistant/1.0 (Personal Use)"}

async def get_item_price(item_name: str, league: str = "Settlers") -> Optional[float]:
    """Fetches approximate chaos value for currency/items from poe.ninja"""
    endpoints = [
        f"{POE_NINJA_BASE}/currencyoverview?league={league}&type=Currency",
        f"{POE_NINJA_BASE}/itemoverview?league={league}&type=UniqueArmour"
    ]
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for url in endpoints:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    lines = data.get("lines", [])
                    for line in lines:
                        name = line.get("currencyTypeName") or line.get("name")
                        if name and name.lower() == item_name.lower():
                            return line.get("chaosEquivalent") or line.get("chaosValue")
    return None

async def search_poe_wiki(query: str) -> Optional[str]:
    """Searches official poe.wiki and returns the top article URL"""
    params = {
        "action": "opensearch",
        "search": query,
        "limit": 1,
        "format": "json"
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(POE_WIKI_API, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                if len(data) >= 4 and data[3]:
                    return data[3][0]  # First URL result
    return None