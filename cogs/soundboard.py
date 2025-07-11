import discord
from discord.ext import commands
import wavelink
import asyncio
import random

from discord.ext.commands import bot

sound_effects = {
    "pi": "https://cdn.jsdelivr.net/gh/Lou-ey/discord-sounds@main/smokeAlarm.mp3",
    "teste": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
    "teste2": "https://cdn.jsdelivr.net/gh/Lou-ey/discord-sounds@main/service-bell_daniel_simion.mp3"
}

loop_tasks = {}  # guardar tasks por guild


class SoundboardView(discord.ui.View):
    def __init__(self, vc: wavelink.Player, bot):
        super().__init__(timeout=None)
        self.vc = vc
        self.bot = bot

        for name, url in sound_effects.items():
            self.add_item(SoundLoopButton(label=name, sound_url=url, vc=vc, bot=bot))

        self.add_item(StopSoundButton(vc=vc, bot=bot))


class SoundLoopButton(discord.ui.Button):
    def __init__(self, label: str, sound_url: str, vc: wavelink.Player, bot):
        super().__init__(style=discord.ButtonStyle.primary, label=label)
        self.sound_url = sound_url
        self.vc = vc
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id

        # Cancela qualquer loop anterior
        if guild_id in loop_tasks:
            loop_tasks[guild_id].cancel()
            del loop_tasks[guild_id]

        channel = interaction.channel

        async def play_loop():
            while True:
                try:
                    if not self.vc.connected:
                        await self.vc.connect(reconnect=True)

                    results = await wavelink.Playable.search(self.sound_url, source="http")
                    if not results:
                        print(f"❌ Não foi possível encontrar o som: {self.label}")
                        return

                    track = results[0]

                    await self.vc.play(track, populate=False)
                    # track.extras["is_soundboard"] = True  # Marca como soundboard
                    # Envia mensagem a cada execução
                    await interaction.followup.send(f"🔁 Em loop: **{self.label}** com intervalos aleatórios", ephemeral=True)

                    while self.vc.playing:
                        await asyncio.sleep(1)

                    await asyncio.sleep(random.uniform(1, 1000))

                except Exception as e:
                    print(f"Erro no loop do som: {e}")
                    break

        print(loop_tasks)
        # Resposta inicial
        await interaction.response.defer(ephemeral=True)

        # Inicia a task e guarda no dicionário
        task = self.bot.loop.create_task(play_loop())
        loop_tasks[guild_id] = task

        await interaction.followup.send(
            f"🔁 Em loop: **{self.label}** com intervalos aleatórios", ephemeral=True
        )

@bot.Cog.listener()
async def on_wavelink_queue_end(payload: wavelink.TrackEndEventPayload):
    guild_id = payload.player.guild.id

    # Ignora se estiver a tocar em loop manual
    if guild_id in loop_tasks:
        return

    channel = payload.player.guild.system_channel  # ou outro canal adequado
    if channel:
        await channel.send("📭 End of the queue!")


class StopSoundButton(discord.ui.Button):
    def __init__(self, vc: wavelink.Player, bot):
        super().__init__(style=discord.ButtonStyle.danger, label="⏹️ Parar")
        self.vc = vc
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id

        if guild_id in loop_tasks:
            loop_tasks[guild_id].cancel()
            del loop_tasks[guild_id]

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

        embed = discord.Embed(title="🔊 Soundboard", description="Clica num botão para tocar com repetição aleatória.", color=discord.Color.blue())
        await ctx.send(embed=embed, view=SoundboardView(vc, self.bot))



async def setup(bot):
    await bot.add_cog(Soundboard(bot))