import asyncio
import datetime
import json
import logging
from dataclasses import dataclass, field
from typing import TypeVar

import discord
from jsonpickle import decode, encode
from shortuuid import uuid
from surrealdb import Surreal
from surrealdb.ws import ConnectionState

from bot import bot
from classes import config, secrets

log = logging.getLogger(__name__)


@dataclass
class NoResultError(Exception):
    """No results were returned from the last line of a query."""

    query: str
    params: dict
    output: str

    def __str__(self):
        return f"Query {self.query} with params {self.params} returned {self.output}"




R = TypeVar("R", bound='Resource')

class DatabaseConnection:
    connection: Surreal

    def __init__(self):
        self.connection: Surreal = None

    async def asetup(self):
        log.info("Setting up SurrealDB database...")
        self.connection = Surreal("ws://localhost:8000/rpc")
        await self.connection.connect()
        await self.connection.signin(
            {"user": secrets["db_username"], "pass": secrets["db_password"]}
        )
        await self.connection.use("foo", "bar")
        log.info("Database setup complete!")

    async def ateardown(self):
        log.info("Closing SurrealDB database...")
        await self.connection.close()
        log.info("Database closed!")

    async def get(self, obj_type: type[R], obj_id: str) -> R:
        if not self.connection:
            await self.asetup()
        log.debug("Getting %s", obj_id)
        obj = deser(obj_type, await self.connection.select(obj_id))
        log.debug("Found %s", obj)
        return obj

    async def run_query(self, obj_type: type[R], query: str, **params) -> list[R]:
        if (
            not self.connection
        ) or self.connection.client_state != ConnectionState.CONNECTED:
            await self.asetup()
        log.debug("Running query %s with params %s", query, params)
        output = await self.connection.query(query, params)
        try:
            results = output[-1]["result"]
        except (IndexError, KeyError) as e:
            raise NoResultError(query, params, output) from e
        else:
            log.debug("Found %s", results)
            return deser(list, results)


connection = DatabaseConnection()


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
            self.id = f"{self.__class__.__name__}:{uuid()}"

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
        """Stores the object in the database through the DatabaseConnection."""
        log.debug("Storing %s", self)
        if old := await connection.get(self.__class__, self.id):
            old_ser = ser(old)
            differences = {k: v for k, v in ser(self).items() if v != old_ser[k]}
            record = await connection.connection.update(self.id, data=differences)
            log.debug("Updated %s", record)
        else:
            record = await connection.connection.create(self.id, data=ser(self))
            log.debug("Inserted %s", record)


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
