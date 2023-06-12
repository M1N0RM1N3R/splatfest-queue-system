import logging
import os
import discord
from helpers.command_checks import is_admin_or_dev


from classes import *


log = logging.getLogger(__name__)


class AdminCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(
        name="admin", description="Administrative stuff.", checks=[is_admin_or_dev]
    )


def setup(bot: discord.Bot):
    bot.add_cog(AdminCog(bot))

    log.info("Cog initialized")
