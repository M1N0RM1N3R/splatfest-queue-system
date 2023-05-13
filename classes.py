import asyncio
import datetime
import json
from dataclasses import dataclass, field
from typing import Callable, Dict

import discord

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