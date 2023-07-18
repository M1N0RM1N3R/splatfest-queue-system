import logging
import os
from typing import Optional

import discord

from classes import *
from helpers.command_checks import StaffLevel, required_staff_level
from helpers.embed_templates import EmbedStyle

log = logging.getLogger(__name__)


class AdminCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(
        name="admin",
        description="Administrative stuff.",
        checks=[required_staff_level(StaffLevel.admin)],
    )

    @root.command()
    async def echo(
        self,
        ctx: discord.ApplicationContext,
        text: str,
        embeds: str = None,
        channel: discord.TextChannel = None,
    ):
        """Make the bot say anything, anywhere!

        Args:
            text (str): The text of the message.
            embeds (str, optional): A JSON-formatted list of embeds. See [Discord's docs](https://discord.com/developers/docs/resources/channel#embed-object) for the expected schema. Defaults to None.
            channel (TextChannel, optional): The channel to send the message in. Defaults to None.
        """
        await (channel or ctx.channel).send(text, embeds=[discord.Embed.from_dict(e) for e in json.loads(embeds)] if embeds else None)
        await ctx.respond(embed=EmbedStyle.Ok.value.embed(), ephemeral=True)


def setup(bot: discord.Bot):
    bot.add_cog(AdminCog(bot))

    log.info("Cog initialized")
