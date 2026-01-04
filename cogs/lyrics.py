import discord
from discord.ext import commands
import wavelink
import aiohttp
import urllib.parse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Lyrics(commands.Cog):
    vc: wavelink.Player = None

    def __init__(self, bot):
        self.bot = bot

    async def fetch_lyrics_current(self, node: wavelink.Node, session_id: str, guild_id: int):
        """ Fetch lyrics from the LavaLyrics plugin """
        url = (
            f"{node.uri}/v4/sessions/{session_id}"
            f"/players/{guild_id}/track/lyrics"
        )

        headers = {
            'Authorization': node.password,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 204:
                    return None
                if resp.status != 200:
                    raise RuntimeError(f"LavaLyrics error: {resp.status}")

                return await resp.json()

    async def fetch_lyrics_encoded(self, node: wavelink.Node, encoded_track: str):
        """ Fetch lyrics from the LavaLyrics plugin using encoded track """
        url = f"{node.uri}/v4/lyrics"

        headers = {
            'Authorization': node.password,
        }

        params = {
            'track': encoded_track,
            'skipTrackSource': 'true'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 204:
                    return None
                if resp.status != 200:
                    raise RuntimeError(f"LavaLyrics error: {resp.status}")

                return await resp.json()

    @commands.command(name="lyrics")
    async def lyrics(self, ctx, *, song_name: str = None):
        """Mostra as letras da música atual ou de uma pesquisa."""
        vc: wavelink.Player = ctx.voice_client

        if not vc or not vc.current:
            await ctx.send("❌ I'm not connected to a voice channel or no song is currently playing.")
            return

        node = vc.node

        if song_name is None:
            lyrics = await self.fetch_lyrics_current(
                node,
                vc.node.session_id,
                vc.guild.id
            )
            track = vc.current
        else:
            results = await wavelink.Playable.search(song_name)
            if not results:
                await ctx.send(f"❌ No results found for **{song_name}**.")
                return

            track = results[0]
            lyrics = await self.fetch_lyrics_encoded(node, track.encoded)

        if not lyrics or not lyrics.get('lines'):
            await ctx.send(f"❌ Lyrics not found for **{track.title}** by) **{track.author}**.")
            return

        text = "\n".join(line["line"] for line in lyrics['lines'][:25])

        embed = discord.Embed(
            title=f"Lyrics for {track.title} by {track.author}",
            description=f"```{text}```",
            color=discord.Color.blue()
        )

        author = ctx.author

        embed.set_footer(
            text=author.name,
            icon_url=f"Requested by {ctx.author.display_avatar.url}"
        )


async def setup(bot):
    await bot.add_cog(Lyrics(bot))
