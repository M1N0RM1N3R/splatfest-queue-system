import logging
import os

import transaction
from discord.ext import tasks

from bot import bot
from classes import *
from helpers.discord_logger import DiscordLogHandler
from helpers.db_handling import commit

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(module)s:%(lineno)d   %(message)s")
logging.getLogger().addHandler(DiscordLogHandler(bot, config['log_channel'], level=logging.WARNING))
log = logging.getLogger(__name__)


@tasks.loop(minutes=5)
async def commit_db():
    await commit(bot)
commit_db.start()


for cog in os.listdir("cogs"):
    if cog.startswith("."): # Exclude incomplete modules (filenames starting with .), these modules are also gitignore'd.
        continue
    bot.load_extension(f'cogs.{cog.removesuffix(".py")}')

bot.run(secrets["bot_token"])
log.info("Committing changes to database...")
transaction.commit()
log.info("Done committing changes to database")
