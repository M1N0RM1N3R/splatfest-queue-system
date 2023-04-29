import logging

import discord
import discord.ext.commands as cmd
from aiohttp import client as aiohttp

from classes import *

log = logging.getLogger(__name__)

# https://beebom.com/how-get-invisible-discord-name-and-avatar/
invisible_username = "᲼᲼"


class WelcomeCog(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot
        self.log_channel = self.bot.get_channel(config["log_channel"])

    @cmd.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Fires when a new member joins the server.

        Args:
                member (discord.Member): The new member.
        """
        await webhook.send(
            content=f"<a:Booyah:847300266566746153> {member.mention} joined **Splatfest!**\nCheck out Anarchy Splatcast! <:splatfest:1024053687217295460> <:splatlove:1057108266062196827>",
            username=invisible_username,
            avatar_url="https://cdn.discordapp.com/attachments/1066917293935841340/1079624383410216970/Picsart_22-10-18_17-30-36-248.png",
        )

    @cmd.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Fires when a member leaves the server.

        Args:
                member (discord.Member): The member that just left.
        """
        await webhook.send(
            content=f"<a:Ouch:847300319071043604> {member} just left **Splatfest...**\n<a:1member:803768545816084480> <:splatbroke:1057109111097004103>",
            username=invisible_username,
            avatar_url="https://cdn.discordapp.com/attachments/1066917293935841340/1079624383804493864/Picsart_22-10-18_21-30-54-748.png",
        )


def setup(bot: discord.Bot):
    bot.add_cog(WelcomeCog(bot))
    global webhook
    webhook = discord.Webhook.from_url(
        secrets["welcome_webhook"], session=aiohttp.ClientSession()
    )
    log.info("Cog initialized")


def teardown(bot: discord.Bot):
    asyncio.get_event_loop().run_until_complete(webhook.session.close())
    log.info("Cog closed")
