import datetime, json, os, discord
from discord import app_commands
from discord.ext import commands
from google import genai

# Configuration constants
DAILY_LIMIT = 950  # Safe threshold below the 1,000 free-tier limit
TRACKER_FILE = "gemini_usage_tracker.json"
MODEL_NAME = "gemini-3.6-flash"  # Lightweight, fast model for chat

# System prompt forcing short, targeted answers focused on tech/gaming
SYSTEM_PROMPT = (
    "You are a veteran Path of Exile theorycrafter. Explain mechanics concisely without fluff."
    "Keep your answers concise, clear, and under 150 words. "
    "Avoid unnecessary fluff or lengthy introductions."
)

def check_and_increment_quota() -> bool:
    """Checks daily request limit and resets if the date has changed."""
    today_str = datetime.date.today().isoformat()
    data = {"date": today_str, "count": 0}

    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r") as f:
                loaded_data = json.load(f)
                if loaded_data.get("date") == today_str:
                    data = loaded_data
        except Exception:
            pass

    if data["count"] >= DAILY_LIMIT:
        return False

    data["count"] += 1
    try:
        with open(TRACKER_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

    return True

async def query_gemini(prompt: str) -> str:
    """Sends a request to Google Gemini using the official SDK with rate-limiting."""
    if not check_and_increment_quota():
        return "⚠️ Daily AI request limit reached. Please try again tomorrow."

    try:
        client = genai.Client(api_key=os.getenv("GEMINI"))
        
        # Combine system instructions and user prompt safely
        full_prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {prompt}\nAnswer:"
        
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=full_prompt,
        )
        
        if response and response.text:
            return response.text.strip()
        return "No response generated."
        
    except Exception as e:
        return f"⚠️ Could not reach Gemini API: {e}"

class AICog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Slash Command ---
    @app_commands.command(name="ask", description="Ask Achiftant a question")
    @app_commands.describe(question="Your question for Achiftant")
    async def ask_slash(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        
        answer = await query_gemini(question)
        
        embed = discord.Embed(
            title="🤖 Achiftant's Response",
            description=answer,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Model: {MODEL_NAME} | Requested by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(AICog(bot))