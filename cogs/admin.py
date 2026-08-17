import discord
from discord.ext import commands

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Sync commands ---
    @commands.command()
    @commands.is_owner()
    async def sync(self,ctx: commands.Context):
        # Fast instant sync for the current server only (great for development)
        synced = await self.bot.tree.sync(guild=ctx.guild)
            
        await ctx.send(f"Synced {len(synced)} slash commands to this server!")

    @commands.command()
    @commands.is_owner()
    async def globalsync(self, ctx: commands.Context):
        
        # Global sync (updates across all servers, can take up to 1 hour to propagate)
        synced_global = await self.bot.tree.sync()
        
        await ctx.send(f"Synced {len(synced_global)} slash commands globally!")

    @commands.command(name="reload", aliases=["r"], help="Reloads a specified extension/cog.")
    @commands.is_owner()
    async def reload_cog(self, ctx: commands.Context, *, cog_name: str):
        """Reloads a cog dynamically.
        Usage: !reload poe OR !reload cogs.poe
        """
        # Format input name to ensure standard module pathing (e.g., 'cogs.poe')
        extension = cog_name if cog_name.startswith("cogs.") else f"cogs.{cog_name}"

        try:
            await self.bot.reload_extension(extension)
            await ctx.send(f"✅ Successfully reloaded `{extension}`")
        except commands.ExtensionNotLoaded:
            # If not currently loaded, attempt to load it directly
            try:
                await self.bot.load_extension(extension)
                await ctx.send(f"📥 `{extension}` was not loaded. Successfully loaded it now.")
            except Exception as e:
                await ctx.send(f"❌ Failed to load `{extension}`: ```py\n{e}\n```")
        except Exception as e:
            await ctx.send(f"❌ Error reloading `{extension}`: ```py\n{e}\n```")

    @reload_cog.error
    async def reload_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.NotOwner):
            await ctx.send("⛔ You do not have permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("⚠️ Please specify a cog name (e.g., `!reload poe`).")

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))