import datetime
import json
import logging
from typing import Dict

import discord
from discord.ext import commands
import yaml

log = logging.getLogger(__name__)

config: Dict[str, str | int | float | list |
             dict] = json.load(open('config.json'))

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
