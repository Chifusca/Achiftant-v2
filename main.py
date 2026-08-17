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
        # Wavelink v2 Node setup
        node: wavelink.Node = wavelink.Node(
            id="MAIN_NODE",
            host="127.0.0.1",
            port=2333,
            password="youshallnotpass",
            secure=False
        )
        await wavelink.NodePool.connect(client=self, nodes=[node])

        print("Lavalink node connected successfully.")

    async def on_ready(self):
        print(f"Bot online as {self.user} (ID: {self.user.id})")

bot = Achiftant()

@bot.command()
@commands.is_owner()
async def sync(ctx: commands.Context):
    #"""Syncs slash commands globally or to the local guild for fast testing."""
    # Fast instant sync for the current server only (great for development)
    synced = await bot.tree.sync(guild=ctx.guild)
    
    # Global sync (updates across all servers, can take up to 1 hour to propagate)
    # synced_global = await bot.tree.sync()
    
    await ctx.send(f"Synced {len(synced)} slash commands to this server!")

# --- Slash Command: Play ---
@bot.tree.command(name="play", description="Play a song from YouTube")
@app_commands.describe(search="Song title or URL")
async def play(interaction: discord.Interaction, search: str):
    await interaction.response.defer()

    # Check if user is in a voice channel
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("You must be in a voice channel to use this command.")
        return

    channel = interaction.user.voice.channel

    # Connect or get existing player
    if not interaction.guild.voice_client:
        vc: wavelink.Player = await channel.connect(cls=wavelink.Player)
    else:
        vc: wavelink.Player = interaction.guild.voice_client

    # Search for tracks using Wavelink v2 syntax (YouTubeTrack search)
    tracks = await wavelink.YouTubeTrack.search(search)
    if not tracks:
        await interaction.followup.send("No tracks found.")
        return

    track = tracks[0]
    await vc.play(track)
    await interaction.followup.send(f"Now playing: **{track.title}**")

# --- Slash Command: Price ---
@bot.tree.command(name="price", description="Check item prices on poe.ninja")
@app_commands.describe(item_name="The name of the item or currency")
async def price(interaction: discord.Interaction, item_name: str):
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