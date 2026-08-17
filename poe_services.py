import aiohttp
import logging
import asyncio
from typing import Optional, Dict, Any, List

# Configure logger for debug visibility in your console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("poe_services")

POE_NINJA_BASE = "https://poe.ninja/api/data"
POE_WIKI_API = "https://www.poewiki.net/w/api.php"

headers = {"User-Agent": "Achiftant/1.0 (Personal Use)"}

async def get_current_league() -> str:
    """Fetches active economy league from poe.ninja"""
    url = f"{POE_NINJA_BASE}/getindexstate"
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    economy_leases = data.get("economyLeaseInformation", [])
                    if economy_leases:
                        return economy_leases[0].get("league", "Standard")
        except Exception as e:
            logger.error(f"League fetch error: {e}")
    return "Standard"

async def fetch_endpoint(session: aiohttp.ClientSession, url: str, is_currency: bool, category: str) -> List[Dict[str, Any]]:
    """Helper to fetch a single poe.ninja endpoint safely"""
    results = []
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                lines = data.get("lines", [])
                for line in lines:
                    name = line.get("currencyTypeName") if is_currency else line.get("name")
                    chaos = line.get("chaosEquivalent") if is_currency else line.get("chaosValue")
                    icon = line.get("icon")
                    
                    if name and chaos is not None:
                        results.append({
                            "name": name,
                            "chaos": float(chaos),
                            "icon": icon,
                            "category": category
                        })
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
    return results

async def search_poe_ninja_items(item_query: str, league: Optional[str] = None) -> Dict[str, Any]:
    """
    Searches poe.ninja and returns:
    - matches: List of matching item dictionaries
    - divine_rate: Current price of 1 Divine Orb in Chaos
    - league: Active league queried
    """
    if not league:
        league = await get_current_league()

    clean_query = item_query.strip().lower()
    logger.info(f"Searching poe.ninja for '{clean_query}' in '{league}'")

    currency_endpoints = [
        ("Currency", f"{POE_NINJA_BASE}/currencyoverview?league={league}&type=Currency"),
        ("Fragment", f"{POE_NINJA_BASE}/currencyoverview?league={league}&type=Fragment"),
    ]
    
    item_categories = [
        "UniqueWeapon", "UniqueArmour", "UniqueAccessory", "UniqueFlask",
        "UniqueJewel", "DivinationCard", "Essence", "SkillGem", 
        "Scarab", "Resonator", "Oil", "Artifact", "Tattoo"
    ]
    
    item_endpoints = [
        (cat, f"{POE_NINJA_BASE}/itemoverview?league={league}&type={cat}")
        for cat in item_categories
    ]

    divine_price_in_chaos = 150.0  # Fallback default
    all_items = []

    async with aiohttp.ClientSession(headers=headers) as session:
        # Fetch all currency & item categories concurrently
        tasks = []
        for cat, url in currency_endpoints:
            tasks.append(fetch_endpoint(session, url, is_currency=True, category=cat))
        for cat, url in item_endpoints:
            tasks.append(fetch_endpoint(session, url, is_currency=False, category=cat))

        responses = await asyncio.gather(*tasks)
        
        for item_list in responses:
            all_items.extend(item_list)

    # Extract Divine Orb price for conversions
    for item in all_items:
        if item["name"].lower() == "divine orb":
            divine_price_in_chaos = item["chaos"]
            break

    # Filter items matching the search query
    matches = [item for item in all_items if clean_query in item["name"].lower()]

    # Format chaos and divine values for all matches
    for item in matches:
        item["chaos_value"] = item["chaos"]
        item["divine_value"] = item["chaos"] / divine_price_in_chaos if divine_price_in_chaos > 0 else 0
        item["divine_rate"] = divine_price_in_chaos
        item["league"] = league

    return {
        "matches": matches,
        "divine_rate": divine_price_in_chaos,
        "league": league
    }


# --- Wiki Search Function ---
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
            "exintro": "1",
            "explaintext": "1",
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