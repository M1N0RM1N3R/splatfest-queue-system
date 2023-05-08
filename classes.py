import asyncio
import datetime
import json
from dataclasses import dataclass, field
from typing import Callable, Dict

import discord
import persistent
import shortuuid
from bot import bot

secrets: Dict[str, str] = json.load(open("secrets.json"))
config = json.load(open(secrets['config_file']))


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


clean = discord.utils.escape_markdown


async def delay(duration: float, coroutine, **kwargs):
    await asyncio.sleep(duration)
    await coroutine(**kwargs)


@dataclass
class Resource(persistent.Persistent):
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