import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5:1.5b"  # Replace with phi3:mini or llama3.2:1b if desired

# System prompt forcing short, targeted answers focused on tech/gaming
SYSTEM_PROMPT = (
    "You are a helpful gaming and tech assistant inside a Discord bot. Expert in Path of Exile"
    "Keep your answers concise, clear, and under 150 words. "
    "Avoid unnecessary fluff or lengthy introductions."
)

async def query_ollama(prompt: str) -> str:
    """Sends a non-blocking request to the local Ollama instance."""
    payload = {
        "model": MODEL_NAME,
        "prompt": f"{SYSTEM_PROMPT}\n\nUser Question: {prompt}\nAnswer:",
        "stream": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OLLAMA_URL, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "No response generated.").strip()
                return f"⚠️ Ollama error: Received status code {resp.status}"
    except Exception as e:
        return f"⚠️ Could not reach local AI service: {e}"

class AICog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Slash Command ---
    @app_commands.command(name="ask", description="Ask Achiftant a question")
    @app_commands.describe(question="Your question for Achiftant")
    async def ask_slash(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        
        answer = await query_ollama(question)
        
        embed = discord.Embed(
            title="🤖 Achiftant's Response",
            description=answer,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Model: {MODEL_NAME} | Requested by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(AICog(bot))