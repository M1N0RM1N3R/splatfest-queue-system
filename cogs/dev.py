import logging
import os
import sys
from inspect import isawaitable
from io import StringIO

import discord
from aiohttp import client

from bot import secrets
from helpers.db_handling_sdb import connection
from helpers.embed_templates import EmbedStyle

log = logging.getLogger(__name__)


async def is_owner(ctx: discord.ApplicationContext):
    if not await ctx.bot.is_owner(ctx.user):
        await ctx.respond(embed=EmbedStyle.AccessDenied.value.embed(description="This command is restricted to the bot owner only."))
        return False
    return True

def reload_cogs():
    # Unload the old cogs
    for cog in list(self.bot.extensions.keys()):
        self.bot.unload_extension(cog)
    # Load in the new cogs
    errors = {}
    for cog in os.listdir("cogs"):
        if cog.startswith("."):
            continue
        try:
            self.bot.load_extension(f'cogs.{cog.removesuffix(".py")}')
        except Exception as e:
            errors[cog] = e
    return errors

async def hastebin_upload(text: str):
    """Uploads text to Hastebin.

    Args:
        text (str): The text to upload.

    Returns:
        str: The link to the uploaded text.
    """
    async with client.ClientSession() as session:
                async with session.post(
                    "https://hastebin.com/documents",
                    data=text,
                    headers={
                        "content-type": "text/plain",
                        "Authorization": f"Bearer {secrets['hastebin_token']}",
                    },
                    raise_for_status=True,
                ) as response:
                    paste_id = (await response.json())["key"]
    return f"https://hastebin.com/share/{paste_id}"

class DevCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(
        name="dev",
        description="Internal commands restricted to M1N3R only.",
        checks=[is_owner],
    )

    async def fetch_merge(self, ctx, commit_id, branch: str = 'main'):
        # Fetch and merge commit from GitHub
        for cmd in [f"git fetch origin {branch}", f"git merge {commit_id}"]:
            if exit_status := await self.bot.loop.run_in_executor(None, os.system, cmd):
                raise OSError(
                    f"Failed to fetch-merge commit {commit_id}: {cmd} returned exit status {exit_status}"
                )

    @root.command(description="Execute an arbitrary script.")
    async def execute(self, ctx: discord.ApplicationContext, script: str):
        """Executes an arbitrary Python script in the bot context. Used to debug and retrieve information not accessible by other commands.
        
        Args:
            script (str): The Python script to execute.
        """
        await ctx.defer(ephemeral=True)

        output = eval(script)
        if isawaitable(output):
            output = await output
        output = str(output)
        if (
            len(output) > 4000
        ):  # If the response is too long, upload it to Hastebin and return a link to the uploaded text.
            link = await hastebin_upload(output)
            await ctx.respond(
                embed=EmbedStyle.Ok.value.embed(
                    title="Output uploaded to Hastebin",
                    description="The output of this script is over 4,000 characters, so it was uploaded to Hastebin.",
                ).add_field(
                    name="Link to uploaded output",
                    value=link,
                ),
                ephemeral=True,
            )
        else:
            await ctx.respond(
                embed=EmbedStyle.Ok.value.embed(
                    title="Script output", description=output
                ),
                ephemeral=True,
            )

    @root.command(description="Update cogs without a cold start.")
    async def hot_update(self, ctx: discord.ApplicationContext, commit_id: str, branch: str = 'main'):
        """Automatically update Kolkra's cogs (command modules) without taking her offline entirely. Updates to code/config info outside of cogs requires a full update.
        
        Args:
            commit_id (str): The commit ID to update to.
            branch (str): The branch the commit belongs to. Defaults to main.
        """
        await ctx.defer(ephemeral=True)
        await self.fetch_merge(ctx, commit_id, branch)
        if errors := reload_cogs():
            error_list = "\n".join([f"- {k}: {v}" for k, v in errors.items()])
            return await ctx.respond(
                embed=EmbedStyle.Warning.value.embed(
                    title="Cog reloading failed", description=error_list
                )
            )
        else:
            return await ctx.respond(
                embed=EmbedStyle.Ok.value.embed(
                    description="All cogs updated successfully."
                )
            )

    @root.command()
    async def restart_bot(self, ctx: discord.ApplicationContext):
        """Self-restart the bot."""

        log.warning("Bot is restarting!")
        await ctx.respond(
            embed=EmbedStyle.Ok.value.embed(title="Restarting..."), ephemeral=True
        )
        # Teardown tasks
        for name in list(self.bot.extensions):
            self.bot.unload_extension(name)
        # https://stackoverflow.com/a/5758926
        args = sys.argv[:]
        args.insert(0, sys.executable)
        if sys.platform == "win32":
            args = ['"%s"' % arg for arg in args]
        os.execv(sys.executable, args)

    @root.command(description="Update Kolkra's files, then restart.")
    async def full_update(self, ctx: discord.ApplicationContext, commit_id: str, branch: str = 'main'):
        """Update Kolkra's files, then self-restart.
        
        Args:
            commit_id (str): The commit ID to update to. The commit must be on the main branch.
            branch (str): The branch the commit belongs to. Defaults to main.
        """
        await ctx.defer(ephemeral=True)
        await self.fetch_merge(ctx, commit_id)
        await ctx.respond(
            embed=EmbedStyle.Ok.value.embed(description="Fetch-merge complete."),
            ephemeral=True,
        )
        await self.restart_bot(ctx)

    @root.command(description="Run a SurrealQL query against the database.")
    async def sql(self, ctx: discord.ApplicationContext, query: str):
        """Run a SurrealQL query against the database.

        Args:
            query (str): The query to execute.
        """
        await ctx.defer(ephemeral=True)
        output = await connection.connection.query(query)
        if (
            len(output) > 4000
        ):  # If the response is too long, upload it to Hastebin and return a link to the uploaded text.
            link = await hastebin_upload(json.dumps(output))
            await ctx.respond(
                embed=EmbedStyle.Ok.value.embed(
                    title="Output uploaded to Hastebin",
                    description="The output of this query is over 4,000 characters, so it was uploaded to Hastebin.",
                ).add_field(
                    name="Link to uploaded output",
                    value=link,
                ),
                ephemeral=True,
            )
        else:
            await ctx.respond(
                embed=EmbedStyle.Ok.value.embed(
                    title="Query output", description=output
                ),
                ephemeral=True,
            )


def setup(bot: discord.Bot):
    bot.add_cog(DevCog(bot))
    log.info("Cog initialized")
