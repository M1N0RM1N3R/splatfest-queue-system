import discord
import logging

import asyncio
from classes import clean
import datetime

import textwrap


def truncate_and_codeblock(original: str, max_length: int, placeholder: str = "..."):
    return (
        f"```{original[:max_length - len(placeholder) - 6]}```{placeholder}"
        if len(original) > max_length - 6
        else f"```{original}```"
    )


class DiscordLogHandler(logging.Handler):
    def __init__(
        self,
        bot: discord.Bot,
        channel_id: int,
        level=logging.NOTSET,
    ):
        super().__init__(level)

        self.bot = bot

        self.channel_id = channel_id

    def emit(self, record: logging.LogRecord) -> None:
        embed = discord.Embed(
            title=f"{record.levelname} at {record.module}:{record.lineno} in {record.funcName}",
            description=truncate_and_codeblock(clean(record.message), 4090),
            timestamp=datetime.datetime.fromtimestamp(record.created),
        )

        embed.set_thumbnail(
            url={
                "DEBUG": "https://cdn-icons-png.flaticon.com/512/2818/2818757.png",
                "INFO": "https://cdn-icons-png.flaticon.com/512/1304/1304036.png",
                "WARNING": "https://cdn-icons-png.flaticon.com/512/2684/2684750.png",
                "ERROR": "https://cdn-icons-png.flaticon.com/512/2797/2797263.png",
                "CRITICAL": "https://cdn-icons-png.flaticon.com/512/559/559375.png",
            }[record.levelname]
        )

        if record.exc_text:
            embed.add_field(
                name="Exception info",
                value=truncate_and_codeblock(record.exc_text, 1024),
            )

        asyncio.get_event_loop().create_task(
            self.bot.get_channel(self.channel_id).send(embed=embed)
        )
