import datetime
import discord
from discord.ext import commands
import wavelink
import time

green = 0x00FF00
red = 0xFF0000
blue = 0x0080FF

class Music(commands.Cog):
    vc: wavelink.Player = None

    def __init__(self, bot):
        self.bot = bot

    async def setup(self):
        nodes = [wavelink.Node(
            identifier='MAIN',
            uri='http://localhost:2333',
            password='luisito'
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

    @commands.command()
    async def play(self, ctx, *, query: str):
        if not ctx.voice_client:
            await ctx.invoke(self.connect)  # Conectar ao canal de voz se necessário

        vc: wavelink.Player = ctx.voice_client

        if not query:
            return await ctx.send(
                embed=discord.Embed(color=red, description="❌ **Please provide a song name or URL to play.**")
            )

        tracks: wavelink.Search = await wavelink.Playable.search(query)
        if not tracks:
            return await ctx.send(embed=discord.Embed(color=red, description=f"❌ **No results found for `{query}`.**"))

        msg = await ctx.send(f"🔍 **Searching for** `{query}`...")

        if isinstance(tracks, wavelink.Playlist):
            # Adiciona todas as músicas à fila
            for track in tracks.tracks:
                await vc.queue.put_wait(track)

            embed = discord.Embed(color=green,
                                  description=f"📥 **Playlist `{tracks.name}` added to queue with {len(tracks.tracks)} songs.**")
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            await msg.edit(content='', embed=embed)

            # Se não estiver a tocar, toca a primeira música da playlist
            if not vc.playing:
                track: wavelink.Playable = tracks.tracks[0]
                await vc.play(track)
                embed = self._now_playing_embed(track, ctx)

        else: # Se for apenas uma música
            track: wavelink.Playable = tracks[0]
            if not vc.playing: # Toca a música
                await vc.play(track)
                embed = self._now_playing_embed(track, ctx)
                #await msg.edit(content='', embed=embed)
            else: # Adiciona à fila
                await vc.queue.put_wait(track)
                embed = discord.Embed(color=green, description=f"📥 **{track.title}** added to the queue.")
                embed.set_footer(text=f"Requested by {ctx.author.display_name}")

        await msg.edit(content='', embed=embed)
        #await ctx.send(embed=embed)

    def _now_playing_embed(self, track, ctx):
        """Cria um embed para a música que está a tocar."""
        source = self.source_emoji(track.source)
        embed = discord.Embed(color=blue, title=f"{source}  🎶 Now Playing")
        embed.description = f"**{track.title}** by `{track.author}`"

        duration = ":red_circle: **LIVE**" if track.is_stream else time.strftime('%H:%M:%S',
                                                                                 time.gmtime(track.length / 1000))
        embed.add_field(name="Duration", value=duration)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")

        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        return embed

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        vc: wavelink.Player = payload.player
        source = self.source_emoji(payload.track.source)

        if vc.queue.is_empty and vc.auto_queue:
            track = vc.auto_queue.get()
            await vc.play(track)
            embed = self._now_playing_embed(track, vc.text_channel)
            await vc.text_channel.send(embed=embed)

        if not vc.queue.is_empty:
            next_track = await vc.queue.get_wait()
            await vc.play(next_track)

            embed = discord.Embed(color=blue, title=f"{source}  🎶 Now Playing")
            embed.description = f"**{next_track.title}** by `{next_track.author}`"
            duration = time.strftime('%H:%M:%S', time.gmtime(next_track.length / 1000))
            embed.add_field(name="Duration", value=duration)

            if next_track.artwork:
                embed.set_thumbnail(url=next_track.artwork)
            await vc.text_channel.send(embed=embed)
        else:
            embed = discord.Embed(description="🏁 **End of the queue.**", color=green)
            await vc.text_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        await player.disconnect(force=True)
        embed = discord.Embed(description="🏁 **Disconnected due to inactivity.**", color=green)
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

        if not vc or vc.queue.is_empty:
            embed.description = '📭 **The queue is empty.**'
            await ctx.send(embed=embed)
            return

        queue_list = list(vc.queue.copy())
        description = '\n'.join(f"**{i + 1}.** {track.title}" for i, track in enumerate(queue_list[:len(queue_list)]))
        embed.title = f'📜 Queue ({len(queue_list)} songs)'
        embed.description = description
        await ctx.send(embed=embed)

    #@commands.command()
    #async def autoplay(self, ctx, mode: str = 'enabled'):
        #if not ctx.voice_client:
            #return await ctx.send(embed=discord.Embed(color=red, description=":x: **Not connected to any voice channel.**"))

        #vc: wavelink.Player = ctx.voice_client

        #modes = {
            #'enabled': wavelink.AutoPlayMode.enabled,
            #'partial': wavelink.AutoPlayMode.partial,
            #'disabled': wavelink.AutoPlayMode.disabled
        #}

        #if mode.lower() not in modes:
            #return await ctx.send(embed=discord.Embed(color=red, description=":x: **Invalid mode.**"))

        #vc.autoplay = modes[mode.lower()]
        #embed = discord.Embed(color=green, description=f"🔀 **Autoplay mode set to** `{mode.lower()}`.")
        #await ctx.send(embed=embed)

    @commands.command()
    async def autoplay(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc:
            return await ctx.send(
                embed=discord.Embed(color=red, description="❌ **Bot is not connected to a voice channel.**"))

        vc.auto_play = wavelink.AutoPlayMode.enabled

        embed = discord.Embed(description="🔄 **Autoplay enabled.**", color=green)
        await ctx.send(embed=embed)

async def setup(bot):
    play_music = Music(bot)
    await bot.add_cog(play_music)
    await play_music.setup()
