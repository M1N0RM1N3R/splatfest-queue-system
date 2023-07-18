from enum import IntEnum
from typing import Callable

import discord

from bot import config
from helpers.embed_templates import EmbedStyle


class StaffLevel(IntEnum):
    pleb = 0
    council = 1
    arbit = 2
    mod = 3
    admin = 4
    server_owner = 5


def get_staff_level(member: discord.Member) -> StaffLevel:
    if member.guild.owner.id == member.id:
        level = StaffLevel.server_owner
    else:
        has_roles_for: list[str] = [
            level_name
            for level_name, role_id in config["staff_roles"].items()
            if member.get_role(role_id)
        ]

        try:
            level = max(StaffLevel[i] for i in has_roles_for)
        except ValueError:
            level = StaffLevel.pleb
    return level


def required_staff_level(
    min_level: StaffLevel, except_dev: bool = True
) -> Callable[[discord.ApplicationContext], bool]:
    """Factory function for a check that returns True if the user is of or above the specified staff level.

    Args:
        min_level (StaffLevel): The minimum staff level for the check to pass.
        except_dev (bool, optional): Allow the bot owner to override this check. Defaults to True.

    Returns:
        Callable[[discord.ApplicationContext], bool]: The resulting check.
    """

    async def inner(ctx: discord.ApplicationContext) -> bool:
        user = ctx.interaction.user
        if except_dev and await ctx.bot.is_owner(user):
            return True
        # Establish the user's staff level
        level = get_staff_level(user)
        if level and level >= min_level:
            return True
        await ctx.respond(
            embed=EmbedStyle.AccessDenied.value.embed(
                title="Insufficient staff level",
                description=f"You must be {min_level.name} or higher to use this command. (You are currently {level.name if level else 'not a staff member'}.)",
            ),
            ephemeral=True,
        )
        return False

    return inner


def in_channel(*channel_ids: int) -> Callable[[discord.ApplicationContext], bool]:
    """Factory function for a simple check that a command is being invoked in a specified channel or group of channels.

    Returns:
        callable[[discord.ApplicationContext], bool]: The check function itself.
    """

    async def inner(ctx: discord.ApplicationContext):
        channel = ctx.interaction.channel
        if channel.id in channel_ids:
            return True
        await ctx.respond(
            embed=EmbedStyle.AccessDenied.value.embed(
                title="Wrong channel",
                description=f"This command can only be used in {', '.join([f'<#{id}>' for id in channel_ids])}.",
            ),
            ephemeral=True,
        )
        return False

    return inner


def has_role(*role_ids: int) -> Callable[[discord.ApplicationContext], bool]:
    """Factory function for a simple check that the user invoking a command has one of a set of roles.

    Returns:
        Callable[[discord.ApplicationContext], bool]: The check function itself.
    """

    async def inner(ctx: discord.ApplicationContext) -> bool:
        user = ctx.interaction.user
        for role_id in role_ids:
            if user.get_role(role_id):
                return True
        await ctx.respond(
            embed=EmbedStyle.AccessDenied.value.embed(
                description=f"You must have one or more of the following roles to use this command:\n{', '.join([f'<@&{role_id}>' for role_id in role_ids])}"
            )
        )
        return False

    return inner
