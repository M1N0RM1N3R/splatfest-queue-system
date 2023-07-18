import datetime
import json
import logging
import traceback
from typing import Dict

import discord
from discord.errors import CheckFailure
from discord.ext import commands
from docstring_parser.google import parse as parse_docstring
import tomllib

from helpers.embed_templates import EmbedStyle

log = logging.getLogger(__name__)

secrets: Dict[str, str] = json.load(open("secrets.json"))
with open(secrets["config_file"], "rb") as toml:
    config = tomllib.load(toml)
    log.info("Current configuration:\n%s", json.dumps(config))
print("guild id", type(config["guild"]))
bot = discord.Bot(
    debug_guilds=[config["guild"]],
    intents=discord.Intents(
        members=True, guilds=True, messages=True, message_content=True, reactions=True
    ),
)
guild = lambda: bot.get_guild(config["guild"])


@bot.slash_command()
async def ping(ctx):
    """Ensures that the bot is working properly, and shows the system latency."""
    from helpers.db_handling_sdb import connection as db_connection
    global last_ready_time
    await ctx.respond(
        embed=EmbedStyle.Ok.value.embed(title="Pong!")
        .add_field(name="Discord latency", value=f"{int(bot.latency*1000)}ms")
        .add_field(
            name="Database latency",
            value=f"{int(db_connection.connection.ws.latency*1000)}ms"
            if db_connection.connection
            else "Not initialized",
        )
        .add_field(
            name="Last Ready event", value=discord.utils.format_dt(last_ready_time)
        ),
        ephemeral=True,
    )


async def _cmd_list(ctx: discord.AutocompleteContext):
    async def can_run(cmd, ctx):
        try:
            return await cmd.can_run(ctx)
        except Exception:
            return False

    return [
        cmd.qualified_name
        for cmd in bot.walk_application_commands()
        if type(cmd) == discord.SlashCommand and await can_run(cmd, ctx)
    ]


@bot.slash_command(name="help", description="Show detailed info about a command.")
async def help(
    ctx,
    command=discord.Option(
        str,
        description="The command to get help for.",
        autocomplete=discord.utils.basic_autocomplete(_cmd_list),
        default=None,
    ),
):
    """You really need help with using the /help command? You just used it. Have an Easter egg: 🥚"""
    try:
        command = bot.get_application_command(command)
    except AttributeError:
        await ctx.respond(
            embed=EmbedStyle.Info.value.embed(
                title="About Kolkra",
                description="Kolkra is Splatfest's official custom Discord bot, developed and maintained by <@547203725668646912> to help automate server-specific processes.",
            ),
            ephemeral=True,
        )
    else:
        parsed = parse_docstring(command.callback.__doc__)
        embed = EmbedStyle.Info.value.embed(
            title=f"Command info: {command.mention}",
            description=parsed.short_description,
        )
        for arg in parsed.params:
            embed.add_field(
                name=f"Arg: {arg.arg_name} ({arg.type_name})",
                value=f"{arg.description}",
            )
        await ctx.respond(
            embed=embed,
            ephemeral=True,
        )


@bot.event
async def on_login():
    log.info(f"Logged in as {bot.user}")


@bot.event
async def on_ready():
    global last_ready_time
    last_ready_time = datetime.datetime.now()
    log.info("Ready!")


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
        error: commands.CommandOnCooldown
        await ctx.respond(
            embed=EmbedStyle.Wait.value.embed(
                title="Command on cooldown",
                description="Your use of this command is being rate limited.",
            ).add_field(
                name="Retry",
                value=discord.utils.format_dt(
                    datetime.datetime.now()
                    + datetime.timedelta(seconds=error.retry_after)
                ),
            ),
            ephemeral=True,
        )
    elif isinstance(error, commands.BadArgument):
        error: commands.BadArgument
        await ctx.respond(
            embed=EmbedStyle.Warning.value.embed(
                title="Bad argument",
                description=error.message,
            )
        )
    elif isinstance(
        error, CheckFailure
    ):  # Do nothing on check failure--our custom checks in helpers.command_checks and elsewhere return their own error messages
        return
    else:
        await ctx.respond(
            embed=EmbedStyle.Error.value.embed(
                title="Internal error", description=str(error)
            ),
            ephemeral=True,
        )
        log.exception(
            f'Uncaught exception in command "{ctx.command}"!',
            exc_info=(type(error), error, error.__traceback__),
        )
