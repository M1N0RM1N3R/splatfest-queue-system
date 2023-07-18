import asyncio
import datetime
import json
import logging
from dataclasses import asdict, dataclass, field, fields as dc_fields
from typing import Any, Optional, TypeVar

import discord
from dataclasses_json import Undefined, dataclass_json
from marshmallow import fields
from shortuuid import uuid
from surrealdb import Surreal
from surrealdb.ws import ConnectionState, SurrealPermissionException


from classes import config, secrets

log = logging.getLogger(__name__)


@dataclass
class NoResultError(Exception):
    """No results were returned from the last line of a query."""

    query: str
    params: dict
    output: list[dict[str, Any]]

    def __str__(self):
        return f"Query {self.query} with params {self.params} returned {self.output}"


R = TypeVar("R", bound="Resource")


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
        await self.connection.use("kolkra", "main")
        log.info("Database setup complete!")

    async def ateardown(self):
        log.info("Closing SurrealDB database...")
        await self.connection.close()
        log.info("Database closed!")

    async def get(self, obj_type: type[R], obj_id: str) -> Optional[R]:
        if not self.connection:
            await self.asetup()
        log.info("Getting %s", obj_id)
        if data := await self.connection.select(obj_id):
            obj = obj_type.from_dict(data)
        else:
            obj = None
        assert isinstance(obj, obj_type)
        log.info("Found %s", obj)
        return obj

    async def run_query(self, obj_type: type[R], query: str, **params) -> list[R]:
        """Runs a SurrealQL query on the database and returns a list of objects. Only the last line's results are returned.

        Args:
            obj_type (type[R]): The type of object to expect.
            query (str): The query to be executed.

        Raises:
            NoResultError: No results were returned.

        Returns:
            list[R]: The results of the query.
        """
        if (
            not self.connection
        ) or self.connection.client_state != ConnectionState.CONNECTED:
            await self.asetup()
        log.info("Running query %s with params %s", query, params)
        output = await self.connection.query(query, params)
        try:
            results = output[-1]["result"]
        except (IndexError, KeyError) as e:
            raise NoResultError(query, params, output) from e
        else:
            log.info("Found %s", results)
            return schema(obj_type).load(results, many=True)


connection = DatabaseConnection()
# Handles schema caching--schemas aren't cached by my ser/de library...
schema_cache: dict = {}


def schema(t: type[R]):
    try:
        return schema_cache[t]
    except KeyError:
        s = t.schema(exclude=(f.name for f in dc_fields(t) if f.name.startswith('_')))
        schema_cache[t] = s
        return s


def debug_print(
    c: callable, label: str
) -> callable:  # sourcery skip: replace-interpolation-with-fstring
    def inner(*args, **kwargs):
        try:
            o = c(*args, **kwargs)
            log.info("%s: %s(%s %s) -> %s" % (label, c.__name__, args, kwargs, o))
            return o
        except Exception as e:
            log.info(
                "%s: %s(%s %s) -> EXCEPTION %s" % (label, c.__name__, args, kwargs, e)
            )
            raise e

    return inner


def dt_ser(dt: datetime.datetime | str):
    match type(dt):
        case datetime.datetime:
            return dt.isoformat()
        case str:
            return dt


def dt_deser(dt: datetime.datetime | str):
    match type(dt):
        case datetime.datetime:
            return dt
        case str:
            return datetime.datetime.fromisoformat(dt)


dt_metadata = {
    "dataclasses_json": {
        "encoder": dt_ser,
        "decoder": dt_deser,
        "mm_field": fields.DateTime(format="iso"),
    }
}

emote_metadata = {
    "dataclasses_json": {
        "encoder": str,
        "decoder": discord.PartialEmoji.from_str,
        "mm_field": fields.String(),
    }
}

color_metadata = {
    "dataclasses_json": {
        "encoder": lambda x: x.value,
        "decoder": discord.Color,
        "mm_field": fields.Int(),
    }
}


def now():
    return datetime.datetime.now(datetime.timezone.utc)


@dataclass_json(undefined=Undefined.EXCLUDE)
@dataclass
class Resource:
    id: Optional[str] = field(
        default=None, kw_only=True
    )  # Unique SurrealDB-formatted record ID. Generated post-init if not provided.
    created_at: datetime.datetime = field(
        default_factory=now, kw_only=True, metadata=dt_metadata
    )
    updated_at: Optional[datetime.datetime] = field(
        default=None, kw_only=True, metadata=dt_metadata
    )

    def __post_init__(self):
        if not self.id:
            self.id = f"{self.__class__.__name__}:{uuid()}"

    def embed(self, bot: discord.Bot, fields: dict[str, str] = None) -> discord.Embed:
        if fields is None:
            fields = {}
        embed = discord.Embed(title=self.__class__.__name__).set_footer(
            text=f"ID: {self.id} | Made with 💚 by M1N3R"
        )
        for k, v in fields.items():
            embed.add_field(name=k, value=v)
        if getattr(self, "owner_id", None) is not None:
            owner = bot.get_guild(config["guild"]).get_member(self.owner_id)
            embed.set_author(name=owner.display_name, icon_url=owner.display_avatar.url)
        return embed

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if (
            name != "updated_at"
        ):  # prevent setting updated_at from causing a recursive loop
            self.updated_at = now()

    async def store(self):
        """Stores the object in the database through the DatabaseConnection."""
        if not connection.connection:
            await connection.asetup()
        try:
            record = await connection.connection.create(
                self.id, data=self.to_dict(encode_json=True)
            )
            log.info("Inserted %s", record)
        except SurrealPermissionException:  # Raised when the object already exists
            record = await connection.connection.update(
                self.id, data=self.to_dict(encode_json=True)
            )
            log.info("Updated %s", record)

    async def refresh(self):
        """Refresh the Resource's data from the database."""
        new_self = await connection.get(self.__class__, self.id)
        for field, value in asdict(new_self).items():
            setattr(self, field, value)

    async def delete(self):
        """Delete the Resource from the database."""
        if not connection.connection:
            await connection.asetup()
        await connection.connection.delete(self.id)
