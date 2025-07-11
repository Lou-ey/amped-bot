import os
import discord
from discord.ext import commands

TOKEN = os.environ['TOKEN']

intents = discord.Intents.all()
intents.members = True
intents.message_content = True

client = commands.Bot(command_prefix='!', intents=intents)

green = 0x00FF00
red = 0xFF0000

@client.event
async def on_ready():
    print(f'{client.user} has connected to the following servers:\n')
    for server in client.guilds:
        print(f'- {server.name} (id: {server.id})')

        client.tree.copy_global_to(guild=server) # Copy global commands to the server
        await client.tree.sync(guild=server) # Sync the commands to the server
    print(f'\nCogs loaded:')
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await client.load_extension(f'cogs.{filename[:-3]}')
            try:
                print(f'- {filename[:-3]}')
            except Exception as e:
                print(f'Failed to load {filename[:-3]}')
                print(e)

@client.event
async def on_message(message):
    await client.process_commands(message)

@client.tree.command(name='help', description='Help command')
async def help(ctx): # This is a global command
    embed = discord.Embed(title='Help', color=green)
    embed.description = 'This is a help command'
    embed.add_field(name='!help', value='This command', inline=False)
    embed.add_field(name='!play', value='Play a song', inline=False)
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
