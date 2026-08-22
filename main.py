import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import settings_utils as settings

load_dotenv()
TOKEN = os.getenv('TOKEN')
LavalinkTOKEN = os.getenv('LavalinkToken')
CONFIG_FILE = os.getenv('CONFIG_FILE', 'config.json')
Chif = os.getenv('CHIF')

class Achiftant(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Dynamically load all cogs from the cogs directory
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded extension: {filename[:-3]}")

        # Sync app / slash command tree with Discord
        await self.tree.sync()
        print("Command tree synced successfully.")
    
    async def on_ready(self):
        print(f"Bot online as {self.user} (ID: {self.user.id})")

bot = Achiftant()

if __name__ == "__main__":
    bot.run(TOKEN)