import discord
from discord.ext import commands
import wavelink
import aiohttp
import urllib.parse

class Lyrics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_lyrics(self, node: wavelink.Node, title: str, author: str = ""):
        """ Fetch lyrics from the LavaLyrics plugin """
        base = node.uri.rstrip('/')
        print(base)
        params = urllib.parse.urlencode({'title': title, 'author': author})
        print(params)
        url = f'{base}/v4/lyrics?{params}'

        headers = {
            'Authorization': node.password,
            'Content-Type': 'application/json'
        }

        async with node.session_id.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None

            data = await resp.json()
            return data.get('lyrics')

    @commands.command(name="lyrics")
    async def lyrics(self, ctx, *, song_name: str = None):
        """Mostra as letras da música atual ou de uma pesquisa."""
        vc: wavelink.Player = ctx.voice_client

        if song_name is None:
            if not vc or not vc.current:
                return await ctx.send("❌ There is no song currently playing and no song name was provided.")

            track = vc.current
            title = track.title
            author = track.author
            node = vc.node

            lyrics = await self.fetch_lyrics(node, title, author)

            if not lyrics:
                return await ctx.send(f"❌ Lyrics not found for **{title}** by **{author}**.")

            embed = discord.Embed(
                title=f"Lyrics for {title} by {author}",
                description=lyrics[:4000],
                color=discord.Color.blue()
            )
            embed.set_footer(
                text=author,
                icon_url=f"Requested by {ctx.author.display_avatar.url}"
            )
            return await ctx.send(embed=embed)
        else:
            results = await wavelink.Playable.search(song_name)

            if not results:
                return await ctx.send(f"❌ No results found for **{song_name}**.")

            track = results[0]
            node = vc.node if vc else list(self.bot.wavelink.nodes.values())[0]

            lyrics = await self.fetch_lyrics(node, track.title, track.author)

            if not lyrics:
                return await ctx.send(f"❌ Lyrics not found for **{track.title}** by **{track.author}**.")

            embed = discord.Embed(
                title=f"Lyrics for {track.title} by {track.author}",
                description=lyrics[:4000],
                color=discord.Color.blue()
            )
            embed.set_footer(
                text=track.author,
                icon_url=f"Requested by {ctx.author.display_avatar.url}"
            )

            return await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Lyrics(bot))
