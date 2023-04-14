import asyncio
import datetime
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List
import dateparser

import discord
from cuid2 import CUID
from glicko2 import Player as Glicko2
from ZODB import DB
from ZODB.FileStorage import FileStorage
from bot import *

config: Dict[str, str | int | float | list | dict] = json.load(open("config_beta.json"))
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
    id: str = field(default_factory=CUID().generate, kw_only=True)
    owner_id: int  # The Discord user ID that owns this resource.
    created_at: datetime.datetime = field(
        default_factory=datetime.datetime.now, kw_only=True
    )
    updated_at: datetime.datetime = field(default=None, kw_only=True)

    def embed(self, fields: Dict[str, str]):
        user = bot.get_guild(config["guild_id"]).get_member(self.owner_id)
        embed = discord.Embed(title=self.__class__.__doc__)
        embed.set_footer(
            f"{self.__class__.__name__} ID: {self.id} | Made with <:splatlove:1057108266062196827> by M1N3R"
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


@dataclass
class PlayerProfile(Resource):
    """Player Information"""

    rank: int  # The player's rank tier. (0=C, 1=B, 2=A, 3=S, 4=X)
    rank_points: int  # The player's rank points.
    series_wins: int
    series_losses: int
    series_active: bool
    # Player experience, increased by playing matches. Not to be confused with X Power.
    xp: int
    # A Glicko2 rating, implemented using the glicko2 module. (https://pypi.org/project/glicko2/)
    glicko2: Glicko2
    # The player's NSO friend code. Defaults to "Not Set" and can also be set to "Banned" (self explanatory).
    friend_code: str
    # The LAN play server the player prefers to use. Defaults to "Not Set".
    main_lan_server: str
    xtag: str
    ign: str

    def embed(self):
        return super().embed(
            {
                "Rank": f"{self.rank}/{self.rank_points}lrp",
                "XP": self.xp,
                "NSO Friend Code": self.friend_code,
                "Main LAN play server": self.main_lan_server,
                "XLink Kai username": self.xtag,
                "In-game name": self.ign,
            }
        )


def new_player_info():
    return {
        "rank": 0,
        "rank_points": 100,
        "series_wins": 0,
        "series_losses": 0,
        "series_active": False,
        "xp": 0,
        "glicko2": Glicko2(),
        "nso_friend_code": "Not set",
        "main_lan_server": "Not set",
        "xlink_kai_username": "Not set",
    }


try:
    db_root["players"]
except KeyError:
    db_root["players"] = {}


def get_player_by_id(discord_id):
    try:
        player = db_root["players"][discord_id]
    except KeyError:
        player = PlayerProfile(owner_id=discord_id, **new_player_info())
        db_root["players"][discord_id] = player
    finally:
        return player


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
