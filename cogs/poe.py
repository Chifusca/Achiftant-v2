import aiohttp, asyncio, logging, discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, Any, List

# Configure logger for debug visibility in your console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("poe_services")

POE_NINJA_EXCHANGE = "https://poe.ninja/poe1/api/economy/exchange/current/overview"
POE_NINJA_ITEM = "https://poe.ninja/poe1/api/economy/stash/current/item/overview"
POE_WIKI_API = "https://www.poewiki.net/w/api.php"

# Set your default target league here if none is specified by the user
ACTIVE_LEAGUE = "Allflame"
POPULAR_LEAGUES = [
        "Allflame",
        "Hardcore Allflame",
        "Standard",
        "Hardcore",
    ]

headers = {
    "User-Agent": "Achiftant/1.0 (radeon1389@hotmail.com)"
}

def get_active_league() -> str:
    """Returns the currently active league."""
    return ACTIVE_LEAGUE

def set_active_league(new_league: str) -> None:
    """Updates the active default league for price checking."""
    global ACTIVE_LEAGUE
    ACTIVE_LEAGUE = new_league

def build_price_embed(data: dict) -> discord.Embed:
    """Formats item price data into a Discord Embed."""
    embed = discord.Embed(
        title=f"💰 Price Check: {data['name']}",
        color=discord.Color.gold()
    )
    chaos_fmt = f"{data['chaos_value']:,.1f} c"
    divine_fmt = f"{data['divine_value']:.2f} Div" if data.get('divine_value', 0) >= 0.05 else "—"
    
    embed.add_field(name="Chaos Value", value=f"**{chaos_fmt}**", inline=True)
    embed.add_field(name="Divine Value", value=f"**{divine_fmt}**", inline=True)
    embed.add_field(name="Category", value=data.get('category', 'N/A'), inline=True)
    
    if data.get("icon"):
        embed.set_thumbnail(url=data["icon"])
        
    div_rate = data.get('divine_rate', 0)
    embed.set_footer(
        text=f"League: {data.get('league', 'N/A')} | 1 Div ≈ {div_rate:.0f}c | Source: poe.ninja"
    )
    return embed

# --- UI Elements ---

class LeagueSelect(discord.ui.Select):
    def __init__(self):
        current_league = get_active_league()
        options = [
            discord.SelectOption(
                label=league,
                description=f"Set price check league to {league}",
                default=(league.lower() == current_league.lower())
            )
            for league in POPULAR_LEAGUES
        ]
        super().__init__(
            placeholder="Select a league for price checks...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_league = self.values[0]
        set_active_league(selected_league)
        
        await interaction.response.edit_message(
            content=f"✅ Default price check league changed to **{selected_league}**!",
            view=None
        )

class LeagueSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(LeagueSelect())

class ItemSelect(discord.ui.Select):
    def __init__(self, matches: list):
        options = [
            discord.SelectOption(
                label=item["name"][:100],
                description=f"{item['category']} | {item['chaos_value']:,.1f}c",
                value=str(index)
            )
            for index, item in enumerate(matches[:25])
        ]
        super().__init__(placeholder="Select the exact item...", min_values=1, max_values=1, options=options)
        self.matches = matches

    async def callback(self, interaction: discord.Interaction):
        selected_index = int(self.values[0])
        data = self.matches[selected_index]
        embed = build_price_embed(data)
        await interaction.response.edit_message(content=None, embed=embed, view=None)


class ItemSelectView(discord.ui.View):
    def __init__(self, matches: list):
        super().__init__(timeout=60)
        self.add_item(ItemSelect(matches))

# --- API Fetching Functions ---

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

# --- poe Cog ---

class PoeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Commands ---
    @app_commands.command(name="setleague", description="Select the default league used for price checking")
    async def set_league(self, interaction: discord.Interaction):
        current = get_active_league()
        view = LeagueSelectView()
        await interaction.response.send_message(
            f"⚙️ **Current Price Check League:** `{current}`\nSelect a new league from the dropdown below:",
            view=view,
            ephemeral=True
        )

    @app_commands.command(name="price", description="Check item prices on poe.ninja")
    @app_commands.describe(item_name="The name of the item or currency (e.g. divine, mageblood, headhunter)",
        league="Optional: The league name (e.g. Settlers, Standard, Hardcore). Defaults to current league."
    )
    async def price(self,interaction: discord.Interaction, item_name: str, league: str = None):
        await interaction.response.defer()
        
        result = await search_poe_ninja_items(item_name, league=league)
        matches = result.get("matches", [])
        
        if not matches:
            await interaction.followup.send(
                f"❌ Could not find any price data for **'{item_name}'** in league `{result['league']}`."
            )
            return

        exact_match = next((item for item in matches if item["name"].lower() == item_name.strip().lower()), None)

        if exact_match:
            embed = build_price_embed(exact_match)
            await interaction.followup.send(embed=embed)
        elif len(matches) == 1:
            embed = build_price_embed(matches[0])
            await interaction.followup.send(embed=embed)
        else:
            view = ItemSelectView(matches)
            await interaction.followup.send(
                f"🔍 Found **{len(matches)}** matches for **'{item_name}'** in `{result['league']}`. Select one from the menu below:",
                view=view
            )

    # --- Slash Command: Wiki (Rich Card Format) ---
    @app_commands.command(name="wiki", description="Search the PoE Wiki")
    @app_commands.describe(query="Topic or item to search")
    async def wiki(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        result = await search_poe_wiki_details(query)
        
        if result:
            embed = discord.Embed(
                title=result["title"],
                url=result["url"],
                description=result["summary"],
                color=discord.Color.dark_gold()
            )
            embed.set_footer(text="Official Path of Exile Wiki", icon_url="https://www.poewiki.net/favicon.ico")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"No Wiki results found for **{query}**.")

async def setup(bot: commands.Bot):
    await bot.add_cog(PoeCog(bot))