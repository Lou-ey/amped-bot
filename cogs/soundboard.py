import discord
from discord.ext import commands
import wavelink
import requests

repo_owner = "Lou-ey"
repo_name = "discord-sounds"
path = ""
branch = "main"

sound_effects = {}
api_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{path}?ref={branch}'
response = requests.get(api_url).json()

for file in response:
    if file["name"].endswith(('.mp3', '.wav', '.ogg')):
        url = f"https://cdn.jsdelivr.net/gh/{repo_owner}/{repo_name}@{branch}/{path}/{file['name']}"
        key_name = file["name"].split(".")[0]
        sound_effects[key_name] = url

class SoundSelect(discord.ui.Select):
    def __init__(self, vc: wavelink.Player, options):
        self.vc = vc
        super().__init__(
            placeholder="Escolhe um som...",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label=name) for name in options]
        )

    async def callback(self, interaction: discord.Interaction):
        sound_name = self.values[0]
        url = sound_effects[sound_name]

        if not self.vc.connected:
            await self.vc.connect(reconnect=True)

        results = await wavelink.Playable.search(url, source="http")
        if not results:
            return await interaction.response.send_message(
                f"❌ Não foi possível tocar o som **{sound_name}**", ephemeral=True
            )

        track = results[0]
        await self.vc.play(track, populate=False)
        await interaction.response.send_message(f"🔊 A tocar: **{sound_name}**", ephemeral=True)

class SoundboardView(discord.ui.View):
    def __init__(self, vc: wavelink.Player, page_size=25):
        super().__init__(timeout=None)
        self.vc = vc
        self.page_size = page_size
        self.sounds = list(sound_effects.keys())
        self.page = 0
        self.max_page = (len(self.sounds) - 1) // page_size
        self.update_view()

    def update_view(self):
        self.clear_items()
        start = self.page * self.page_size
        end = start + self.page_size
        options = self.sounds[start:end]
        self.add_item(SoundSelect(self.vc, options))

        # Botões de navegação
        if self.page > 0:
            self.add_item(PrevPageButton(self))
        if self.page < self.max_page:
            self.add_item(NextPageButton(self))

class PrevPageButton(discord.ui.Button):
    def __init__(self, view: SoundboardView):
        super().__init__(style=discord.ButtonStyle.secondary, label="⬅️ Anterior")
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        self.view_ref.page -= 1
        self.view_ref.update_view()
        await interaction.response.edit_message(view=self.view_ref)

class NextPageButton(discord.ui.Button):
    def __init__(self, view: SoundboardView):
        super().__init__(style=discord.ButtonStyle.secondary, label="Próxima ➡️")
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        self.view_ref.page += 1
        self.view_ref.update_view()
        await interaction.response.edit_message(view=self.view_ref)

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
            description="Escolhe um som no menu suspenso.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=SoundboardView(vc))

async def setup(bot):
    await bot.add_cog(Soundboard(bot))

