import logging
from dataclasses import dataclass
from typing import Optional

import discord

from classes import config
from helpers.db_handling_sdb import Resource, connection

log = logging.getLogger(__name__)


@dataclass
class PlayerProfile(Resource):
    owner_id: int  # The Discord user ID that owns this resource.
    friend_code: Optional[str] = None
    main_lan_server: Optional[str] = None
    xtag: Optional[str] = None
    ign: Optional[str] = None

    def embed(self, bot: discord.Bot):
        embed = super().embed(
            bot,
            {
                "NSO Friend Code": self.friend_code or "Not set",
                "Main classic LAN play server": self.main_lan_server or "Not set",
                "XLink Kai username": self.xtag or "Not set",
                "In-game name": self.ign or "Not set",
            },
        )
        embed.title = "Player Info"
        return embed


class ProfileEditor(discord.ui.Modal):
    user_id: int
    bot: discord.Bot

    def __init__(self, user_id: int, bot: discord.Bot):
        self.user_id = user_id
        self.bot = bot

    async def build(self) -> "ProfileEditor":
        super().__init__(title="Profile Editor")
        try:
            self.profile: PlayerProfile = (
                await connection.run_query(
                    PlayerProfile,
                    "SELECT * FROM PlayerProfile WHERE owner_id = $id",
                    id=self.user_id,
                )
            )[0]
        except IndexError:
            self.profile = PlayerProfile(self.user_id)
        for field in [
            {
                "label": "NSO Friend Code",
                "placeholder": "SW-1234-5678-9012",
                "value": self.profile.friend_code,
                "min_length": 12,
                "max_length": 17,
            },
            {
                "label": "Main classic LAN play server",
                "placeholder": "lan-play.example:11453",
                "value": self.profile.main_lan_server,
                "min_length": 9,
            },
            {
                "label": "XLink Kai username",
                "placeholder": "kolkraintraining",
                "value": self.profile.xtag,
            },
            {
                "label": "In-game name",
                "placeholder": "Kolkra",
                "value": self.profile.ign,
                "max_length": 10,
            },
        ]:
            self.add_item(discord.ui.InputText(required=False, **field))
        return self

    async def callback(self, interaction: discord.Interaction):
        for i, v in enumerate(["friend_code", "main_lan_server", "xtag", "ign"]):
            self.profile.__setattr__(v, self.children[i].value)
        await self.profile.store()
        await interaction.response.send_message(
            embeds=[
                EmbedStyle.Ok.value.embed(description="Profile updated."),
                self.profile.embed(self.bot),
            ],
            ephemeral=True,
        )


class ProfileCog(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    root = discord.SlashCommandGroup(name="profile")

    @root.command(name="edit")
    async def edit(self, ctx: discord.ApplicationContext):
        """Edit the information in your player profile using the profile editor."""
        await ctx.send_modal(await ProfileEditor(ctx.author.id, self.bot).build())

    @root.command(name="get", description="Check out your or someone else's profile.")
    async def get(
        self,
        ctx: discord.ApplicationContext,
        user: Optional[discord.Member] = None,
        ephemeral: bool = False,
    ):
        """Find the player profile for either yourself or another user.

        Args:
            user (Member, optional): The user to look up. Defaults to yourself.
            ephemeral (bool, optional): Whether to hide the result from other users. Defaults to False.
        """
        await ctx.defer(ephemeral=ephemeral)
        target = user or ctx.author
        try:
            profile = (
                await connection.run_query(
                    PlayerProfile,
                    "SELECT * FROM PlayerProfile WHERE owner_id = $id",
                    id=target.id,
                )
            )[0]
        except IndexError:
            await ctx.respond(
                embed=EmbedStyle.Error.value.embed(
                    title="Profile not found",
                    description="I couldn't find this user's profile.",
                ),
                ephemeral=True,
            )
        else:
            await ctx.respond(embed=profile.embed(self.bot), ephemeral=ephemeral)


def setup(bot: discord.Bot):
    bot.add_cog(ProfileCog(bot))
    log.info("Cog initialized")
