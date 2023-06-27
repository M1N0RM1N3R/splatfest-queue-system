import datetime
import json
import logging
import traceback
from typing import Dict
import discord
from discord.ext import commands
from discord.errors import CheckFailure
from helpers.response_embeds import EmbedStyle
from helpers.db_handling_sdb import connection as db_connection

log = logging.getLogger(__name__)

secrets: Dict[str, str] = json.load(open("secrets.json"))
config = json.load(open(secrets["config_file"]))
bot = discord.Bot(
    debug_guilds=[config["guild"]],
    intents=discord.Intents(members=True, guilds=True, messages=True),
)
guild = lambda: bot.get_guild(config["guild"])


@bot.slash_command(description="Check the bot's status.")
async def ping(ctx):
    """Ensures that the bot is working properly, and shows the system latency."""
    global last_ready_time
    await ctx.send_response(
        embed=EmbedStyle.Ok.value.embed(title="Pong!")
        .add_field(name="Discord latency", value=f"{int(bot.latency*1000)}ms")
        .add_field(name="Database latency", value=f"{int(db_connection.connection.ws.latency*1000)}ms" if db_connection.connection else "Not initialized")
        .add_field(name="Last Ready event", value=f"<t:{int(last_ready_time.timestamp())}>"),
        ephemeral=True,
    )


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
        default=None,
    ),
):
    """You really need help with using the /help command? You just used it. Have an Easter egg: 🥚"""
    try:
        command = bot.get_application_command(command)
    except AttributeError:
        await ctx.send_response(
            embed=EmbedStyle.Info.value.embed(
                title="About Kolkra",
                description="Kolkra is Splatfest's official custom Discord bot, developed and maintained by <@547203725668646912> to help automate server-specific processes.",
            ),
            ephemeral=True,
        )
    else:
        await ctx.send_response(
            embed=EmbedStyle.Info.value.embed(
                title=f"Command info: {command.mention}",
                description=command.callback.__doc__,
            ),
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
        await ctx.respond(
            embed=EmbedStyle.Wait.value.embed(
                title="Command on cooldown",
                description="Your use of this command is being rate limited.",
            ).add_field(
                name="Retry",
                value=f"<t:{int(datetime.datetime.now().timestamp() + error.retry_after)}:R>",
            )
        )
    if isinstance(error, commands.BadArgument):
        await ctx.respond(
            embed=EmbedStyle.Warning.value.embed(
                title="Bad argument",
                description="An argument could not be parsed successfully.",
            )
        )
    elif isinstance(error, CheckFailure):
        await ctx.respond(
            embed=EmbedStyle.AccessDenied.value.embed(
                title="Command check(s) failed",
                description="A required check has failed while attempting to execute this command. This may be because you do not have the required permissions to execute the command.",
            ),
            ephemeral=True,
        )

    else:
        await ctx.respond(
            embed=EmbedStyle.Error.value.embed(title="Internal error", description=str(error)), ephemeral=True
        )
        log.exception(
            f'Uncaught exception in command "{ctx.command}"!',
            exc_info=(type(error), error, error.__traceback__),
        )
