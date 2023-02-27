import datetime
import logging

import discord
import transaction
import yaml
from discord.ext import commands, tasks

from classes import *

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = discord.Bot(debug_guilds=[config['guild']],
                  intents=discord.Intents(members=True))


@bot.slash_command(name='ping')
async def ping(ctx):
    await ctx.send_response(f"🏓 Pong! Latency: {int(bot.latency*1000)}ms")


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user}")


@bot.event
async def on_disconnect():
    log.error(f"Lost connection to Discord!")


@bot.event
async def on_error(event, *args, **kwargs):
    log.exception(
        f'Uncaught exception in event "{event}"! Event information:\n{yaml.dump({"args": args, "kwargs": kwargs})}')


@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error: discord.DiscordException):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.respond(f"❌⏳ This command is on cooldown. Please try again <t:{datetime.datetime.now().timestamp() + error.retry_after}:R>.")
    else:
        await ctx.respond(f"❌⚠️ Something went wrong on our end: {str(error)}")
        log.exception(
            f'Uncaught exception in application command "{ctx.command.qualified_name}"! CTX information:\n{yaml.dump(ctx)}')


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
