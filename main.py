import logging
import os
from typing import Any

from discord.ext import tasks

from bot import bot
from classes import *
from helpers.discord_logger import DiscordLogHandler

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(module)s:%(lineno)d   %(message)s",
)
logging.getLogger().addHandler(
    DiscordLogHandler(bot, config["log_channel"], level=logging.WARNING)
)
log = logging.getLogger(__name__)


for cog in os.listdir("cogs"):
    if cog.startswith(
        "."
    ):  # Exclude incomplete modules (filenames starting with .), these modules are also gitignore'd.
        continue
    bot.load_extension(f'cogs.{cog.removesuffix(".py")}')

bot.run(secrets["bot_token"])
