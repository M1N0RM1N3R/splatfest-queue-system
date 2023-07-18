import logging

import discord


from cogs.scheduled_tasks import Task
from helpers.command_arg_types import timedelta
from helpers.db_handling_sdb import now

log = logging.getLogger(__name__)


async def pong(channel_id: int, text: str):
    from bot import bot

    await bot.get_channel(channel_id).send(text)


class TempCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(name="temp", description="Temporary commands.")

    @root.command()
    async def scheduler_test(
        self, ctx: discord.ApplicationContext, text: str, delay: timedelta()
    ):
        s = now() + delay
        t = Task(scheduled_for=s, callback=pong, args=[ctx.channel.id, text])
        t.schedule()
        await t.store()
        await ctx.respond(f"I will say '{text}' {discord.utils.format_dt(s, 'R')}")


def setup(bot: discord.Bot):
    bot.add_cog(TempCog(bot))

    log.info("Cog initialized")
