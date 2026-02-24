from datetime import timedelta
import os
import sys
import discord

class Utils:
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def format_time(ms: int) -> str:
        return str(timedelta(milliseconds=ms))[2:7]

    @staticmethod
    def format_time_hhmmss(ms: int) -> str:
        total_seconds = ms // 1000

        days = total_seconds // 86400
        remainder = total_seconds % 86400

        hours = remainder // 3600
        minutes = (remainder % 3600) // 60
        seconds = remainder % 60

        if days > 0:
            return f"{days}d {hours:02}:{minutes:02}:{seconds:02}"

        return f"{hours:02}:{minutes:02}:{seconds:02}"

    @staticmethod
    def generate_progress_bar(current: int, total: int, length: int = 20) -> str:
        if total <= 0:
            proportion = 0
        else:
            proportion = 1 if total - current <= 1000 else current / total

        exact = length * proportion
        filled = int(exact)
        remainder = exact - filled

        partial = remainder >= 0.5
        empty = length - filled - (1 if partial else 0)

        return '⌈' + '█' * filled + ('▒' if partial else '') + '░' * empty + '⌉'

    @staticmethod
    async def paginate(ctx, items, title=None, per_page=10):
        pages = [
            items[i:i + per_page]
            for i in range(0, len(items), per_page)
        ]

        view = PaginationView(ctx, pages, title=title)
        await ctx.send(embed=view.make_embed(), view=view)

    # UNUSED FUNCTION FOR TESTING PURPOSES
    '''
    async def terminal_commanding(self, logging):
        disabled_cogs = os.getenv('DISABLED_COGS', '').split(',') if os.getenv('DISABLED_COGS') else []

        while True:
            command = input('Enter a command (exit, cogs, help, reset): ').strip()

            if command == 'exit':
                logging.info('Shutting down the bot...')
                await self.bot.close()
                break

            elif command == 'cogs':
                logging.info('Cogs currently loaded:')
                for ext in self.bot.extensions:
                    logging.info(f'- {ext}')

                subcommand = input('Enter (load, unload, back): ').strip()

                if subcommand == 'back':
                    continue

                elif subcommand == 'load':
                    cog = input('Cog name: ').strip()
                    if not cog:
                        continue

                    name = f'cogs.{cog}'

                    try:
                        await self.bot.load_extension(name)
                        logging.info(f'Loaded {cog}')
                    except Exception as e:
                        logging.error(e)

                elif subcommand == 'unload':
                    cog = input('Cog name: ').strip()
                    if not cog:
                        continue

                    name = f'cogs.{cog}'

                    try:
                        await self.bot.unload_extension(name)
                        logging.info(f'Unloaded {cog}')
                    except Exception as e:
                        logging.error(e)

            elif command == 'help':
                logging.info('exit | cogs | help | reset')

            elif command == 'reset':
                logging.info('Restarting...')
                await self.bot.close()
                os.execv(sys.executable, ['python'] + sys.argv)
'''

class PaginationView(discord.ui.View):
    def __init__(self, ctx, pages, title=None, timeout=60):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.pages = pages
        self.title = title
        self.current = 0

    def make_embed(self):
        embed = discord.Embed(
            title=self.title,
            description="\n".join(self.pages[self.current]),
            color=0x00FF00
        )
        embed.set_footer(text=f"Page {self.current + 1}/{len(self.pages)}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "❌ Só quem executou o comando pode usar os botões.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = (self.current - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = (self.current + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)
