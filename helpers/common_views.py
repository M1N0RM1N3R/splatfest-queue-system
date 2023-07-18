import contextlib
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

import discord


class Confirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.primary, emoji="✅")
    async def confirm_callback(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        self.value = True
        await self.close(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_callback(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        self.value = False
        await self.close(interaction)

    async def close(self, interaction: discord.Interaction):
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        self.stop()


T = TypeVar("T")


def display_order(thing: any) -> str:
    for attr_name in ["display_name", "name"]:
        with contextlib.suppress(AttributeError):
            return str(getattr(thing, attr_name))
    return str(thing)


class ChoiceButton(discord.ui.Button["ButtonSelect"]):
    def __init__(self, value, parent):
        self.value = value
        self.parent = parent
        super().__init__(
            style=discord.ButtonStyle.secondary, label=display_order(self.value)[:80]
        )

    async def callback(self, interaction: discord.Interaction):
        await self.parent.click(self, interaction)


class ButtonSelect(discord.ui.View):
    choices: list
    user: discord.Member
    selected: Optional = None

    def __init__(self, choices, user):
        super().__init__(disable_on_timeout=True)
        self.choices = choices
        self.user = user
        self.children = [ChoiceButton(value, self) for value in self.choices]

    async def click(self, button, interaction):
        if interaction.user != self.user:
            await interaction.response.send_message(
                embed=EmbedStyle.AccessDenied.value.embed(
                    title="Not for you", description="This menu is not yours."
                ),
                ephemeral=True,
            )
        else:
            self.selected = button.value
            button.style = discord.ButtonStyle.primary
            self.disable_all_items()
            await interaction.response.edit_message(view=self)
            self.stop()
