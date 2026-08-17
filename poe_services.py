import aiohttp
import logging
import asyncio
from typing import Optional, Dict, Any, List

# Configure logger for debug visibility in your console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("poe_services")

POE_NINJA_EXCHANGE = "https://poe.ninja/poe1/api/economy/exchange/current/overview"
POE_NINJA_ITEM = "https://poe.ninja/poe1/api/economy/stash/current/item/overview"
#OFFICIAL_GGG_LEAGUES_URL = "https://api.pathofexile.com/league?type=main&realm=pc"
POE_WIKI_API = "https://www.poewiki.net/w/api.php"

headers = {
    "User-Agent": "Achiftant/1.0.0 (contact: radeon1389@hotmail.com)"
}

# Set your default target league here if none is specified by the user
ACTIVE_LEAGUE = "Settlers"

def get_active_league() -> str:
    """Returns the currently active league."""
    return ACTIVE_LEAGUE

def set_active_league(new_league: str):
    """Updates the active default league for price checks."""
    global ACTIVE_LEAGUE
    ACTIVE_LEAGUE = new_league

async def fetch_endpoint(session: aiohttp.ClientSession, url: str, is_currency: bool, category: str) -> List[Dict[str, Any]]:
    results = []
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                lines = data.get("lines", [])
                
                currency_map = {}
                if is_currency:
                    for c in data.get("currencyDetails", []):
                        c_name = c.get("name")
                        c_id = c.get("id")
                        if c_name:
                            currency_map[c_name] = c.get("icon")
                        if c_id:
                            currency_map[c_id] = c.get("icon")

                for line in lines:
                    if is_currency:
                        name = line.get("currencyTypeName")
                        if not name:
                            details_id = line.get("detailsId", "")
                            name = details_id.replace("-", " ").title()
                        
                        chaos = line.get("chaosEquivalent")
                        if chaos is None and "receive" in line:
                            chaos = line.get("receive", {}).get("value")
                        
                        icon = currency_map.get(name) or line.get("icon")
                    else:
                        name = line.get("name")
                        chaos = line.get("chaosValue")
                        icon = line.get("icon")
                    
                    if name and chaos is not None:
                        results.append({
                            "name": name,
                            "chaos": float(chaos),
                            "icon": icon,
                            "category": category
                        })
            else:
                logger.warning(f"Endpoint HTTP {resp.status}: {url}")
    except Exception as e:
        logger.error(f"Request failed for {url}: {e}")
    return results


async def search_poe_ninja_items(item_query: str, league: Optional[str] = None) -> Dict[str, Any]:
    # Use the specified league argument, or fall back to the dynamic active league
    active_league = league.strip() if league else get_active_league()

    clean_query = item_query.strip().lower()
    logger.info(f"Querying poe.ninja for '{clean_query}' in league '{active_league}'")

    currency_endpoints = [
        ("Currency", f"{POE_NINJA_EXCHANGE}?league={active_league}&type=Currency"),
        ("Fragment", f"{POE_NINJA_EXCHANGE}?league={active_league}&type=Fragment"),
    ]
    
    item_categories = [
        "UniqueWeapon", "UniqueArmour", "UniqueAccessory", "UniqueFlask",
        "UniqueJewel", "DivinationCard", "Essence", "SkillGem", 
        "Scarab", "Resonator", "Oil", "Artifact", "Tattoo"
    ]
    
    item_endpoints = [
        (cat, f"{POE_NINJA_ITEM}?league={active_league}&type={cat}")
        for cat in item_categories
    ]

    divine_price_in_chaos = 150.0
    all_items = []

    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = []
        for cat, url in currency_endpoints:
            tasks.append(fetch_endpoint(session, url, is_currency=True, category=cat))
        for cat, url in item_endpoints:
            tasks.append(fetch_endpoint(session, url, is_currency=False, category=cat))

        responses = await asyncio.gather(*tasks)
        for item_list in responses:
            all_items.extend(item_list)

    for item in all_items:
        if item["name"].lower() == "divine orb":
            divine_price_in_chaos = item["chaos"]
            break

    matches = [item for item in all_items if clean_query in item["name"].lower()]

    for item in matches:
        item["chaos_value"] = item["chaos"]
        item["divine_value"] = item["chaos"] / divine_price_in_chaos if divine_price_in_chaos > 0 else 0
        item["divine_rate"] = divine_price_in_chaos
        item["league"] = active_league

    return {
        "matches": matches,
        "divine_rate": divine_price_in_chaos,
        "league": active_league
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