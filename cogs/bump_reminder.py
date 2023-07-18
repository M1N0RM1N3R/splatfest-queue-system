import datetime
import logging

import discord
import discord.ext.commands as cmd

from classes import *
from cogs.scheduled_tasks import Task
from helpers.db_handling_sdb import now
from helpers.embed_templates import EmbedStyle

log = logging.getLogger(__name__)


async def reminder_callback():
    from bot import bot
    from classes import config

    await bot.get_channel(config["bump_reminder"]["channel"]).send(
        " ".join(
            [f"<@&{role_id}>" for role_id in config["bump_reminder"]["ping_roles"]]
        ),
        embed=EmbedStyle.Reminder.value.embed(
            title="Time to bump!",
            description="Bump our server on DISBOARD by doing `/bump`.",
        ),
    )


class BumpReminderCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @cmd.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Check if message matches the criteria for a "bump done" confirmation from the DISBOARD bot
        if not all(
            [
                message.channel.id == config["bump_reminder"]["channel"],
                message.author.id == 302050872383242240,
                message.embed.image.url
                == "https://disboard.org/images/bot-command-image-bump.png",
            ]
        ):
            return

        # Schedule the next reminder for 2 hours
        next_reminder = now() + datetime.timedelta(hours=2)
        reminder = Task(
            scheduled_for=next_reminder,
            callback=reminder_callback,
            task_type="bump_reminder",
        )
        reminder.schedule()
        await reminder.store()

        # Send our own confirmation that the reminder was set
        await self.bot.get_channel(config["bump_reminder"]["channel"]).send(
            embed=EmbedStyle.Ok.value.embed(
                title="Thanks for the bump!",
                description=f"I'll remind you when the server can be bumped again, {discord.utils.format_dt(next_reminder, 'R')}.",
            )
        )


def setup(bot: discord.Bot):
    bot.add_cog(BumpReminderCog(bot))

    log.info("Cog initialized")
