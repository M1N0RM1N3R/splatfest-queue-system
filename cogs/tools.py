import discord
import yaml
from yaml import CBaseLoader
import dateparser

from classes import *

def iso8601_option_autocomplete(actx: discord.AutocompleteContext) -> List[str]:
    try:
        return [dateparser.parse(actx.value).replace(microsecond=0).isoformat()]
    except AttributeError:
        return []


def iso8601_option(desc): return discord.Option(
    str, description=f'{desc} (Tip: I can format natural language!)', autocomplete=iso8601_option_autocomplete)


class ToolsCog(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    root = discord.SlashCommandGroup(
        name='tools', description='Very useful tools.')

    timestamp_types = [discord.OptionChoice(name=f'{k} ({v})', value=v) for k, v in {
        'Short date and time': 'f',
        'Long date and short time': 'F',
        'Short date': 'd',
        'Long date': 'D',
        'Short time': 't',
        'Long time': 'T',
        'Relative time': 'R'
    }.items()]

    @root.command(name='timestamp', description='Convert a specified time into a Discord timestamp.')
    async def timestamp(self, ctx: discord.ApplicationContext, when: iso8601_option('The date/time to convert.'), format: discord.Option(str, description='The type of timestamp to generate.', choices=timestamp_types), ephemeral: discord.Option(bool, description='Whether to hide the result from other users.', default=True)):
        await ctx.defer(ephemeral=ephemeral)
        when = datetime.datetime.fromisoformat(when)
        result = f'<t:{int(when.timestamp())}:{format}>'.format(
            when.timestamp())
        await ctx.send_followup(f'✅ {when.isoformat()}: `{result}` (Preview: {result})', ephemeral=ephemeral)

def setup(bot: discord.Bot):
    bot.add_cog(ToolsCog(bot))