import discord, os
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('TOKEN')
chif = os.getenv('CHIF')

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@tree.command(name='middle-earth')
async def middle_earth(interaction):
    await interaction.response.send_message("melon")

@client.event
async def on_ready():
    await tree.sync()
    print('Ready!')

# @client.event
# async def on_message(self, message):
#     # don't respond to ourselves
#     if message.author == self.user:
#         return

#     if message.content == 'ping':
#         await message.channel.send('pong')

@client.event # follow Chif to VC
async def on_voice_state_update(member, before , after):
    voice_state = member.guild.voice_client
    if not before.channel and after.channel and member.id == int(chif):
        print(f'{member} connected to voice')
        await after.channel.connect(reconnect = False)
    
    if voice_state is None:
        return

    if len(voice_state.channel.members) == 1:
        print('just me')
        await voice_state.disconnect()
        voice_state.cleanup()

client.run(token)