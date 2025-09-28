import os
import discord
from discord.ext import commands
import wavelink
import requests

repo_owner = "Lou-ey" # os.environ['REPO_OWNER']
repo_name = "discord-sounds" # os.environ['REPO_NAME']
path = ""
token = None # os.environ['TOKEN']
branch = "main"

sound_effects = {}

api_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{path}?ref={branch}'
response = requests.get(api_url).json()

for file in response:
    if file["name"].endswith(('.mp3', '.wav', '.ogg')):
        url = f"https://cdn.jsdelivr.net/gh/{repo_owner}/{repo_name}@{branch}/{path}/{file['name']}"
        key_name = file["name"].split(".")[0]
        sound_effects[key_name] = url

print(sound_effects)

class SoundboardView(discord.ui.View):
    def __init__(self, vc: wavelink.Player):
        super().__init__(timeout=None)
        self.vc = vc

        # Adiciona botão para cada som
        for name, url in sound_effects.items():
            self.add_item(SoundButton(label=name, sound_url=url, vc=vc))

        # Botão de parar
        self.add_item(StopSoundButton(vc))


class SoundButton(discord.ui.Button):
    def __init__(self, label: str, sound_url: str, vc: wavelink.Player):
        super().__init__(style=discord.ButtonStyle.primary, label=label)
        self.sound_url = sound_url
        self.vc = vc

    async def callback(self, interaction: discord.Interaction):
        # Toca o som escolhido
        if not self.vc.connected:
            await self.vc.connect(reconnect=True)

        results = await wavelink.Playable.search(self.sound_url, source="http")
        if not results:
            return await interaction.response.send_message(
                f"❌ Não foi possível encontrar o som **{self.label}**", ephemeral=True
            )

        track = results[0]
        await self.vc.play(track, populate=False)

        await interaction.response.send_message(
            f"🔊 A tocar: **{self.label}**", ephemeral=True
        )


class StopSoundButton(discord.ui.Button):
    def __init__(self, vc: wavelink.Player):
        super().__init__(style=discord.ButtonStyle.danger, label="⏹️ Parar Som")
        self.vc = vc

    async def callback(self, interaction: discord.Interaction):
        await self.vc.stop()
        await interaction.response.send_message("⏹️ Som parado.", ephemeral=True)


class Soundboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="soundboard")
    async def soundboard(self, ctx):
        if not ctx.voice_client:
            await ctx.invoke(ctx.bot.get_command("connect"))

        vc: wavelink.Player = ctx.voice_client
        if not vc:
            return await ctx.send("❌ O bot não está num canal de voz.")

        embed = discord.Embed(
            title="🔊 Soundboard",
            description="Clica num botão para tocar o som.",
            color=discord.Color.blue()
        )

        await ctx.send(embed=embed, view=SoundboardView(vc))


async def setup(bot):
    await bot.add_cog(Soundboard(bot))
