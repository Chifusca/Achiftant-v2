import asyncio
import discord
from discord.ext import commands
import wavelink
import os
from dotenv import load_dotenv

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

# --- Music Command Example ---
@bot.command(name="play")
async def play(ctx: commands.Context, *, search: str):
    if not ctx.voice_client:
        vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    else:
        vc: wavelink.Player = ctx.voice_client

    tracks = await wavelink.Playable.search(search)
    if not tracks:
        await ctx.send("No tracks found.")
        return

    track = tracks[0]
    await vc.play(track)
    await ctx.send(f"Now playing: **{track.title}**")

bot.run(TOKEN)