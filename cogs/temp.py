import logging
import discord

from classes import *

log = logging.getLogger(__name__)

totk_thread = 1106630560023052298

class TempCog(discord.Cog):

    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(name="temp",
                                     description="Temporary commands.")

    @root.command()
    async def totk(self, ctx: discord.ApplicationContext):
        """Get pinged in the TOTK spoiler thread to gain access to it.
        """
        await self.bot.get_channel(totk_thread).send(f"{ctx.author.mention} access ping")
        await ctx.send_response("✅ Pinged you in the thread.", ephemeral=True)


def setup(bot: discord.Bot):
    bot.add_cog(TempCog(bot))

    log.info("Cog initialized")
