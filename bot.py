import datetime
import json
import logging

import discord
from discord.ext import commands

log = logging.getLogger(__name__)

config = json.load(open("config_beta.json"))

bot = discord.Bot(debug_guilds=[config["guild"]], intents=discord.Intents(members=True))

guild = lambda: bot.get_guild(config["guild"])
log_channel = lambda: bot.get_channel(config["log_channel"])


@bot.slash_command(name="ping", description="Check the bot's status.")
async def ping(ctx):
    """Ensures that the bot is working properly, and shows the latency between the host and the Discord gateway."""
    await ctx.send_response(f"🏓 Pong! Latency: {int(bot.latency*1000)}ms.")


@bot.slash_command(name="help", description="Show detailed help about a command.")
async def help(
    ctx,
    command=discord.Option(
        str,
        description="The command to get help for.",
        autocomplete=discord.utils.basic_autocomplete(
            lambda ctx: [
                cmd.qualified_name
                for cmd in bot.walk_application_commands()
                if type(cmd) != discord.SlashCommandGroup
            ]
        ),
        optional=False,
    ),
):
    """You really need help with using the /help command? You just used it. Have an Easter egg: 🥚"""
    await ctx.send_response(
        f"> **{command}**\n{bot.get_application_command(command).callback.__doc__}",
        ephemeral=True,
    )


@bot.event
async def on_login():
    log.info(f"Logged in as {bot.user}")


@bot.event
async def on_ready():
    log.info("Ready!")
    
    for channel in bot.get_all_channels():
        print("Go!")
        print(channel)


@bot.event
async def on_disconnect():
    log.error("Lost connection to Discord!")


@bot.event
async def on_error(event, *args, **kwargs):
    log.exception(f'Uncaught exception in event "{event}"!')

@bot.event
async def on_application_command(context:discord.ApplicationContext):
    log.info(f'"{context.command.qualified_name}" invoked by {context.author} with args {context.options}')


@bot.event
async def on_application_command_error(
    ctx: discord.ApplicationContext, error: discord.DiscordException
):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.respond(
            f"❌⏳ This command is on cooldown. Please try again <t:{datetime.datetime.now().timestamp() + error.retry_after}:R>."
        )
    else:
        await ctx.respond(
            f"❌ Something went wrong on our end: {str(error)}", ephemeral=True
        )
        log.exception(f'Uncaught exception in command "{ctx.command}"!', exc_info=(type(error), error, error.__traceback__))