import discord, random
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context

class Dm(commands.Cog, name="dm"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="roll",
        description="Rolls Dice",
    )
    @app_commands.describe(dice="Grab your dice")
    async def dice(self, context: Context, *, dice: str) -> None:
        """
        Rolls dice.

        :param context: The hybrid command context.
        :param question: The dice to be rolled.
        """

        die = [int(i) for i in dice.split("d")]
        result = die[0] * random.randint(1,die[1])
        if result == 20 and dice == '1d20':
            result = f'Crit! {result}'

        embed = discord.Embed(
            title="**Result:**",
            description=f"{result}",
            color=0xBEBEFE,
        )
        embed.set_footer(text=f"The rolled dice were: {dice}")
        await context.send(embed=embed)

async def setup(bot) -> None:
    await bot.add_cog(Dm(bot))