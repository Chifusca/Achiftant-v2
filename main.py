import discord
from discord import app_commands
from discord.ext import commands
import wavelink
import json
import os
from dotenv import load_dotenv
import poe_services

load_dotenv()
TOKEN = os.getenv('TOKEN')
LavalinkTOKEN = os.getenv('LavalinkToken')
CONFIG_FILE = os.getenv('CONFIG_FILE', 'config.json')

def load_settings() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_global_volume(volume: int):
    """Saves the global volume level across all servers."""
    settings = load_settings()
    settings["global_volume"] = volume
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(settings, f, indent=4)

def get_global_volume(default: int = 100) -> int:
    """Retrieves the global volume setting."""
    settings = load_settings()
    return settings.get("global_volume", default)

class Achiftant(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Lavalink v3 compatible Node configuration
        node = wavelink.Node(
            identifier="MAIN_NODE",
            uri="http://127.0.0.1:2333",
            password=LavalinkTOKEN  # Replace with your actual password
        )
        await wavelink.Pool.connect(client=self, nodes=[node])

        print("Lavalink node connected successfully.")

    async def on_ready(self):
        print(f"Bot online as {self.user} (ID: {self.user.id})")

bot = Achiftant()

@bot.listen("on_wavelink_track_start")
async def on_track_start(payload: wavelink.TrackStartEventPayload):
    player = payload.player
    if player:
        await player.set_volume(get_global_volume(default=10))

# --- Sync commands ---
@bot.command()
@commands.is_owner()
async def sync(ctx: commands.Context):
    # Fast instant sync for the current server only (great for development)
    synced = await bot.tree.sync(guild=ctx.guild)
        
    await ctx.send(f"Synced {len(synced)} slash commands to this server!")

@bot.command()
@commands.is_owner()
async def globalsync(ctx: commands.Context):
       
    # Global sync (updates across all servers, can take up to 1 hour to propagate)
    synced_global = await bot.tree.sync()
    
    await ctx.send(f"Synced {len(synced_global)} slash commands globally!")

# --- Player Controls View (Discord UI Buttons) ---
class MusicControlView(discord.ui.View):
    def __init__(self, player: wavelink.Player):
        super().__init__(timeout=None)  # Keeps buttons persistent while track plays
        self.player = player

    @discord.ui.button(label="Pause / Resume", style=discord.ButtonStyle.primary, emoji="⏯️")
    async def toggle_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.current:
            await interaction.response.send_message("Nothing is currently playing.", ephemeral=True)
            return

        if self.player.paused:
            await self.player.pause(False)
            await interaction.response.send_message("▶️ Resumed playback.", ephemeral=True)
        else:
            await self.player.pause(True)
            await interaction.response.send_message("⏸️ Paused playback.", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def skip_track(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.current:
            await interaction.response.send_message("Nothing to skip.", ephemeral=True)
            return

        await self.player.skip()
        await interaction.response.send_message("⏭️ Skipped track.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_player(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.disconnect()
        await interaction.response.send_message("⏹️ Stopped playback and disconnected.", ephemeral=True)
        self.stop()

# --- Helper function to create Now Playing Embed Card ---
def create_now_playing_embed(track: wavelink.Playable, requester: discord.Member) -> discord.Embed:
    # Convert milliseconds to MM:SS format
    duration_sec = track.length // 1000
    mins = duration_sec // 60
    secs = duration_sec % 60
    duration_str = f"{mins}:{secs:02d}"

    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"[{track.title}]({track.uri})",
        color=discord.Color.blurple()
    )
    
    embed.add_field(name="Author / Artist", value=track.author or "Unknown", inline=True)
    embed.add_field(name="Duration", value=duration_str, inline=True)
    embed.add_field(name="Requested By", value=requester.mention, inline=True)

    if track.artwork:
        embed.set_thumbnail(url=track.artwork)

    embed.set_footer(text="Use the buttons below to control playback.")
    return embed

# --- Slash Command: Play ---
@bot.tree.command(name="play", description="Play a track or add it to the queue")
@app_commands.describe(search="Song title or URL")
async def play(interaction: discord.Interaction, search: str):
    await interaction.response.defer()

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("You must be in a voice channel to use this command.")
        return

    channel = interaction.user.voice.channel

    # Fetch existing player or connect to channel
    vc: wavelink.Player = interaction.guild.voice_client  # type: ignore
    if not vc:
        try:
            vc = await channel.connect(cls=wavelink.Player)
        except Exception as e:
            await interaction.followup.send(f"Could not connect to voice channel: {e}")
            return
    elif vc.channel != channel:
        await vc.move_to(channel)

    # Search for track
    tracks: wavelink.Search = await wavelink.Playable.search(search)
    if not tracks:
        await interaction.followup.send("No tracks found.")
        return

    track = tracks[0] if isinstance(tracks, list) else tracks.tracks[0]

    try:
        # Check if a track is currently playing or paused
        if vc.playing or vc.paused:
            # Add to the queue instead of overriding
            await vc.queue.put_wait(track)
            
            embed = discord.Embed(
                title="📝 Added to Queue",
                description=f"[{track.title}]({track.uri})",
                color=discord.Color.green()
            )
            embed.add_field(name="Position in Queue", value=f"#{len(vc.queue)}", inline=True)
            embed.add_field(name="Author", value=track.author or "Unknown", inline=True)
            if track.artwork:
                embed.set_thumbnail(url=track.artwork)

            await interaction.followup.send(embed=embed)
        else:
            # Nothing is playing, start immediately
            await vc.play(track)
            
            embed = create_now_playing_embed(track, interaction.user)
            view = MusicControlView(player=vc)
            await interaction.followup.send(embed=embed, view=view)

    except wavelink.LavalinkException:
        # Handle reconnection if Lavalink session expired
        await vc.disconnect()
        vc = await channel.connect(cls=wavelink.Player)
        await vc.play(track)
        
        embed = create_now_playing_embed(track, interaction.user)
        view = MusicControlView(player=vc)
        await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="queue", description="Display the currently playing song and upcoming music queue")
async def queue(interaction: discord.Interaction):
    await interaction.response.defer()

    vc: wavelink.Player = interaction.guild.voice_client  # type: ignore

    # Check if the bot is connected to a voice channel
    if not vc or not vc.channel:
        await interaction.followup.send("The bot is not currently connected to a voice channel.")
        return

    # Check if there is a song playing or items in the queue
    if not vc.current and len(vc.queue) == 0:
        await interaction.followup.send("The queue is currently empty and nothing is playing.")
        return

    embed = discord.Embed(
        title="🎶 Current Music Queue",
        color=discord.Color.blurple()
    )

    # 1. Display currently playing song
    if vc.current:
        current_track = vc.current
        embed.add_field(
            name="Now Playing",
            value=f"[{current_track.title}]({current_track.uri}) | `{current_track.author or 'Unknown'}`",
            inline=False
        )
        if current_track.artwork:
            embed.set_thumbnail(url=current_track.artwork)

    # 2. Display upcoming tracks from vc.queue
    if len(vc.queue) > 0:
        upcoming_list = []
        # Show up to the first 10 upcoming tracks
        for idx, track in enumerate(list(vc.queue)[:10], start=1):
            upcoming_list.append(f"`{idx}.` [{track.title}]({track.uri}) — `{track.author or 'Unknown'}`")

        queue_str = "\n".join(upcoming_list)

        # Indicate if there are more tracks beyond the first 10
        if len(vc.queue) > 10:
            queue_str += f"\n\n*...and {len(vc.queue) - 10} more track(s)*"

        embed.add_field(
            name=f"Upcoming Tracks ({len(vc.queue)})",
            value=queue_str,
            inline=False
        )
    else:
        embed.add_field(
            name="Upcoming Tracks",
            value="No songs queued up next.",
            inline=False
        )

    await interaction.followup.send(embed=embed)

# --- Slash Command: Clear Queue ---
@bot.tree.command(name="clearqueue", description="Clear all upcoming tracks from the queue")
async def clear_queue(interaction: discord.Interaction):
    await interaction.response.defer()

    vc: wavelink.Player = interaction.guild.voice_client  # type: ignore

    if not vc or not vc.channel:
        await interaction.followup.send("The bot is not currently connected to a voice channel.")
        return

    if len(vc.queue) == 0:
        await interaction.followup.send("The queue is already empty.")
        return

    # Clear all tracks in the Wavelink queue
    track_count = len(vc.queue)
    vc.queue.clear()

    await interaction.followup.send(f"🗑️ Cleared **{track_count}** track(s) from the queue.")


# --- Slash Command: Remove Specific Track ---
@bot.tree.command(name="remove", description="Remove a specific track from the queue by its position")
@app_commands.describe(index="Position of the track in the queue (e.g., 1 for the next track)")
async def remove_track(interaction: discord.Interaction, index: app_commands.Range[int, 1, None]):
    await interaction.response.defer()

    vc: wavelink.Player = interaction.guild.voice_client  # type: ignore

    if not vc or not vc.channel:
        await interaction.followup.send("The bot is not currently connected to a voice channel.")
        return

    if len(vc.queue) == 0:
        await interaction.followup.send("The queue is currently empty.")
        return

    if index > len(vc.queue):
        await interaction.followup.send(f"Invalid position. The queue currently has **{len(vc.queue)}** track(s).")
        return

    # Remove the track at (index - 1) since positions are 1-based in UI
    removed_track = vc.queue.delete(index - 1)

    if removed_track:
        await interaction.followup.send(
            f"❌ Removed **[{removed_track.title}]({removed_track.uri})** from position **#{index}**."
        )
    else:
        await interaction.followup.send("Failed to remove the track from the queue.")


# --- Slash Command: Skip To Track ---
@bot.tree.command(name="skipto", description="Skip directly to a specific track in the queue")
@app_commands.describe(index="Position of the track in the queue to skip to")
async def skip_to(interaction: discord.Interaction, index: app_commands.Range[int, 1, None]):
    await interaction.response.defer()

    vc: wavelink.Player = interaction.guild.voice_client  # type: ignore

    if not vc or not vc.channel:
        await interaction.followup.send("The bot is not currently connected to a voice channel.")
        return

    if len(vc.queue) == 0:
        await interaction.followup.send("The queue is currently empty.")
        return

    if index > len(vc.queue):
        await interaction.followup.send(f"Invalid position. The queue currently has **{len(vc.queue)}** track(s).")
        return

    # Remove all preceding tracks up to index - 1
    for _ in range(index - 1):
        vc.queue.delete(0)

    # Skip current track to immediately play target track
    target_track = vc.queue[0]
    await vc.skip()

    await interaction.followup.send(
        f"⏭️ Skipped directly to position **#{index}**: **[{target_track.title}]({target_track.uri})**"
    )

# --- Volume command ---
@bot.command(name="volume", aliases=["vol"])
async def volume(ctx: commands.Context, level: int):
    """Prefix command to adjust global player volume (!volume <0-100>)."""
    if not (0 <= level <= 100):
        await ctx.send("Please provide a volume level between 0 and 100.")
        return

    # Save to global persistent storage
    save_global_volume(level)

    # Set volume for the current player calling the command
    vc: wavelink.Player = ctx.voice_client  # type: ignore

    if vc and vc.channel:
        await vc.set_volume(level)
        await ctx.send(f"🔊 Global volume set to **{level}%** and saved across all servers!")
    else:
        await ctx.send(f"🔊 Global volume saved to **{level}%**.")


# --- Slash Command: Price ---

POPULAR_LEAGUES = [
    "Allflame",
    "Hardcore Allflame",
    "Standard",
    "Hardcore",
    "Solo Self-Found",
]

class LeagueSelect(discord.ui.Select):
    def __init__(self):
        current_league = poe_services.get_active_league()
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
        # Update active league in poe_services
        poe_services.set_active_league(selected_league)
        
        await interaction.response.edit_message(
            content=f"✅ Default price check league changed to **{selected_league}**!",
            view=None
        )

class LeagueSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(LeagueSelect())

# --- Slash Command: Set League ---
@bot.tree.command(name="setleague", description="Select the default league used for price checking")
async def set_league(interaction: discord.Interaction):
    current = poe_services.get_active_league()
    view = LeagueSelectView()
    await interaction.response.send_message(
        f"⚙️ **Current Price Check League:** `{current}`\nSelect a new league from the dropdown below:",
        view=view,
        ephemeral=True  # Keeps menu interactions private to the caller
    )

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


def build_price_embed(data: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"💰 Price Check: {data['name']}",
        color=discord.Color.gold()
    )
    chaos_fmt = f"{data['chaos_value']:,.1f} c"
    divine_fmt = f"{data['divine_value']:.2f} Div" if data['divine_value'] >= 0.05 else "—"
    
    embed.add_field(name="Chaos Value", value=f"**{chaos_fmt}**", inline=True)
    embed.add_field(name="Divine Value", value=f"**{divine_fmt}**", inline=True)
    embed.add_field(name="Category", value=data['category'], inline=True)
    
    if data.get("icon"):
        embed.set_thumbnail(url=data["icon"])
        
    embed.set_footer(
        text=f"League: {data['league']} | 1 Div ≈ {data['divine_rate']:.0f}c | Source: poe.ninja"
    )
    return embed


@bot.tree.command(name="price", description="Check item prices on poe.ninja")
@app_commands.describe(
    item_name="The name of the item or currency (e.g. divine, mageblood, headhunter)",
    league="Optional: The league name (e.g. Settlers, Standard, Hardcore). Defaults to current league."
)
async def price(interaction: discord.Interaction, item_name: str, league: str = None):
    await interaction.response.defer()
    
    result = await poe_services.search_poe_ninja_items(item_name, league=league)
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
@bot.tree.command(name="wiki", description="Search the PoE Wiki")
@app_commands.describe(query="Topic or item to search")
async def wiki(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    result = await poe_services.search_poe_wiki_details(query)
    
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

bot.run(TOKEN)