import asyncio
import datetime
import json
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

import discord
import tomllib


secrets: Dict[str, str] = json.load(open("secrets.json"))
with open(secrets["config_file"], "rb") as toml:
    config = tomllib.load(toml)


async def wait_for(
    condition: Callable[..., bool],
    timeout: Optional[float] = None,
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
