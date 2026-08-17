import discord
from discord import app_commands
from discord.ext import commands
import wavelink
import json
import os
from dotenv import load_dotenv
import settings_utils as settings

from settings_utils import get_setting  # Adjust import path as needed

load_dotenv()
LavalinkTOKEN = os.getenv('LavalinkToken')
CONFIG_FILE = os.getenv('CONFIG_FILE', 'config.json')

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

# --- Music Cog ---
class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
            node = wavelink.Node(
                identifier="MAIN_NODE",
                uri="http://127.0.0.1:2333",
                password=LavalinkTOKEN  # Replace with your actual password
            )
            await wavelink.Pool.connect(client=self.bot, nodes=[node])

            print("Lavalink node connected successfully.")

    # --- Commands ---

    # --- Volume command ---
    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, level: int):
        """Prefix command to adjust global player volume (!volume <0-100>)."""
        if not (0 <= level <= 100):
            await ctx.send("Please provide a volume level between 0 and 100.")
            return

        # Save to global persistent storage
        settings.save_setting("volume", level)

        # Set volume for the current player calling the command
        vc: wavelink.Player = ctx.voice_client  # type: ignore

        if vc and vc.channel:
            await vc.set_volume(level)
            await ctx.send(f"🔊 Global volume set to **{level}%** and saved across all servers!")
        else:
            await ctx.send(f"🔊 Global volume saved to **{level}%**.")

    # --- AutoDisconnect Command ---
    @commands.command(name="autodisconnect", aliases=["autodc", "inactivetimeout"])
    async def auto_disconnect(self, ctx: commands.Context, seconds: int):
        """Prefix command to set global empty voice channel auto-disconnect timeout in seconds."""
        if seconds < 0:
            await ctx.send("Please specify a valid time in seconds (0 or greater).")
            return

        settings.save_setting("auto_disconnect_seconds", seconds)

        if seconds == 0:
            await ctx.send("⏸️ Global auto-disconnect on empty channel disabled.")
        else:
            await ctx.send(f"⏱️ Global auto-disconnect set to **{seconds} seconds** when voice channel is empty.")

    # --- Slash Command: Play ---
    @app_commands.command(name="play", description="Play a track or add it to the queue")
    @app_commands.describe(search="Song title or URL")
    async def play(self,interaction: discord.Interaction, search: str):
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
            # Check if a track is currently playing or paused
            if vc.playing or vc.paused:
                # Add to the queue instead of overriding
                await vc.queue.put_wait(track)
                
                embed = discord.Embed(
                    title="📝 Added to Queue",
                    description=f"[{track.title}]({track.uri})",
                    color=discord.Color.green()
                )
                embed.add_field(name="Position in Queue", value=f"#{len(vc.queue)}", inline=True)
                embed.add_field(name="Author", value=track.author or "Unknown", inline=True)
                if track.artwork:
                    embed.set_thumbnail(url=track.artwork)

                await interaction.followup.send(embed=embed)
            else:
                # Nothing is playing, start immediately
                await vc.play(track)
                
                embed = create_now_playing_embed(track, interaction.user)
                view = MusicControlView(player=vc)
                await interaction.followup.send(embed=embed, view=view)

        except wavelink.LavalinkException:
            # Handle reconnection if Lavalink session expired
            await vc.disconnect()
            vc = await channel.connect(cls=wavelink.Player)
            await vc.play(track)
            
            embed = create_now_playing_embed(track, interaction.user)
            view = MusicControlView(player=vc)
            await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="queue", description="Display the currently playing song and upcoming music queue")
    async def queue(self,interaction: discord.Interaction):
        await interaction.response.defer()

        vc: wavelink.Player = interaction.guild.voice_client  # type: ignore

        # Check if the bot is connected to a voice channel
        if not vc or not vc.channel:
            await interaction.followup.send("The bot is not currently connected to a voice channel.")
            return

        # Check if there is a song playing or items in the queue
        if not vc.current and len(vc.queue) == 0:
            await interaction.followup.send("The queue is currently empty and nothing is playing.")
            return

        embed = discord.Embed(
            title="🎶 Current Music Queue",
            color=discord.Color.blurple()
        )

        # 1. Display currently playing song
        if vc.current:
            current_track = vc.current
            embed.add_field(
                name="Now Playing",
                value=f"[{current_track.title}]({current_track.uri}) | `{current_track.author or 'Unknown'}`",
                inline=False
            )
            if current_track.artwork:
                embed.set_thumbnail(url=current_track.artwork)

        # 2. Display upcoming tracks from vc.queue
        if len(vc.queue) > 0:
            upcoming_list = []
            # Show up to the first 10 upcoming tracks
            for idx, track in enumerate(list(vc.queue)[:10], start=1):
                upcoming_list.append(f"`{idx}.` [{track.title}]({track.uri}) — `{track.author or 'Unknown'}`")

            queue_str = "\n".join(upcoming_list)

            # Indicate if there are more tracks beyond the first 10
            if len(vc.queue) > 10:
                queue_str += f"\n\n*...and {len(vc.queue) - 10} more track(s)*"

            embed.add_field(
                name=f"Upcoming Tracks ({len(vc.queue)})",
                value=queue_str,
                inline=False
            )
        else:
            embed.add_field(
                name="Upcoming Tracks",
                value="No songs queued up next.",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    # --- Slash Command: Clear Queue ---
    @app_commands.command(name="clearqueue", description="Clear all upcoming tracks from the queue")
    async def clear_queue(self, interaction: discord.Interaction):
        await interaction.response.defer()

        vc: wavelink.Player = interaction.guild.voice_client  # type: ignore

        if not vc or not vc.channel:
            await interaction.followup.send("The bot is not currently connected to a voice channel.")
            return

        if len(vc.queue) == 0:
            await interaction.followup.send("The queue is already empty.")
            return

        # Clear all tracks in the Wavelink queue
        track_count = len(vc.queue)
        vc.queue.clear()

        await interaction.followup.send(f"🗑️ Cleared **{track_count}** track(s) from the queue.")


    # --- Slash Command: Remove Specific Track ---
    @app_commands.command(name="remove", description="Remove a specific track from the queue by its position")
    @app_commands.describe(index="Position of the track in the queue (e.g., 1 for the next track)")
    async def remove_track(self, interaction: discord.Interaction, index: app_commands.Range[int, 1, None]):
        await interaction.response.defer()

        vc: wavelink.Player = interaction.guild.voice_client  # type: ignore

        if not vc or not vc.channel:
            await interaction.followup.send("The bot is not currently connected to a voice channel.")
            return

        if len(vc.queue) == 0:
            await interaction.followup.send("The queue is currently empty.")
            return

        if index > len(vc.queue):
            await interaction.followup.send(f"Invalid position. The queue currently has **{len(vc.queue)}** track(s).")
            return

        # Remove the track at (index - 1) since positions are 1-based in UI
        removed_track = vc.queue.delete(index - 1)

        if removed_track:
            await interaction.followup.send(
                f"❌ Removed **[{removed_track.title}]({removed_track.uri})** from position **#{index}**."
            )
        else:
            await interaction.followup.send("Failed to remove the track from the queue.")


    # --- Slash Command: Skip To Track ---
    @app_commands.command(name="skipto", description="Skip directly to a specific track in the queue")
    @app_commands.describe(index="Position of the track in the queue to skip to")
    async def skip_to(self, interaction: discord.Interaction, index: app_commands.Range[int, 1, None]):
        await interaction.response.defer()

        vc: wavelink.Player = interaction.guild.voice_client  # type: ignore

        if not vc or not vc.channel:
            await interaction.followup.send("The bot is not currently connected to a voice channel.")
            return

        if len(vc.queue) == 0:
            await interaction.followup.send("The queue is currently empty.")
            return

        if index > len(vc.queue):
            await interaction.followup.send(f"Invalid position. The queue currently has **{len(vc.queue)}** track(s).")
            return

        # Remove all preceding tracks up to index - 1
        for _ in range(index - 1):
            vc.queue.delete(0)

        # Skip current track to immediately play target track
        target_track = vc.queue[0]
        await vc.skip()

        await interaction.followup.send(
            f"⏭️ Skipped directly to position **#{index}**: **[{target_track.title}]({target_track.uri})**"
        )

    # --- Listeners ---
    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        player = payload.player
        if player:
            vol = get_setting("volume", 10)
            await player.set_volume(vol)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player or not player.guild:
            return

        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)

            vol = get_setting("volume", 10)
            await player.set_volume(vol)


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))