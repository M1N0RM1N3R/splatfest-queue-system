import logging

import transaction
from discord.ext import tasks

from bot import bot
from classes import *

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)




@tasks.loop(minutes=5)
async def commit_db():
    log.info("Committing changes to database...")
    transaction.commit()
    log.info("Done committing changes to database")


for cog_name in [
    'dev',
    'tools',
    'welcome'
]:
    bot.load_extension(f'cogs.{cog_name}')

bot.run(secrets['bot_token'])
log.info("Committing changes to database...")
transaction.commit()
log.info("Done committing changes to database")
