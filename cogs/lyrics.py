import discord
from discord.ext import commands
import lavalink
import aiohttp
import logging

# Configuração básica de logs
_log = logging.getLogger(__name__)


class Lyrics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_lyrics_current(self, node, player):
        """ Procura letras para a música que está a tocar agora no player. """
        # No Lavalink.py, o node.base_uri já inclui http://host:port
        # O endpoint do plugin LavaLyrics é /v4/sessions/{session}/players/{guild}/track/lyrics
        url = f"{node.base_uri}/v4/sessions/{node.session_id}/players/{player.guild_id}/track/lyrics"

        headers = {
            'Authorization': node.password,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()

    async def fetch_lyrics_encoded(self, node, encoded_track: str):
        """ Procura letras usando o base64 da track. """
        url = f"{node.base_uri}/v4/lyrics"

        headers = {
            'Authorization': node.password,
        }
        params = {
            'track': encoded_track,
            'skipTrackSource': 'true'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()

    @commands.command(name="lyrics")
    async def lyrics(self, ctx, *, song_name: str = None):
        """Mostra as letras da música atual ou de uma pesquisa."""
        # Obtém o player do Lavalink.py para este servidor
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player or not player.is_connected:
            return await ctx.send("❌ Não estou num canal de voz.")

        node = player.node

        # Cenário 1: O utilizador não deu nome, procuramos a música atual
        if song_name is None:
            if not player.current:
                return await ctx.send("❌ Não está a tocar nada agora.")

            track = player.current
            lyrics_data = await self.fetch_lyrics_current(node, player)

        # Cenário 2: O utilizador quer pesquisar uma música específica
        else:
            # Pesquisa no Lavalink
            results = await node.get_tracks(f"ytsearch:{song_name}")
            if not results or not results.tracks:
                return await ctx.send(f"❌ Sem resultados para: **{song_name}**")

            track = results.tracks[0]
            lyrics_data = await self.fetch_lyrics_encoded(node, track.track)  # track.track é o base64

        # Verificação se as letras foram encontradas
        if not lyrics_data or 'lines' not in lyrics_data:
            return await ctx.send(f"❌ Letras não encontradas para: **{track.title}**")

        # Formata as primeiras 25 linhas (para não estourar o limite de caracteres do Discord)
        lines = lyrics_data['lines']
        text = "\n".join([line['line'] for line in lines[:25] if line.get('line')])

        embed = discord.Embed(
            title=f"Lyrics: {track.title}",
            url=track.uri,
            description=f"```\n{text}\n```",
            color=discord.Color.blue()
        )

        # Corrigido o erro do icon_url (não se pode meter texto dentro do icon_url)
        embed.set_footer(
            text=f"Requisitado por {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url
        )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Lyrics(bot))