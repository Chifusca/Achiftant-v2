import discord, os, wavelink
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
Chif = os.getenv('CHIF')

class FollowCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        
        # 1. Ignore the bot itself to prevent loop issues
        if member.id == self.bot.user.id:
            return

        # 2. Only proceed if the member is the target user
        if member.id == Chif:
            return

        # 3. Check if the user moved to a valid voice channel (covers both joining and switching channels)
        if after.channel is not None and before.channel != after.channel:
            
            # Fetch the bot's current voice client in this server
            vc: wavelink.Player = member.guild.voice_client

            if not vc:
                # IMPORTANT: Connect using Wavelink Player so music commands still function
                try:
                    await after.channel.connect(cls=wavelink.Player)
                    print(f"Followed {member.display_name} into {after.channel.name}")
                except Exception as e:
                    print(f"Failed to follow into voice channel: {e}")
            else:
                # If the bot is already connected somewhere else, just move it
                if vc.channel != after.channel:
                    await vc.move_to(after.channel)
                    print(f"Moved with {member.display_name} into {after.channel.name}")

async def setup(bot: commands.Bot):
    await bot.add_cog(FollowCog(bot))
