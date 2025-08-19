import discord
import wavelink
import os
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()
TOKEN = os.getenv('TOKEN')
LavalinkTOKEN = os.getenv('LavalinkToken')
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(command_prefix="!", intents=intents)

queues = {}
voice_clients = {}

async def connect_nodes():
  """Connect to our Lavalink nodes."""
  await bot.wait_until_ready() # wait until the bot is ready

  nodes = [
    wavelink.Node(
      identifier="Node1", # This identifier must be unique for all the nodes you are going to use
      uri="localhost:2333", # Protocol (http/s) is required, port must be 443 as it is the one lavalink uses
      password=LavalinkTOKEN
    )
  ]

  await wavelink.Pool.connect(nodes=nodes, client=bot) # Connect our nodes

@bot.event
async def on_ready():
  await connect_nodes() # connect to the server

@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
  # Everytime a node is successfully connected, we
  # will print a message letting it know.
  print(f"Node with ID {payload.session_id} has connected")
  print(f"Resumed session: {payload.resumed}")

bot.run(TOKEN)