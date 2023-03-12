import logging

import transaction
from discord.ext import tasks

from bot import bot
from classes import *

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)




@tasks.loop(minutes=5)
async def commit_db():
    log.info(f"Committing changes to database...")
    transaction.commit()
    log.info(f"Done committing changes to database")


for cog_name in [
    'dev',
    'tools',
    'welcome'
]:
    bot.load_extension('cogs.'+cog_name)

bot.run(config['bot_token'])
transaction.commit()
