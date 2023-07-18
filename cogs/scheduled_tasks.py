"""A module for handling persistent scheduled events, such as starting/ending fests, revoking mod actions when they expire, etc.
# How it works
    The module primarily consists of a `Resource` subclass named `Task`.
    To serialize the task's callback, we use the `marshal` module in the Python standard library to compile the function to bytecode, then encode it as a base85 string so SurrealDB can handle it.
    On load, we automatically fetch, deserialize, and reschedule any pending tasks from the database. Any pending tasks whose scheduled run times have lapsed are executed immediately, unless `run_late` is False, in which case the task is cancelled.
    When a task is executed or cancelled, it is removed from the database so that it does not run again.
# Limitations
    Very large or complex functions take up a lot of space in the database once compiled. 
        - Make sure that any scheduled tasks don't have very complex callbacks. 
        - Consider using a "stub" function that simply imports and calls the actual callback function for scheduled runs of complex functions.
    Non-serializable arguments to callback functions are not supported for persistence.
    Class methods are not supported due to issues with recursion.
"""
import asyncio
import datetime
import hashlib
import logging
import marshal
import os
import types
from base64 import b85decode, b85encode
from dataclasses import dataclass, field
from typing import Any, Callable

import discord
from marshmallow import ValidationError, fields

from helpers.db_handling_sdb import Resource, connection, dt_metadata, now

loop: asyncio.AbstractEventLoop

log = logging.getLogger(__name__)


def store_task_code(fn: Callable) -> str:
    bytecode = marshal.dumps(fn.__code__)
    bc_hash = hashlib.md5(bytecode).hexdigest()
    path = f"temp/task_code/{bc_hash}"
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(bytecode)
    return bc_hash


def get_task_code(bc_hash: str) -> Callable:
    with open(f"temp/task_code/{bc_hash}", "rb") as f:
        bytecode = f.read()
    return types.FunctionType(marshal.loads(bytecode), globals())


fn_metadata = {
    "dataclasses_json": {
        "encoder": store_task_code,
        "decoder": get_task_code,
        "mm_field": fields.String(),
    }
}
ignore_metadata = {
    "dataclasses_json": {
        "encoder": lambda x: None,
        "decoder": lambda x: None,
        "mm_field": fields.Raw(
            load_only=True, load_default=None
        ),
    }
}


@dataclass
class Task(Resource):
    scheduled_for: datetime.datetime = field(metadata=dt_metadata)
    callback: Callable = field(metadata=fn_metadata)
    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)
    run_late: bool = True
    task_type: str = None
    _handle: asyncio.TimerHandle = field(metadata=ignore_metadata, default=None)

    def inner(self):
        log.info(
            "Fired task %s(%s, %s) scheduled for %s",
            self.callback.__name__,
            ", ".join(str(v) for v in self.args),
            ", ".join(f"{k}={str(v)}" for k, v in self.kwargs.items()),
            self.scheduled_for.isoformat(),
        )
        # Call the inner callback, and await it if it's async
        r = self.callback(*self.args, **self.kwargs)
        if asyncio.iscoroutine(r):
            loop.create_task(r)
        # The task is done! We don't need/want to keep it in the database anymore.
        loop.create_task(self.delete())

    def _handle_overdue(self):
        if (self.scheduled_for - now()).total_seconds() <= 0:
            if self.run_late:
                self.inner()
                return True
            log.info(
                "Cancelled late task %s(%s, %s) scheduled for %s",
                self.callback.__name__,
                ", ".join(str(v) for v in self.args),
                ", ".join(f"{k}={v}" for k, v in self.kwargs.items()),
                self.scheduled_for.isoformat(),
            )
            loop.create_task(self.delete())

    def __post_init__(self):
        super().__post_init__()
        if not self.task_type:
            self.task_type = self.callback.__qualname__

    def schedule(self):
        global loop
        if self._handle_overdue(): return
        # Schedule the task on the event loop
        self._handle = loop.call_later(
            delay=(self.scheduled_for - now()).total_seconds(), callback=self.inner
        )
        log.info(
            "Scheduled task %s(%s, %s) for %s",
            self.callback.__name__,
            ", ".join(str(v) for v in self.args),
            ", ".join(f"{k}={v}" for k, v in self.kwargs.items()),
            self.scheduled_for.isoformat(),
        )

    async def cancel(self):
        log.info(
            "Cancelled task %s(%s, %s) scheduled for %s",
            self.callback.__name__,
            ", ".join(str(v) for v in self.args),
            ", ".join(f"{k}={v}" for k, v in self.kwargs.items()),
            self.scheduled_for.isoformat(),
        )
        # Cancel the task on the loop
        if self._handle:
            self._handle.cancel()
        # Delete the task from the database to prevent it from coming back on restart
        await self.delete()

    async def delete(self):
        await super().delete()
        bytecode = marshal.dumps(self.callback.__code__)
        bc_hash = hashlib.md5(bytecode).hexdigest()
        if not await connection.run_query(
            Task, "SELECT * FROM Task WHERE callback = $hash", hash=bc_hash
        ):
            os.remove(f"temp/task_code/{bc_hash}")


async def restore_tasks():
    tasks = await connection.run_query(Task, "SELECT * FROM Task;")
    for task in tasks:
        task.schedule()


def setup(bot: discord.Bot):
    global loop
    loop = bot.loop
    loop.create_task(restore_tasks())


def teardown(bot: discord.Bot):
    pass
