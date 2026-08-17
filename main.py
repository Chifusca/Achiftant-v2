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
        node: wavelink.Node = wavelink.Node(
            id="MAIN_NODE",
            uri="http://127.0.0.1:2333",
            password=LavalinkTOKEN  # Replace with your actual password
        )
        await wavelink.NodePool.connect(client=self, nodes=[node])

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

# --- Slash Command: Play ---
@bot.tree.command(name="play", description="Play a song from YouTube")
@app_commands.describe(search="Song title or URL")
async def play(interaction: discord.Interaction, search: str):
    await interaction.response.defer()

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("You must be in a voice channel to use this command.")
        return

    channel = interaction.user.voice.channel

    if not interaction.guild.voice_client:
        vc: wavelink.Player = await channel.connect(cls=wavelink.Player)
    else:
        vc: wavelink.Player = interaction.guild.voice_client

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