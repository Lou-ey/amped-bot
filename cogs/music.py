import random
import re
import discord
from discord import Embed, message
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

    def _now_playing_embed(self, track, player, requester):
        source = self.source_emoji(track.source_name)

        embed = discord.Embed(color=blue, title=f"{source}  🎶 Now Playing")
        embed.description = f"**{track.title}** by `{track.author}`"

        duration = ":red_circle: **LIVE**" if track.stream else self.format_time_hhmmss(track.duration)

        embed.add_field(name="Duration", value=duration)
        if len(player.queue) > 0:
            next_song = player.queue[0]
            embed.add_field(name="Next in queue", value=f"**{next_song.title}** by `{next_song.author}`")
        else:
            embed.add_field(name="Next in queue", value="No more songs.")

        if track.artwork_url:
            embed.set_thumbnail(url=track.artwork_url)

        if requester:
            embed.set_footer(text=f"Requested by {requester.display_name}", icon_url=requester.display_avatar.url)

        return embed

    async def start_progress_updater(self, player, track, message):
        while player.is_playing and track == player.current:
            try:
                pos = player.position
                bar = self.bar(pos, track.duration)
                requester = self.bot.get_user(track.extra.get('requester', 0))
                embed = self._now_playing_embed(track, player, requester)
                embed.add_field(name="Progress", value=f"{bar} `{self.format_time(pos)}` / `{self.format_time(track.duration)}`", inline=False)

                await message.edit(embed=embed)
                await asyncio.sleep(1)

            except discord.NotFound:
                break
            except Exception as e:
                logging.error(f"Error updating progress: {e}")
                await asyncio.sleep(1)

    # EVENTS
    @lavalink.listener(TrackStartEvent)
    async def on_track_start(self, event: TrackStartEvent):
        player = event.player
        track = event.track
        guild_id = player.guild_id

        if guild_id in self.progress_tasks:
            task = self.progress_tasks[guild_id]
            if not task.done():
                task.cancel()
                del self.progress_tasks[guild_id]

        channel_id = player.fetch('text_channel')
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        requester = self.bot.get_user(track.extra.get('requester', 0))

        # O teu Embed de Now Playing
        embed = self._now_playing_embed(track, player, requester)
        msg = await channel.send(embed=embed)

        old_task = self.progress_tasks.get(player.guild_id)
        if old_task and not old_task.done():
            old_task.cancel()

        task = asyncio.create_task(self.start_progress_updater(player, track, msg))

        self.progress_tasks[player.guild_id] = task

    @lavalink.listener(QueueEndEvent)
    async def on_queue_end(self, event: QueueEndEvent):
        guild_id = event.player.guild_id
        guild = self.bot.get_guild(guild_id)

        if guild_id in self.progress_tasks:
            task = self.progress_tasks[guild_id]
            if not task.done():
                task.cancel()

        self.progress_tasks[guild_id] = asyncio.create_task(self.inactivity_watcher(guild_id, timeout=300))

        channel_id = event.player.fetch('text_channel')
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            await channel.send(embed=discord.Embed(description="🏁 **End of the queue.**", color=green))

        #if guild and guild.voice_client:
        #    await guild.voice_client.disconnect(force=True)

    async def on_inactive_event(self, guild_id):
        player = self.lavalink.player_manager.get(guild_id)
        guild = self.bot.get_guild(guild_id)

        if not guild or not guild.voice_client:
            return

        player.queue.clear()
        await player.stop()

        await guild.voice_client.disconnect(force=True)

        channel_id = player.fetch('text_channel')
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                embed = discord.Embed(description=":wave: **Disconnected due to inactivity.**", color=blue)
                await channel.send(embed=embed)

    async def on_channel_empty(self, guild_id):
        timeout = 300  # 5 minutes
        if guild_id in self.progress_tasks:
            task = self.progress_tasks[guild_id]
            if not task.done():
                task.cancel()
        await self.inactivity_watcher(guild_id, timeout)

    async def inactivity_watcher(self, guild_id, timeout):
        await asyncio.sleep(timeout)

        player = self.lavalink.player_manager.get(guild_id)

        if player:
            await self.on_inactive_event(guild_id)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.bot.user.id:
            return

        if before.channel is not None:
            guild = before.channel.guild
            vc = guild.voice_client

            if vc and vc.channel.id == before.channel.id and len(vc.channel.members) == 1:
                await self.on_channel_empty(guild.id)

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
        # remove o embed do link
        await ctx.message.edit(suppress=True)

        shuffle = False
        if "-s" in query.lower():
            shuffle = True
            query = query.replace("-s", "").strip()

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
            p_tracks = results.tracks
            if shuffle:
                random.shuffle(p_tracks)
            for track in p_tracks:
                track.extra["requester"] = ctx.author.id
                player.add(track=track)

            playlist_added_embed = discord.Embed(
                color=green,
                description="📥 **Playlist `{results.playlist_info.name}` added with {len(p_tracks)} songs.**"
            )
            playlist_added_embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
            await search_msg.edit(content='', embed=playlist_added_embed)

            if not player.is_playing:
                await player.play()

        else:
            track = results.tracks[0]
            track.extra["requester"] = ctx.author.id
            player.add(track=track)

            if not player.is_playing:
                await player.play()
                await search_msg.delete()
            else:
                track_added_embed = discord.Embed(description = f"📥 **{track.title}** by `{track.author}` added to the queue.", color=green)

                if len(player.queue) == 1:
                    pos_text = "Next in queue"
                else:
                    pos_text = len(player.queue) - 1
                track_added_embed.add_field(name="Position in queue", value=pos_text, inline=False)
                track_added_embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                await search_msg.edit(content='', embed=track_added_embed)

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
                queue_text += f"**{i}. {track.title}** by `{track.author}`"
            if len(player.queue) > 10:
                queue_text += f"... and {len(player.queue) - 10} more."
            embed.add_field(name="Up Next", value=queue_text, inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))