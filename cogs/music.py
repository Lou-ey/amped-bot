import discord
from discord import Embed, message
from discord.ext import commands
import wavelink
import time
import asyncio
from datetime import timedelta
from dotenv import load_dotenv
import os

load_dotenv()
PASSWORD = os.getenv("PASSWORD")

green = 0x00FF00
red = 0xFF0000
blue = 0x0080FF

def format_time(ms):
    return str(timedelta(milliseconds=ms))[2:7]

def generate_progress_bar(current, total, length=20):
    if total <= 0:
        proportion = 0
    else:
        if total - current <= 1000:
            proportion = 1
        else:
            proportion = current / total

    exact_filled = length * proportion
    filled_length = int(exact_filled)
    remainder = exact_filled - filled_length

    has_partial = remainder >= 0.5

    empty = length - filled_length - (1 if has_partial else 0)

    return '⌈' + '█' * filled_length + ('▒' if has_partial else '') + '░' * empty + '⌉'

class Music(commands.Cog):
    vc: wavelink.Player = None

    def __init__(self, bot):
        self.bot = bot

    async def setup(self):
        nodes = [wavelink.Node(
            identifier='MAIN',
            uri='http://localhost:2333',
            password=PASSWORD,
        )]
        await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=100)

    async def setup_hook(self):
        await self.setup()

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        print(f"\n{payload.node!r} is ready!")

    @commands.command(name='connect', aliases=['con', 'c'])
    async def connect(self, ctx):
        g_embed = discord.Embed(color=green)
        r_embed = discord.Embed(color=red)
        if not ctx.author.voice:
            r_embed.description = ':x: **You are not connected to a voice channel.**'
            await ctx.send(embed=r_embed)
            return

        channel = ctx.author.voice.channel
        if ctx.voice_client:
            r_embed.description = f':information_source: Already connected to **{ctx.voice_client.channel.name}**.'
        else:
            self.vc = await channel.connect(cls=wavelink.Player)
            self.vc.text_channel = ctx.channel
            g_embed.description = f':white_check_mark: Connected to **{channel.name}**.'
        await ctx.send(embed=g_embed)

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        print(f"Error while playing track: {payload.exception}")
        r_embed = discord.Embed(color=red)
        r_embed.description = ':x: **An error occurred while trying to play the track.**'
        await payload.player.text_channel.send(embed=r_embed)

    @commands.command(name='disconnect', aliases=['dis', 'dc'])
    async def disconnect(self, ctx):
        g_embed = discord.Embed(color=green)
        r_embed = discord.Embed(color=red)
        if ctx.voice_client:
            channel = ctx.voice_client.channel
            await ctx.voice_client.disconnect()
            g_embed.description = f':wave: Disconnected from **{channel.name}**.'
        else:
            r_embed.description = ':x: **Not connected to any voice channel.**'
        await ctx.send(embed=g_embed)

    @staticmethod
    def source_emoji(source: str):
        if source == 'youtube':
            return '<:youtube:1304468389883809813>'
        elif source == 'spotify':
            return '<:spotify:1304468005102555206>'
        elif source == 'soundcloud':
            return '<:soundcloud:1305561757653139506>'
        return ''

    async def start_progress_updater(self, vc: wavelink.Player, track, message):
        while vc.playing and track == vc.current:
            pos = vc.position
            bar = generate_progress_bar(pos, track.length)
            requester = getattr(vc, "current_requester", None)
            embed = self._now_playing_embed(track, vc, requester)
            embed.add_field(
                name="Progress",
                value=f"{bar}\n`{format_time(pos)} / {format_time(track.length)}`",
                inline=False
            )

            try:
                await message.edit(embed=embed)
            except discord.NotFound:
                print('Mensagem apagada.')
                break

            await asyncio.sleep(1)

    @commands.command()
    async def play(self, ctx, *, query: str):
        await ctx.message.edit(suppress=True)
        if not ctx.voice_client:
            try:
                await ctx.invoke(self.connect)
            except Exception as e:
                return await ctx.send(
                    embed=discord.Embed(
                        color=red,
                        description=f"❌ **Failed to connect to the voice channel.**\n`{str(e)}`"
                    )
                )

        vc: wavelink.Player = ctx.voice_client

        if not query:
            return await ctx.send(
                embed=discord.Embed(
                    color=red,
                    description="❌ **Please provide a song name or URL to play.**"
                )
            )

        search_msg = await ctx.send(f"🔍 **Searching for** `{query}`...", suppress_embeds=True)

        tracks: wavelink.Search = await wavelink.Playable.search(query)
        if not tracks:
            return await search_msg.edit(
                content='',
                embed=discord.Embed(
                    color=red,
                    description=f"❌ **No results found for `{query}`.**"
                )
            )

        if isinstance(tracks, wavelink.Playlist):

            # Adiciona todas as músicas à fila
            for track in tracks.tracks:
                track.requester = ctx.author
                await vc.queue.put_wait(track)

            playlist_added_embed = discord.Embed(
                color=green,
                description=f"📥 **Playlist `{tracks.name}` added to queue with {len(tracks.tracks)} songs.**"
            )
            playlist_added_embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
            await search_msg.edit(content='', embed=playlist_added_embed)

            if not vc.playing:
                first_track = await vc.queue.get_wait()
                vc.current_requester = getattr(first_track, "requester", ctx.author)
                await vc.play(first_track)

        else:
            track: wavelink.Playable = tracks[0]
            track.requester = ctx.author
            vc.current_requester = ctx.author
            track.position_in_queue = vc.queue.count + (1 if vc.current else 0)

            if not vc.playing:
                await vc.play(track)
                await search_msg.delete()

            else:
                await vc.queue.put_wait(track)
                track_added_embed = discord.Embed(
                    color=green,
                    description=f"📥 **{track.title}** by `{track.author}` added to the queue."
                )

                if vc.queue.count == 1:
                    pos_text = "Next in queue"
                else:
                    pos_text = f"{track.position_in_queue}"
                track_added_embed.add_field(name="Position in queue", value=pos_text)

                track_added_embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                await search_msg.edit(content='', embed=track_added_embed)

    def _now_playing_embed(self, track, vc, requester):
        """Cria um embed para a música que está a tocar."""
        source = self.source_emoji(track.source)

        embed = discord.Embed(color=blue, title=f"{source}  🎶 Now Playing")
        embed.description = f"**{track.title}** by `{track.author}`"

        duration = ":red_circle: **LIVE**" if track.is_stream else time.strftime('%H:%M:%S',
                                                                                 time.gmtime(track.length / 1000))
        embed.add_field(name="Duration", value=duration)
        if vc.queue.count > 0 or vc.auto_queue.count > 0:
            next_song = vc.queue.peek(0) if vc.queue.count > 0 else vc.auto_queue.peek(0)
            embed.add_field(name="Next in queue", value=f"**{next_song.title}** by `{next_song.author}`")
        else:
            embed.add_field(name="Next in queue", value="No more songs in the queue.")

        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        if requester:
            embed.set_footer(text=f"Requested by {requester.display_name}", icon_url=requester.display_avatar.url)

        return embed

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        vc: wavelink.Player = payload.player

        if not vc.queue.is_empty:
            next_track = await vc.queue.get_wait()
            next_track.position_in_queue = vc.queue.count + 1
            vc.current_requester = getattr(next_track, "requester", None)
            await vc.play(next_track)

        elif vc.autoplay == wavelink.AutoPlayMode.enabled:
            if vc.auto_queue.is_empty:
                # pede já a próxima recomendação
                next_track = await vc.auto_queue.get_wait()

                if vc.playing and vc.auto_queue.count > 0:
                    await vc.auto_queue.put_wait(next_track)
                else:
                    next_track.position_in_queue = vc.auto_queue.count + 1
                    vc.current_requester = getattr(next_track, "requester", None)
                    await vc.play(next_track)
            else:
                if vc.playing:
                    next_track = await vc.auto_queue.get_wait()
                    await vc.auto_queue.put_wait(next_track)
                else:
                    next_track = await vc.auto_queue.get_wait()
                    next_track.position_in_queue = vc.auto_queue.count + 1
                    vc.current_requester = getattr(next_track, "requester", None)
                    await vc.play(next_track)

        else:
            await vc.text_channel.send(
                embed=discord.Embed(description="🏁 **End of the queue.**", color=green)
            )

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):

        vc: wavelink.Player = payload.player
        track = payload.track

        requester = getattr(vc, "current_requester", None) or getattr(track, "requester", None)
        #if requester is None:
        #    requester = getattr(track, "requester", None)

        embed = self._now_playing_embed(track, vc, requester)
        msg = await vc.text_channel.send(embed=embed)
        asyncio.create_task(self.start_progress_updater(vc, track, msg))

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        await player.disconnect(force=True)
        embed = discord.Embed(description=":wave: **Disconnected due to inactivity.**", color=green)
        await player.text_channel.send(embed=embed)

    @commands.command()
    async def pause(self, ctx):
        if self.vc and self.vc.playing:
            await self.vc.pause(True)
            embed = discord.Embed(description="⏸️ **Music paused.**", color=green)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(description=":x: **Nothing is currently playing.**", color=red)
            await ctx.send(embed=embed)

    @commands.command()
    async def resume(self, ctx):
        if self.vc and self.vc.paused:
            await self.vc.pause(False)
            embed = discord.Embed(description="▶️ **Music resumed.**", color=green)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(description=":x: **The music is not paused.**", color=red)
            await ctx.send(embed=embed)

    @commands.command()
    async def stop(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if vc and vc.playing:
            vc.queue.clear()
            vc.auto_queue.clear()
            vc.auto_play = wavelink.AutoPlayMode.disabled
            await vc.stop(force=True)
            embed = discord.Embed(description="⏹️ **Music stopped.**", color=green)
            await ctx.send(embed=embed)

    @commands.command(name='skip', aliases=['s', 'next'])
    async def skip(self, ctx):
        player: wavelink.Player = ctx.voice_client
        if player and player.queue.is_empty:
            embed = discord.Embed(description=":x: **The queue is empty.**", color=red)
            await ctx.send(embed=embed)
            return
        await player.skip()
        embed = discord.Embed(description="⏭️ **Song skipped.**", color=green)
        await ctx.send(embed=embed)

    @commands.command()
    async def queue(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        embed = discord.Embed(color=green)

        if not vc or (vc.queue.is_empty and vc.auto_queue.is_empty):
            embed.description = '📭 **The queue is empty.**'
            await ctx.send(embed=embed)
            return

        description = ""

        # Queue normal
        if not vc.queue.is_empty:
            queue_list = list(vc.queue.copy())
            description += "**🎶 Normal Queue:**\n"
            description += '\n'.join(f"**{i + 1}.** {track.title}" for i, track in enumerate(queue_list[:50]))
            description += "\n\n"

        # Auto Queue
        if not vc.auto_queue.is_empty:
            auto_queue_list = list(vc.auto_queue.copy())
            description += "**🤖 Auto Queue:**\n"
            description += '\n'.join(f"**{i + 1}.** {track.title}" for i, track in enumerate(auto_queue_list[:50]))

        embed.title = f'📜 Combined Queue'
        embed.description = description.strip()
        await ctx.send(embed=embed)

    @commands.command()
    async def autoplay(self, ctx, mode: str = None):
        vc: wavelink.Player = ctx.voice_client
        if not vc:
            return await ctx.send(
                embed=discord.Embed(color=red, description="❌ **Bot is not connected to a voice channel.**")
            )

        if not mode:
            # Mostrar estado atual
            current = vc.autoplay.name.capitalize()
            return await ctx.send(
                embed=discord.Embed(color=blue, description=f"ℹ️ **Autoplay is currently:** `{current}`")
            )

        mode = mode.lower()
        if mode in ["on", "enabled", "enable"]:
            vc.autoplay = wavelink.AutoPlayMode.enabled
            msg = "🔄 **Autoplay enabled (recommended tracks will auto-play).**"
            color = green
        elif mode in ["partial"]:
            vc.autoplay = wavelink.AutoPlayMode.partial
            msg = "🟡 **Autoplay set to partial (manual handling of recommended tracks).**"
            color = blue
        elif mode in ["off", "disabled", "disable"]:
            vc.autoplay = wavelink.AutoPlayMode.disabled
            msg = "⛔ **Autoplay disabled.**"
            color = red
        else:
            return await ctx.send(
                embed=discord.Embed(color=red,
                                    description="⚠️ Use `!autoplay on`, `!autoplay partial`, or `!autoplay off`.")
            )

        await ctx.send(embed=discord.Embed(color=color, description=msg))

async def setup(bot):
    play_music = Music(bot)
    await bot.add_cog(play_music)
    await play_music.setup()
