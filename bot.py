

import datetime
import json
import logging
import traceback
from typing import Dict
import discord
from discord.ext import commands

log = logging.getLogger(__name__)

secrets: Dict[str, str] = json.load(open("secrets.json"))
config = json.load(open(secrets['config_file']))
bot = discord.Bot(
    debug_guilds=[config["guild"]], intents=discord.Intents(members=True, guilds=True)
)
guild = lambda: bot.get_guild(config["guild"])


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
        default=None
    )
):
    """You really need help with using the /help command? You just used it. Have an Easter egg: 🥚"""
    try: command = bot.get_application_command(command)
    except AttributeError:
        await ctx.send_response(f"""
Hi there! My name is Kolkra. I'm an Octarian youth training to become a helpful assistant to everyone in the Splatfest server.
If you want to learn more about what I can do, just ask me about one of my commands with {help.mention}, and I'll show you one of these descriptions from M1N3R about what it does and how to use it.
""")
    else:
        await ctx.send_response(f"> **{command}**\n{command.callback.__doc__}", ephemeral=True)
        


@bot.event
async def on_login():
    log.info(f"Logged in as {bot.user}")


@bot.event
async def on_ready():
    log.info("Ready!")


@bot.event
async def on_disconnect():
    log.error("Lost connection to Discord!")


@bot.event
async def on_error(event, *args, **kwargs):
    log.exception(f'Uncaught exception in event "{event}"!')


@bot.event
async def on_application_command(context: discord.ApplicationContext):
    log.info(
        f'"{context.command.qualified_name}" invoked by {context.author} with args {context.selected_options}'
    )


@bot.event
async def on_application_command_error(
    ctx: discord.ApplicationContext, error: discord.DiscordException
):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.respond(
            f"❌⏳ This command is on cooldown. Please try again <t:{datetime.datetime.now().timestamp() + error.retry_after}:R>.",
            ephemeral=True,
        )
    if isinstance(error, commands.BadArgument):
        await ctx.respond(
            f"❌⁉️ Could not parse an argument: {error.message}"
        )
    elif isinstance(error, commands.CheckFailure):
        await ctx.respond(
            f"⛔ {error.message or 'You do not have the proper permissions to use this command.'} If you believe you have received this message in error, please contact a server admin or <@547203725668646912> for assistance.",
            ephemeral=True,
        )
    else:
        await ctx.respond(
            f"❌ Something went wrong on our end: {str(error)}", ephemeral=True
        )
        log.exception(
            f'Uncaught exception in command "{ctx.command}"!',
            exc_info=(type(error), error, error.__traceback__),
        )
