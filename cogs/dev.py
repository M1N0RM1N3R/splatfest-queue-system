import logging
import discord

from classes import *

log = logging.getLogger(__name__)

async def is_owner(
    ctx: discord.ApplicationContext): return await ctx.bot.is_owner(ctx.user)


class DevCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(
        name='dev', description='Internal commands restricted to M1N3R only.', checks=[is_owner])

    @root.command(name='execute')
    async def execute(self, ctx: discord.ApplicationContext, script: str):
        await ctx.defer(ephemeral=True)
        output = str(eval(script) or '✅')
        for i in range(0, len(output), 2000):
            await ctx.send_followup(output[i:i+2000], ephemeral=True)


def setup(bot: discord.Bot):
    bot.add_cog(DevCog(bot))
    log.info("Dev cog initialized")
