import aiohttp
from typing import Optional, Dict, Any

POE_NINJA_BASE = "https://poe.ninja/api/data"
POE_WIKI_API = "https://www.poewiki.net/w/api.php"

headers = {"User-Agent": "MyDiscordAssistant/1.0 (Personal Use)"}

async def get_current_league() -> str:
    """Fetches the active main league from poe.ninja or defaults to Standard"""
    url = "https://poe.ninja/api/data/getindexstate"
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                economy_leases = data.get("economyLeaseInformation", [])
                if economy_leases:
                    return economy_leases[0].get("league", "Standard")
    return "Standard"
async def get_item_price(item_name: str, league: Optional[str] = None) -> Optional[float]:
    """Fetches approximate chaos value for items/currency across multiple categories"""
    if not league:
        league = await get_current_league()

    # Define endpoints to check (Currency vs Items)
    currency_url = f"{POE_NINJA_BASE}/currencyoverview?league={league}&type=Currency"
    item_types = ["UniqueWeapon", "UniqueArmour", "UniqueAccessory", "UniqueFlask", "Fragment", "Scarab"]
    
    async with aiohttp.ClientSession(headers=headers) as session:
        # 1. Check Currency overview
        async with session.get(currency_url) as resp:
            if resp.status == 200:
                data = await resp.json()
                for line in data.get("lines", []):
                    if line.get("currencyTypeName", "").lower() == item_name.lower():
                        return line.get("chaosEquivalent")

        # 2. Check Item overviews
        for item_type in item_types:
            url = f"{POE_NINJA_BASE}/itemoverview?league={league}&type={item_type}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for line in data.get("lines", []):
                        if line.get("name", "").lower() == item_name.lower():
                            return line.get("chaosValue")
    return None

async def search_poe_wiki_details(query: str) -> Optional[Dict[str, str]]:
    """Searches official poe.wiki and returns title, URL, and intro summary snippet"""
    search_params = {
        "action": "opensearch",
        "search": query,
        "limit": 1,
        "format": "json"
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(POE_WIKI_API, params=search_params) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if not data or len(data) < 4 or not data[1]:
                return None

            title = data[1][0]
            url = data[3][0]

        # Extract summary text for the page
        parse_params = {
            "action": "query",
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "titles": title,
            "format": "json"
        }
        async with session.get(POE_WIKI_API, params=parse_params) as resp:
            if resp.status == 200:
                parse_data = await resp.json()
                pages = parse_data.get("query", {}).get("pages", {})
                for page_id, page_info in pages.items():
                    extract = page_info.get("extract", "No description available.")
                    # Truncate extract if too long
                    if len(extract) > 300:
                        extract = extract[:297] + "..."
                    return {"title": title, "url": url, "summary": extract}

    return {"title": title, "url": url, "summary": "No description preview available."}