import asyncio
import datetime
from typing import Callable

import discord
import pyotp
import yaml
from yaml import CBaseLoader

from classes import *

totp = pyotp.TOTP('5YJCKGMRJUK52LSAWCDYEBOTKMOQY4KN')


async def is_owner(
    ctx: discord.ApplicationContext): return await ctx.bot.is_owner(ctx.user)


class AuthModal(discord.ui.Modal):
    def __init__(self):
        self.value = None
        super().__init__(title="Secondary Authentication Required", timeout=60)
        self.add_item(discord.ui.InputText(
            label="TOTP", placeholder='123456', min_length=6, max_length=6))

    async def callback(self, interaction: discord.Interaction):
        self.value = totp.verify(self.children[0].value)
        await interaction.response.defer()


async def wait_for(condition: Callable[..., bool], timeout: float = None, poll_interval: float = 0.1, *args, **kwargs) -> bool:
    if timeout:
        stop_time = datetime.datetime.now() + datetime.timedelta(seconds=timeout)
    while True:
        if condition(*args, **kwargs):
            return True
        elif timeout:
            if datetime.datetime.now() > stop_time:
                return False
        await asyncio.sleep(poll_interval)


class DevCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(
        name='dev', description='Internal commands restricted to M1N3R only.', checks=[is_owner])

    @root.command(name='run')
    async def execute(self, ctx: discord.ApplicationContext, script: str):
        await ctx.defer(ephemeral=True)
        output = str(eval(script) or '✅')
        for i in range(0, len(output), 2000):
            await ctx.send_followup(output[i:i+2000], ephemeral=True)


def setup(bot: discord.Bot):
    bot.add_cog(DevCog(bot))
