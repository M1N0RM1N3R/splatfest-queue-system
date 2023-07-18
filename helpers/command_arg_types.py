import datetime
from typing import Generic, List, TypeVar

import dateparser
import discord
from discord.ext.commands import BadArgument, Converter
from natural.date import compress as hr_duration
from pytimeparse.timeparse import timeparse

from helpers.db_handling_sdb import R, connection


def timestamp_autocomplete(actx: discord.AutocompleteContext) -> List[str]:
    dt = dateparser.parse(actx.value)
    if isinstance(dt, datetime.datetime):
        return [dt.replace(microsecond=0).isoformat()]
    else:
        return [f'❌ Invalid/unknown format: "{actx.value}"']


def timedelta_autocomplete(actx: discord.AutocompleteContext) -> List[str]:
    if seconds := timeparse(actx.value):
        return [hr_duration(seconds)]
    else:
        return [f'❌ Invalid/unknown format: "{actx.value}"']


class TimestampConverter(Converter):
    async def convert(self, ctx, argument):
        if not (res := dateparser.parse(argument)):
            raise BadArgument(f'Invalid/unknown timestamp format: "{argument}"')
        return res.replace(microsecond=0)


def timestamp(**kwargs):
    return discord.Option(
        TimestampConverter, autocomplete=timestamp_autocomplete, **kwargs
    )


class TimeDeltaConverter(Converter):
    async def convert(self, ctx, argument):
        if res := timeparse(argument):
            return datetime.timedelta(seconds=res)
        else:
            raise BadArgument(f'Invalid/unknown duration format: "{argument}"')


def timedelta(**kwargs):
    return discord.Option(
        TimeDeltaConverter,
        autocomplete=timedelta_autocomplete,
        **kwargs,
    )
