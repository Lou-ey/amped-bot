import discord
from discord.ext import commands
import datetime

class VoiceLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = 1340390075007107083  # log channel ID
        self.voice_times = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        log_channel = discord.utils.get(member.guild.text_channels, id=self.log_channel_id)
        if not log_channel:
            return  # channel not found

        if before.channel is None and after.channel is not None:
            # the user joined a voice channel
            self.voice_times[member.id] = datetime.datetime.utcnow()
            embed = discord.Embed(
                description=f"🔊 **{member.display_name}** joined `{after.channel.name}`",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"ID: {member.id}")
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.timestamp = discord.utils.utcnow()
            await log_channel.send(embed=embed)

        elif before.channel is not None and after.channel is None:
            # the user left a voice channel
            join_time = self.voice_times.pop(member.id, None)
            embed = discord.Embed(
                description=f"🔇 **{member.display_name}** left `{before.channel.name}`",
                color=discord.Color.red()
            )
            embed.set_footer(text=f"ID: {member.id}")
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.timestamp = discord.utils.utcnow()

            if join_time:
                join_time = join_time.replace(tzinfo=None)
                duration = datetime.datetime.utcnow() - join_time
                duration_str = str(duration).split('.')[0]
                embed.add_field(name=f"Was on the {before.channel.name} for", value=duration_str, inline=False)
            await log_channel.send(embed=embed)

        elif before.channel != after.channel:
            # O utilizador mudou de canal de voz
            embed = discord.Embed(
                description=f"🔄 **{member.display_name}** change from `{before.channel.name}` to `{after.channel.name}`",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"ID: {member.id}")
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.timestamp = discord.utils.utcnow()
            await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(VoiceLogger(bot))