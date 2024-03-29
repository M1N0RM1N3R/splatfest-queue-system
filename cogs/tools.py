import logging
import discord
import random
from classes import *
from helpers.command_arg_types import timestamp

log = logging.getLogger(__name__)


def gen_lan_ip():
    a = random.randint(0, 255)
    b = random.randint(1, 254)
    return gen_lan_ip() if a == 37 and b == 1 else (a, b)


class ToolsCog(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    root = discord.SlashCommandGroup(name="tools", description="Very useful tools.")
    timestamp_types = [
        discord.OptionChoice(name=f"{k} ({v})", value=v)
        for k, v in {
            "Short date and time": "f",
            "Long date and short time": "F",
            "Short date": "d",
            "Long date": "D",
            "Short time": "t",
            "Long time": "T",
            "Relative time": "R",
        }.items()
    ]

    @root.command(
        name="timestamp",
        description="Convert a specified time into a Discord timestamp.",
    )
    async def timestamp(
        self,
        ctx: discord.ApplicationContext,
        when: timestamp(description="The date/time to convert."),
        format: discord.Option(
            str,
            description="The type of timestamp to generate.",
            choices=timestamp_types,
        ),
        ephemeral: bool = True,
    ):
        """Generates a Discord timestamp from a given date and time.

        Args:
            when (timestamp, optional): The date/time to convert.
            format (enum, optional): The type of timestamp to generate.
            ephemeral (bool, optional): Whether to hide the result from other users. Defaults to True.
        """
        result = f"<t:{int(when.timestamp())}:{format}>".format(when.timestamp())
        await ctx.send_response(
            f"✅ {when.isoformat()}: `{result}` (Preview: {result})", ephemeral=ephemeral
        )

    @root.command(
        name="lan-ip", description="Generate a random, valid IP for classic LAN play."
    )
    async def lan_ip(self, ctx: discord.ApplicationContext):
        """Generates a random, valid console IP address for use in a classic LAN play setup."""
        ip = gen_lan_ip()
        await ctx.send_response(f"✅ `10.13.{ip[0]}.{ip[1]}`", ephemeral=True)


def setup(bot: discord.Bot):
    bot.add_cog(ToolsCog(bot))
    log.info("Cog initialized")
