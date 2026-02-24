import logging
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import sys
from utils.utils import Utils

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
intents.members = True
intents.message_content = True

client = commands.Bot(command_prefix='!', intents=intents)

green = 0x00FF00
red = 0xFF0000

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

disabled_cogs = [cog.strip() for cog in os.getenv('DISABLED_COGS', '').split(',') if cog.strip()]

utils = Utils(client)

@client.event
async def on_ready():
    activity = discord.Activity(type=discord.ActivityType.listening, name='!help')
    await client.change_presence(activity=activity)
    logging.info(f'{client.user} has connected to the following servers:\n')
    for server in client.guilds:
        logging.info(f'- {server.name} (id: {server.id})')

        client.tree.copy_global_to(guild=server) # Copy global commands to the server
        await client.tree.sync(guild=server) # Sync the commands to the server
    logging.info(f'\nCogs loaded:')
    # verify that the cogs already loaded
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and filename[:-3] not in disabled_cogs:
            cog_name = f'cogs.{filename[:-3]}'
            try:
                if cog_name in client.extensions:
                    logging.info(f'Cog {filename[:-3]} already loaded, ignoring...')
                else:
                    await client.load_extension(cog_name)
                    logging.info(f'Loaded cog: {filename[:-3]}')
            except Exception as e:
                logging.info(f"Failed to load '{cog_name}': {e}")

    #await utils.terminal_commanding(logging=logging)

@client.event
async def on_message(message):
    await client.process_commands(message)

@client.tree.command(name='help', description='Help command')
async def help(ctx): # This is a global command
    embed = discord.Embed(title='Help', color=green)
    embed.description = 'This is a help command'
    embed.add_field(name='!help', value='This command', inline=False)
    embed.add_field(name='!play', value='Play a song. In case of a playlist you can use -s to shuffle like this: "!play <url> -s" or "!play -s <url>"', inline=False)
    embed.add_field(name='!pause', value='Pause the song', inline=False)
    embed.add_field(name='!resume', value='Resume the song', inline=False)
    embed.add_field(name='!stop', value='Stop the song', inline=False)
    embed.add_field(name='!skip', value='Skip the song', inline=False)
    embed.add_field(name='!queue', value='Show the queue', inline=False)
    await ctx.response.send_message(embed=embed)

@client.command()
async def chg_vc(ctx, from_channel: discord.VoiceChannel, to_channel: discord.VoiceChannel):
    embed = discord.Embed(color=green)
    if ctx.voice_client is None:
        embed.description = 'I am not connected to a voice channel'
        await ctx.send(embed=embed)
        return
    if ctx.voice_client.channel != from_channel:
        await ctx.send('I am not connected to the specified voice channel')
        return
    await ctx.voice_client.move_to(to_channel)
    embed.description(f'Moved from {from_channel} to {to_channel}')
    await ctx.send(embed=embed)

client.run(TOKEN)
