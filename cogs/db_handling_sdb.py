"""
This isn't exactly a cog, but it is an important component of the system whose setup/teardown can be handled by the existing extension API built into Pycord.
"""
import datetime
import json
import logging
from dataclasses import dataclass, field
from typing import TypeVar
from asyncio import get_event_loop

import discord
import shortuuid
from jsonpickle import decode, encode
from surrealdb import Surreal

from bot import bot
from classes import config, secrets

log = logging.getLogger(__name__)


@dataclass
class NoResultError(Exception):
    """No results were returned from the last line of a query."""

    query: str = None


@dataclass
class Resource:
    id: str = field(
        default=None, kw_only=True
    )  # Unique SurrealDB-formatted record ID. Generated post-init if not provided.
    owner_id: int  # The Discord user ID that owns this resource.
    created_at: datetime.datetime = field(
        default_factory=datetime.datetime.now, kw_only=True
    )
    updated_at: datetime.datetime = field(default=None, kw_only=True)

    def __post_init__(self):
        if not self.id:
            self.id = f"{self.__class__.__name__}:{shortuuid.uuid()}"

    def embed(self, fields: dict[str, str]):
        user = bot.get_guild(config["guild"]).get_member(self.owner_id)
        embed = (
            discord.Embed(title=self.__class__.__name__)
            .set_footer(text=f"ID: {self.id} | Made with 💚 by M1N3R")
            .set_author(name=user.display_name, icon_url=user.display_avatar)
        )
        for k, v in fields.items():
            embed.add_field(name=k, value=v)
        return embed

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if (
            name != "updated_at"
        ):  # prevent setting updated_at from causing a recursive loop
            self.updated_at = datetime.datetime.now()

    async def store(self):
        """Stores the object in the database."""
        log.debug("Storing %s", self)
        if old := await get(self.__class__, self.id):
            old_ser = ser(old)
            differences = {k: v for k, v in ser(self).items() if v != old_ser[k]}
            record = await connection.update(self.id, data=differences)
            log.debug("Updated %s", record)
        else:
            record = await connection.create(self.id, data=ser(self))
            log.debug("Inserted %s", record)


async def asetup():
    """Connects and authenticates with the local database."""
    global connection
    log.info("Setting up SurrealDB database...")
    connection = Surreal("ws://localhost:8000/rpc")
    await connection.connect()
    await connection.signin({"user": secrets['db_username'], "pass": secrets['db_password']})
    await connection.use("kolkra", "kolkra")
    log.info("Database setup complete!")

def setup(bot: discord.Bot):
    t = get_event_loop().run_until_complete(asetup())

async def ateardown():
    global connection
    log.info("Closing SurrealDB database...")
    await connection.close()
    log.info("Database closed!")

def teardown(bot: discord.Bot):
    t = get_event_loop().run_until_complete(ateardown())

R = TypeVar("R", bound=Resource)


def ser(value: R):
    return json.loads(encode(value))


def deser(obj_type: type[R], data: dict) -> R:
    """Deserializes data into a Resource.

    Args:
        obj_type (Type[R]): The Resource type to expect.
        data (dict): The data to deserialize.

    Returns:
        R: The final object.
    """
    return decode(json.dumps(data))


async def get(obj_type: type[R], obj_id: str) -> R:
    assert (
        obj_type.__name__ == obj_id.split(":")[0]
    ), "That object ID does not match the expected type."
    log.debug("Getting %s", obj_id)
    obj = deser(obj_type, await connection.select(obj_id))
    log.debug("Found %s", obj)
    return obj


async def run_query(obj_type: type[R], query: str, **params) -> list[R]:
    """Runs a query against the database, and returns the results from the last line.

    Args:
        obj_type (Type[R]): The object type to expect.
        query (str): The query to run.
        **params: Parameters to use in the query.

    Returns:
        list[R]: A list of objects returned from the last line of the query.

    Raises:
        NoResultError: No results or an error was returned from the last line.
    """
    log.debug("Running query %s with params %s", query, params)
    try:
        results = (await connection.query(query, params))[-1]["result"]
    except (IndexError, KeyError) as e:
        raise NoResultError(query) from e
    else:
        log.debug("Found %s", results)
        return deser(list, results)
