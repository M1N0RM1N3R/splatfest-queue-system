import logging
import os
import sys
import discord
from helpers.db_handling import commit, db
from classes import *

log = logging.getLogger(__name__)


async def is_owner(ctx: discord.ApplicationContext):
    return await ctx.bot.is_owner(ctx.user)


class DevCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(
        name="dev",
        description="Internal commands restricted to M1N3R only.",
        checks=[is_owner],
    )

    async def fetch_merge(self, ctx, commit_id):
        # Fetch and merge commit from GitHub
        for cmd in ["git fetch origin main", f"git merge {commit_id}"]:
            if exit_status := await self.bot.loop.run_in_executor(None, os.system, cmd):
                raise OSError(
                    f"Failed to fetch-merge commit {commit_id}: {cmd} returned exit status {exit_status}"
                )

    @root.command(name="execute", description="Execute a script for debugging.")
    async def execute(self, ctx: discord.ApplicationContext, script: str):
        """Executes an arbitrary Python script in the bot context. Used to debug and retrieve information not accessible by other commands.
        Args:
            script (str): The Python script to execute.
        """
        await ctx.defer(ephemeral=True)
        output = str(eval(script) or "✅")
        for i in range(0, len(output), 2000):
            await ctx.send_followup(output[i : i + 2000], ephemeral=True)

    @root.command(name="hot-update", description="Update cogs without a cold start.")
    async def hot_update(self, ctx: discord.ApplicationContext, commit_id: str):
        """Automatically update Kolkra's cogs (command modules) without taking her offline entirely. Updates to code/config info outside of cogs requires a full update.
        Args:
            commit_id (str): The commit ID to update to. The commit must be on the main branch.
        """
        await ctx.defer(ephemeral=True)
        await self.fetch_merge(ctx, commit_id)
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
        if errors:
            error_list = "\n".join([f" - {k}: {v}" for k, v in errors.items()])
            return await ctx.send_followup(
                f"⚠️ One or more cogs failed to load:\n{error_list}"
            )
        else:
            return await ctx.send_followup("✅ All cogs updated successfully.")

    @root.command(name="restart")
    async def restart_bot(self, ctx: discord.ApplicationContext):
        """Self-restart the bot."""

        log.warning("Bot is restarting!")
        await ctx.respond("🔽 See you on the other side.", ephemeral=True)
        # Teardown tasks
        await commit(self.bot)
        db.close()
        for name in list(self.bot.extensions):
            self.bot.unload_extension(name)
        # https://stackoverflow.com/a/5758926
        args = sys.argv[:]
        args.insert(0, sys.executable)
        if sys.platform == "win32":
            args = ['"%s"' % arg for arg in args]
        os.execv(sys.executable, args)

    @root.command(
        name="full-update", description="Update Kolkra's files, then restart."
    )
    async def full_update(self, ctx: discord.ApplicationContext, commit_id: str):
        """Update Kolkra's files, then self-restart.
        Args:
            commit_id (str): The commit ID to update to. The commit must be on the main branch.
        """
        await ctx.defer(ephemeral=True)
        await self.fetch_merge(ctx, commit_id)
        await ctx.send_followup("✅ Fetch-merge complete.", ephemeral=True)
        await self.restart_bot(ctx)


def setup(bot: discord.Bot):
    bot.add_cog(DevCog(bot))
    log.info("Cog initialized")
