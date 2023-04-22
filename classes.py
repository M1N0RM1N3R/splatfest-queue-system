import asyncio
import datetime
import json
from dataclasses import dataclass, field
from logging import LogRecord
from typing import Callable, Dict, List
import dateparser

import discord
import shortuuid
from ZODB import DB
from ZODB.FileStorage import FileStorage
from bot import *

config = json.load(open("config_beta.json"))
secrets: Dict[str, str] = json.load(open("secrets.json"))


async def wait_for(
    condition: Callable[..., bool],
    timeout: float = None,
    poll_interval: float = 0.1,
    *args,
    **kwargs,
) -> bool:
    if timeout:
        stop_time = datetime.datetime.now() + datetime.timedelta(seconds=timeout)
    while True:
        if condition(*args, **kwargs):
            return True
        elif timeout:
            if datetime.datetime.now() > stop_time:
                return False
        await asyncio.sleep(poll_interval)


# setup the database
print("Initializing database...", end="")
storage = FileStorage("database.fs")
db = DB(storage)
connection = db.open()
db_root = connection.root()
print("DONE!")

clean = discord.utils.escape_markdown


async def delay(duration: float, coroutine, **kwargs):
    await asyncio.sleep(duration)
    await coroutine(**kwargs)


@dataclass
class Resource:
    id: str = field(default_factory=shortuuid.uuid, kw_only=True)
    owner_id: int  # The Discord user ID that owns this resource.
    created_at: datetime.datetime = field(
        default_factory=datetime.datetime.now, kw_only=True
    )
    updated_at: datetime.datetime = field(default=None, kw_only=True)

    def embed(self, fields: Dict[str, str]):
        user = bot.get_guild(config["guild"]).get_member(self.owner_id)
        embed = discord.Embed(title=self.__class__.__name__)
        embed.set_footer(
            text=f"{self.__class__.__name__} ID: {self.id} | Made with 💚 by M1N3R"
        )
        for k, v in fields.items():
            embed.add_field(name=k, value=v)
        embed.set_author(name=user.display_name, icon_url=user.display_avatar)
        return embed

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if (
            name != "updated_at"
        ):  # prevent setting updated_at from causing a recursive loop
            self.updated_at = datetime.datetime.now()


def iso8601_option_autocomplete(actx: discord.AutocompleteContext) -> List[str]:
    try:
        return [dateparser.parse(actx.value).replace(microsecond=0).isoformat()]
    except AttributeError:
        return []


def iso8601_option(desc):
    return discord.Option(
        str,
        description=f"{desc} (Tip: I can format natural language!)",
        autocomplete=iso8601_option_autocomplete,
    )


class DiscordLogHandler(logging.Handler):
    def __init__(
        self,
        level=logging.NOTSET,
    ):
        super().__init__(level)

    def emit(self, record: LogRecord) -> None:
        embed = discord.Embed(title=f"{record.levelname} at {record.module}:{record.lineno} in {record.funcName}",description=clean(record.message),timestamp=datetime.datetime.fromtimestamp(record.created))

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
            embed.add_field(name="Exception info", value=record.exc_text)
        bot.loop.create_task(log_channel.send(embed=embed))
