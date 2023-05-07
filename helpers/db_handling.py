import logging
from typing import Callable, Type

from ZODB import DB
from ZODB.FileStorage import FileStorage

from classes import Resource

log = logging.getLogger(__name__)


class ObjectExists(Exception):
    pass


def store(obj: Resource, upsert: bool = True):
    """Stores an object in the database.

    Args:
        obj (Resource): The object to store.
        upsert (bool, optional): Whether to update an existing object. Defaults to True.

    Raises:
        ObjectExists: Object with the specified ID already exists and `upsert` is False.
    """
    log.debug(f"Storing {obj} object {obj.id}")
    try:
        table = db_root[obj.__class__.__name__]
    except KeyError:
        db_root[obj.__class__.__name__] = table = {}
    try:
        existing = table[obj.id]
    except KeyError:
        table[obj.id] = obj
    else:
        if upsert:
            table[obj.id] = obj
        else:
            raise ObjectExists(
                f"{obj.__class__.__name__} object ID {obj.id} already exists in database."
            )


def get(obj_type: Type[Resource], id: str, none_if_missing: bool = True) -> Resource:
    """Gets a resource based on its ID. Faster than using search().

    Args:
        obj_type (str): The type of object to get.
        id (str): The ID of the object to get.
        none_if_missing (bool, optional): Whether the function should return None if the resource doesn't exist, or raise a KeyError. Defaults to True.

    Returns:
        Resource: The resource object with the specified ID.

    Raises:
        KeyError: Object was not found.
    """
    log.debug(f"Getting {obj_type} object {id}, none_if_missing={none_if_missing}")
    try:
        return db_root[obj_type.__name__][id]
    except KeyError:
        if none_if_missing:
            return None
        else:
            raise


def search(
    obj_type: Type[Resource], cond: Callable[[Resource], bool], single_object: bool = True
) -> Resource | filter:
    """Searches for a given object type that satisfies a given condition.

    Args:
        obj_type (str): The type of object to search for.
        cond (Callable[[Resource], bool]): The condition to check for. Objects that return True are returned here.
        single_object (bool): Whether to return a single object or a filter iterable. Defaults to True.

    Returns:
        Resource | filter: The resulting object or iterable of objects.
    """
    log.debug(
        f"Searching {obj_type} objects with cond {cond}, single_object={single_object}"
    )
    try:
        table = db_root[obj_type]
    except KeyError:
        db_root[obj_type] = {}
        return None
    return (
        next((v for v in db_root[obj_type.__name__].values() if cond(v)), None)
        if single_object
        else filter(cond, table)
    )


def delete(obj_type: str, id: str):
    """Removes a resource from the database.

    Args:
        obj_type (str): The type of object to remove.
        id (str): The ID of the object to remove.
    """
    log.debug(f"Deleting {obj_type} object {id}")
    try:
        table = db_root[obj_type]
    except KeyError:
        db_root[obj_type] = {}
        return
    del db_root[obj_type][id]

storage = FileStorage("database.fs")
db = DB(storage)
connection = db.open()
db_root = connection.root()
log.info("Database initialized")