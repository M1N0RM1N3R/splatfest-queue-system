import discord
from classes import config

async def is_admin_or_dev(ctx: discord.ApplicationContext):
    return ctx.author.get_role(config["admin_role"]) or await ctx.bot.is_owner(
        ctx.user
    )