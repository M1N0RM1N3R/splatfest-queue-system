from classes import db_root, Resource
import logging
from typing import Callable

log = logging.getLogger(__name__)


class ObjectExists(Exception):
    pass


async def store(obj: Resource, upsert: bool = True):
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


async def get(obj_type: str, id: str, none_if_missing: bool = True):
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
        return db_root[obj_type][id]
    except KeyError:
        if none_if_missing:
            return None
        else:
            raise


async def search(
    obj_type: str, cond: Callable[[Resource], bool], single_object: bool = True
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
        f"Searching {obj} objects with cond {cond}, single_object={single_object}"
    )
    try:
        table = db_root[obj_type]
    except KeyError:
        db_root[obj_type] = {}
        return None
    if return_multiple:
        return filter(cond, table)
    return next((v for v in db_root[obj_type].values() if cond(v)), None)


async def delete(obj_type: str, id: str):
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
