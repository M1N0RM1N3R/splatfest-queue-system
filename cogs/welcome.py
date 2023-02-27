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
        self.log_channel = self.bot.get_channel(config['log_channel'])
        self.webhook = discord.Webhook.from_url(config['welcome']['webhook_url'], session=aiohttp.ClientSession())

    @cmd.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Fires when a new member joins the server.

        Args:
                member (discord.Member): The new member.
        """
        await self.webhook.send(content=config['welcome']['join_template'].format(mention=member.mention), username=invisible_username, avatar_url=config['welcome']['join_avatar'])

    @cmd.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Fires when a member leaves the server.

        Args:
                member (discord.Member): The member that just left.
        """
        await self.webhook.send(content=config['welcome']['leave_template'].format(name=member.name, discriminator=member.discriminator), username=invisible_username, avatar_url=config['welcome']['leave_avatar'])


def setup(bot: discord.Bot):
    bot.add_cog(WelcomeCog(bot))
    log.info("Welcome cog initialized")
