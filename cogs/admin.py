import logging
import os
import discord


from classes import *


log = logging.getLogger(__name__)


async def is_admin_or_dev(ctx: discord.ApplicationContext):
    return await ctx.author.get_role(config["admin_role"]) or await ctx.bot.is_owner(
        ctx.user
    )


class AdminCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(
        name="admin", description="Administrative stuff.", checks=[is_admin_or_dev]
    )


def setup(bot: discord.Bot):
    bot.add_cog(AdminCog(bot))

    log.info("Cog initialized")
