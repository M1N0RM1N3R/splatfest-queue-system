import asyncio
import datetime
import logging
import os
import textwrap
import traceback
from os.path import relpath

import discord



def truncate_and_codeblock(original: str, max_length: int, placeholder: str = "..."):
    return (
        f"```{original[:max_length - len(placeholder) - 6]}```{placeholder}"
        if len(original) > max_length - 6
        else f"```{original}```"
    )


def format_exception_info(exc_info):
    out = f"{exc_info[0].__name__}: {exc_info[1]}\nStack trace:\n"
    traces = traceback.extract_tb(exc_info[2])
    for frame in traces:
        out += f"{relpath(frame.filename, os.getcwd())}:{frame.lineno} in {frame.name}\n    {frame.line}\n\n"
    if cause := exc_info[1].__cause__:
        out = f"{format_exception_info((type(cause), cause, cause.__traceback__))}The above exception caused the following exception:\n{out}"
    return out


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
            description=truncate_and_codeblock(discord.utils.escape_markdown(record.message), 4000),
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

        if record.exc_info:
            embed.add_field(
                name="Exception info",
                value=truncate_and_codeblock(
                    format_exception_info(record.exc_info), 1024
                ),
            )

        c = self.bot.get_channel(self.channel_id)
        if isinstance(c, discord.abc.Messageable):
            asyncio.get_event_loop().create_task(c.send(embed=embed))
        else:
            raise TypeError(
                f"Invalid channel type: Expected discord.abc.Messageable, found {type(c)}"
            )
