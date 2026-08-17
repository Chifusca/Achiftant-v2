import asyncio
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
        # Connect Lavalink Node
        node = wavelink.Node(
            uri="http://127.0.0.1:2333",  # Your Lavalink address/port
            password=LavalinkTOKEN      # Your Lavalink password
        )
        await wavelink.Pool.connect(nodes=[node], client=self)
        print("Lavalink node connected successfully.")

    async def on_ready(self):
        print(f"Bot online as {self.user} (ID: {self.user.id})")

bot = Achiftant()

@bot.command()
@commands.is_owner()
async def sync(ctx: commands.Context):
    """Syncs slash commands globally or to the local guild for fast testing."""
    # Fast instant sync for the current server only (great for development)
    synced_guild = await bot.tree.sync(guild=ctx.guild)
    
    # Global sync (updates across all servers, can take up to 1 hour to propagate)
    # synced_global = await bot.tree.sync()
    
    await ctx.send(f"Synced {len(synced_guild)} slash commands to this server!")

# --- Music Command Example ---
@bot.tree.command(name="play" , description="Play a song from YouTube")
@app_commands.describe(search="The song name or URL to play")
async def play(interaction: discord.Interaction, search: str):
    if not interaction.user.voice:
        await interaction.response.send_message("You are not connected to a voice channel.")
        return

    if not interaction.guild.voice_client:
        vc: wavelink.Player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
    else:
        vc: wavelink.Player = interaction.guild.voice_client

    tracks = await wavelink.Playable.search(search)
    if not tracks:
        await interaction.response.send_message("No tracks found.")
        return

    track = tracks[0]
    await vc.play(track)
    await interaction.response.send_message(f"Now playing: **{track.title}**")

@bot.tree.command(name="price", description="Check item prices on poe.ninja")
@app_commands.describe(item_name="The name of the item or currency")
async def price(interaction: discord.Interaction, item_name: str):
    # Acknowledge the command if API calls might take a second
    await interaction.response.defer()
    
    cost = await poe_services.get_item_price(item_name)
    if cost:
        await interaction.followup.send(f"**{item_name}** is approximately **{cost:.1f} Chaos**.")
    else:
        await interaction.followup.send(f"Could not find price data for **{item_name}**.")

# --- Slash Command: Wiki ---
@bot.tree.command(name="wiki", description="Search the PoE Wiki")
@app_commands.describe(query="Topic or item to search")
async def wiki(interaction: discord.Interaction, query: str):
    url = await poe_services.search_poe_wiki(query)
    if url:
        await interaction.response.send_message(f"PoE Wiki entry for **{query}**: {url}")
    else:
        await interaction.response.send_message("No results found on the PoE Wiki.")

bot.run(TOKEN)