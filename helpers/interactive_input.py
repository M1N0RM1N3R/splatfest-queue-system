import asyncio
import logging
from inspect import Parameter
from typing import Optional, TypeVar

import discord
from discord.ext.commands import Converter

from helpers.embed_templates import EmbedStyle

log = logging.getLogger(__name__)


class Cancelled(Exception):
    pass


async def text_input(
    ctx: discord.ApplicationContext, converter: Optional[Converter] = None
):
    try:
        msg: discord.Message = await ctx.bot.wait_for(
            "message",
            check=lambda m: m.author == ctx.author and m.channel.id == ctx.channel.id,
            timeout=120,
        )

        if msg.content == "CANCEL INPUT":
            raise Cancelled()

        converted = (
            await discord.ext.commands.run_converters(
                ctx,
                converter,
                msg.content,
                Parameter("INTERACTIVE_TEXT_INPUT", Parameter.POSITIONAL_OR_KEYWORD),
            )
            if converter is not None
            else msg.content
        )
        log.debug(f"{msg.content} => {converted}")
        return converted

    except asyncio.TimeoutError as e:
        await ctx.send(
            embed=EmbedStyle.Error.value.embed(
                title="Input timed out",
                description="You took too long to provide input.",
            )
        )

        log.debug(f"Got reaction input {msg.content}")

        raise e


async def reaction_input(
    ctx, on_message: discord.Message, allow_custom: bool = True
) -> discord.Emoji | discord.PartialEmoji | str:
    try:
        reaction: discord.Emoji
        user: discord.User
        (reaction, user) = await ctx.bot.wait_for(
            "reaction_add",
            check=lambda r, u: r.message.id == on_message.id
            and u.id == ctx.author.id
            and (not r.is_custom_emoji() or allow_custom),
            timeout=120,
        )

        if str(reaction) == ":x:":
            raise Cancelled()

        return reaction.emoji

    except asyncio.TimeoutError as e:
        await ctx.send(
            embed=EmbedStyle.Error.value.embed(
                title="Input timed out",
                description="You took too long to provide input.",
            )
        )

        raise e
