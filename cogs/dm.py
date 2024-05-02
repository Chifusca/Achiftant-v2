import aiohttp
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context

class Dm(commands.Cog, name="dm"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="dice",
        description="Rolls a Dice",
    )
    async def ping(self, context: Context) -> None:
        """
        Check if the bot is alive.

        :param context: The hybrid command context.
        """
        embed = discord.Embed(
            title="Result:",
            description=f"you got a 20!",
            color=0xBEBEFE,
        )
        await context.send(embed=embed)

async def setup(bot) -> None:
    await bot.add_cog(Dm(bot))