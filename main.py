import discord
from discord import app_commands
from discord.ext import commands
import wavelink
import os
from dotenv import load_dotenv
import poe_services

load_dotenv()
TOKEN = os.getenv('TOKEN')
LavalinkTOKEN = os.getenv('LavalinkToken')

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
@bot.tree.command(name="play", description="Play a song from YouTube")
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
        await vc.play(track)
        
        # Build Embed Card and Attached Button View
        embed = create_now_playing_embed(track, interaction.user)
        view = MusicControlView(player=vc)

        await interaction.followup.send(embed=embed, view=view)

    except wavelink.LavalinkException:
        # Session reconnect handler
        await vc.disconnect()
        vc = await channel.connect(cls=wavelink.Player)
        await vc.play(track)
        
        embed = create_now_playing_embed(track, interaction.user)
        view = MusicControlView(player=vc)
        await interaction.followup.send(embed=embed, view=view)

# --- Slash Command: Price ---
@bot.tree.command(name="price", description="Check item prices on poe.ninja")
@app_commands.describe(item_name="The name of the item or currency")
async def price(interaction: discord.Interaction, item_name: str):
    await interaction.response.defer()
    cost = await poe_services.get_item_price(item_name)
    if cost is not None:
        await interaction.followup.send(f"**{item_name}** is approximately **{cost:.1f} Chaos**.")
    else:
        await interaction.followup.send(f"Could not find price data for **{item_name}**.")

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