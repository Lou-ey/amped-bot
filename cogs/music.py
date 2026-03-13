import re
import discord
import lavalink
from discord.ext import commands
from lavalink.events import TrackStartEvent, TrackEndEvent, QueueEndEvent
from lavalink.server import LoadType
import os
import asyncio
from dotenv import load_dotenv
from utils.utils import Utils
import logging

load_dotenv()
PASSWORD = os.getenv("PASSWORD")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

green = 0x00FF00
red = 0xFF0000
blue = 0x0080FF

url_rx = re.compile(r'https?://(?:www\.)?.+')

class LavalinkVoiceClient(discord.VoiceProtocol):
    def __init__(self, client: discord.Client, channel: discord.abc.Connectable):
        self.client = client
        self.channel = channel
        self.guild_id = channel.guild.id
        self._destroyed = False

        if not hasattr(self.client, 'lavalink'):
            self.client.lavalink = lavalink.Client(client.user.id)
            self.client.lavalink.add_node(
                host='127.0.0.1',
                port=2333,
                password=PASSWORD,
                region='eu',
                name='default-node'
            )

        self.lavalink = self.client.lavalink

    async def on_voice_server_update(self, data):
        lavalink_data = {'t': 'VOICE_SERVER_UPDATE', 'd': data}
        await self.lavalink.voice_update_handler(lavalink_data)

    async def on_voice_state_update(self, data):
        channel_id = data['channel_id']
        if not channel_id:
            await self._destroy()
            return
        self.channel = self.client.get_channel(int(channel_id))
        lavalink_data = {'t': 'VOICE_STATE_UPDATE', 'd': data}
        await self.lavalink.voice_update_handler(lavalink_data)

    async def connect(self, *, timeout: float, reconnect: bool, self_deaf: bool = False,
                      self_mute: bool = False) -> None:
        self.lavalink.player_manager.create(guild_id=self.channel.guild.id)
        await self.channel.guild.change_voice_state(channel=self.channel, self_mute=self_mute, self_deaf=self_deaf)

    async def disconnect(self, *, force: bool = False) -> None:
        player = self.lavalink.player_manager.get(self.channel.guild.id)
        if not force and not player.is_connected:
            return
        await self.channel.guild.change_voice_state(channel=None)
        player.channel_id = None
        await self._destroy()

    async def _destroy(self):
        self.cleanup()
        if self._destroyed:
            return
        self._destroyed = True
        try:
            await self.lavalink.player_manager.destroy(self.guild_id)
        except lavalink.ClientError:
            pass

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(bot)
        self.bar = self.utils.generate_progress_bar
        self.format_time = self.utils.format_time
        self.format_time_hhmmss = self.utils.format_time_hhmmss
        self.paginate = self.utils.paginate
        self.progress_tasks = {}

        if not hasattr(bot, 'lavalink'):
            bot.lavalink = lavalink.Client(bot.user.id)
            bot.lavalink.add_node(
                host='127.0.0.1',
                port=2333,
                password=PASSWORD,
                region='eu',
                name='default-node'
            )

        self.lavalink: lavalink.Client = bot.lavalink
        self.lavalink.add_event_hooks(self)

    def cog_unload(self):
        self.lavalink._event_hooks.clear()

    @staticmethod
    def source_emoji(source: str):
        if source == 'youtube':
            return '<:youtube:1304468389883809813>'
        elif source == 'spotify':
            return '<:spotify:1304468005102555206>'
        elif source == 'soundcloud':
            return '<:soundcloud:1305561757653139506>'
        return '🎵'

    # EVENTS
    @lavalink.listener(TrackStartEvent)
    async def on_track_start(self, event: TrackStartEvent):
        player = event.player
        track = event.track

        channel_id = player.fetch('text_channel')
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        requester = self.bot.get_user(track.extra.get('requester', 0))

        # O teu Embed de Now Playing
        embed = discord.Embed(color=blue, title=f"{self.source_emoji(track.source_name)}  🎶 Now Playing")
        embed.description = f"**{track.title}** by `{track.author}`"

        duration = ":red_circle: **LIVE**" if track.stream else self.format_time_hhmmss(track.duration)
        embed.add_field(name="Duration", value=duration)

        if len(player.queue) > 0:
            next_song = player.queue[0]
            embed.add_field(name="Next in queue", value=f"**{next_song.title}** by `{next_song.author}`")
        else:
            embed.add_field(name="Next in queue", value="No more songs.")

        if requester:
            embed.set_footer(text=f"Requested by {requester.display_name}", icon_url=requester.display_avatar.url)

        await channel.send(embed=embed)

    @lavalink.listener(QueueEndEvent)
    async def on_queue_end(self, event: QueueEndEvent):
        guild_id = event.player.guild_id
        guild = self.bot.get_guild(guild_id)

        channel_id = event.player.fetch('text_channel')
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            await channel.send(embed=discord.Embed(description="🏁 **End of the queue.**", color=green))

        if guild and guild.voice_client:
            await guild.voice_client.disconnect(force=True)

    # COMMANDS
    @commands.command(name='connect', aliases=['con', 'c'])
    async def connect(self, ctx):
        if not ctx.author.voice:
            return await ctx.send(
                embed=discord.Embed(color=red, description=':x: **You are not connected to a voice channel.**'))

        player = self.bot.lavalink.player_manager.create(ctx.guild.id)
        player.store('text_channel', ctx.channel.id)  # Guarda o canal para as mensagens

        if not ctx.voice_client:
            await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient, self_deaf=True)
            await ctx.send(embed=discord.Embed(color=green,
                                               description=f':white_check_mark: Connected to **{ctx.author.voice.channel.name}**.'))
        else:
            await ctx.send(embed=discord.Embed(color=blue, description=f':information_source: Already connected.'))

    @commands.command(name='disconnect', aliases=['dis', 'dc'])
    async def disconnect(self, ctx):
        if not ctx.voice_client:
            return await ctx.send(
                embed=discord.Embed(color=red, description=':x: **Not connected to any voice channel.**'))

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        player.queue.clear()
        await player.stop()

        channel_name = ctx.voice_client.channel.name
        await ctx.voice_client.disconnect(force=True)
        await ctx.send(embed=discord.Embed(color=green, description=f':wave: Disconnected from **{channel_name}**.'))

    @commands.command()
    async def play(self, ctx, *, query: str):
        if not ctx.author.voice:
            return await ctx.send(
                embed=discord.Embed(color=red, description='❌ **You are not connected to a voice channel.**'))

        # Liga automaticamente se não estiver ligado
        if not ctx.voice_client:
            await ctx.invoke(self.connect)

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        query = query.strip('<>')
        if not url_rx.match(query):
            query = f'ytsearch:{query}'  # Força a pesquisa no youtube se não for link

        search_msg = await ctx.send(f"🔍 **Searching...**", suppress_embeds=True)
        results = await player.node.get_tracks(query)

        if results.load_type == LoadType.EMPTY:
            return await search_msg.edit(content='',
                                         embed=discord.Embed(color=red, description="❌ **No results found.**"))

        embed = discord.Embed(color=green)

        if results.load_type == LoadType.PLAYLIST:
            tracks = results.tracks
            for track in tracks:
                track.extra["requester"] = ctx.author.id
                player.add(track=track)

            embed.description = f"📥 **Playlist `{results.playlist_info.name}` added with {len(tracks)} songs.**"
            await search_msg.edit(content='', embed=embed)

        else:
            track = results.tracks[0]
            track.extra["requester"] = ctx.author.id
            player.add(track=track)

            embed.description = f"📥 **{track.title}** by `{track.author}` added to the queue."
            await search_msg.edit(content='', embed=embed)

        if not player.is_playing:
            await player.play()

    @commands.command()
    async def skip(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.is_playing:
            return await ctx.send(embed=discord.Embed(description=":x: **Nothing is playing.**", color=red))

        await player.skip()
        await ctx.send(embed=discord.Embed(description="⏭️ **Song skipped.**", color=green))

    @commands.command()
    async def pause(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player and player.is_playing and not player.paused:
            await player.set_pause(True)
            await ctx.send(embed=discord.Embed(description="⏸️ **Music paused.**", color=green))

    @commands.command()
    async def resume(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player and player.paused:
            await player.set_pause(False)
            await ctx.send(embed=discord.Embed(description="▶️ **Music resumed.**", color=green))

    @commands.command(name='stop', aliases=['s'])
    async def stop(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player and (player.is_playing or player.paused):
            player.queue.clear()
            await player.stop()
            await ctx.send(embed=discord.Embed(description="⏹️ **Music stopped and queue cleared.**", color=green))

    @commands.command(name='queue', aliases=['q'])
    async def queue(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or (not player.is_playing and len(player.queue) == 0):
            return await ctx.send(embed=discord.Embed(description=":x: **The queue is empty.**", color=red))

        embed = discord.Embed(color=blue, title="🎶 Music Queue")
        if player.current:
            current = f"**{player.current.title}** by `{player.current.author}`"
            if player.current.stream:
                current += " (LIVE)"
            embed.add_field(name="Now Playing", value=current, inline=False)

        if len(player.queue) > 0:
            queue_text = ""
            for i, track in enumerate(player.queue[:10], start=1):
                queue_text += f"**{i}. {track.title}** by `{track.author}`\n"
            if len(player.queue) > 10:
                queue_text += f"... and {len(player.queue) - 10} more."
            embed.add_field(name="Up Next", value=queue_text, inline=False)

        await ctx.send(embed=embed)



async def setup(bot):
    await bot.add_cog(Music(bot))