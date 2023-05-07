import datetime
from typing import List

import dateparser
import discord
from natural.date import compress as hr_duration
from pytimeparse.timeparse import timeparse as duration_parse


def timestamp_autocomplete(actx: discord.AutocompleteContext) -> List[str]:
    try:
        return [dateparser.parse(actx.value).replace(microsecond=0).isoformat()]
    except AttributeError:
        return [f'Invalid/unknown format: "{actx.value}"']


def duration_autocomplete(actx: discord.AutocompleteContext) -> List[str]:
    if seconds := duration_parse(actx.value):
        return [hr_duration(seconds)]
    else:
        return [f'Invalid/unknown format: "{actx.value}"']

class TimestampConverter(discord.ext.commands.Converter):
    async def convert(self, ctx, argument):
        if not (res := dateparser.parse(argument)):
            raise discord.ext.commands.BadArgument(f'Invalid/unknown format: "{argument}"')
        res.microsecond = 0
        return res

def timestamp(**kwargs):
    return discord.Option(
        TimestampConverter, autocomplete=timestamp_autocomplete, **kwargs
    )

class DurationConverter(discord.ext.commands.Converter):
    async def convert(self, ctx, argument):
        if res := duration_parse(argument):
            return datetime.timedelta(seconds=res)
        else: raise discord.ext.commands.BadArgument(f'Invalid/unknown format: "{argument}"')

def duration(**kwargs):
    return discord.Option(
        DurationConverter,
        autocomplete=duration_autocomplete,
        **kwargs,
    )
