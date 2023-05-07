from dataclasses import dataclass
import logging

import discord
from classes import Resource
from helpers import db_handling

log = logging.getLogger(__name__)


@dataclass
class PlayerProfile(Resource):
    friend_code: str = None
    main_lan_server: str = None
    xtag: str = None
    ign: str = None

    def embed(self):
        embed = super().embed(
            {
                "NSO Friend Code": self.friend_code,
                "Main classic LAN play server": self.main_lan_server,
                "XLink Kai username": self.xtag,
                "In-game name": self.ign,
            }
        )
        embed.title = "Player Info"
        return embed


class ProfileEditor(discord.ui.Modal):
    def __init__(self, user_id) -> None:
        super().__init__(title="Profile Editor")
        self.profile: PlayerProfile = db_handling.search(
            PlayerProfile, cond=lambda x: x.owner_id == user_id
        ) or PlayerProfile(user_id)
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
                "placeholder": "joinsg.net:11453",
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
            self.add_item(discord.ui.InputText(**field, required=False))

    async def callback(self, interaction: discord.Interaction):
        for i, v in enumerate(["friend_code", "main_lan_server", "xtag", "ign"]):
            self.profile.__setattr__(v, self.children[i].value)
        db_handling.store(self.profile)
        await interaction.response.send_message(
            "✅ Profile updated.", embed=self.profile.embed(), ephemeral=True
        )


class ProfileCog(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    root = discord.SlashCommandGroup(name="profile")

    @root.command(
        name="edit", description="Open the player profile editor to edit your info."
    )
    async def edit(self, ctx: discord.ApplicationContext):
        """Edit the information in your player profile using the profile editor."""
        await ctx.send_modal(ProfileEditor(ctx.author.id))

    @root.command(name="get", description="Check out your or someone else's profile.")
    async def get(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member = None,
        ephemeral: bool = True,
    ):
        """Find the player profile for either yourself or another user.

        Args:
            user (Member, optional): The user to look up. Defaults to yourself.
            ephemeral (bool, optional): Whether to hide the result from other users. Defaults to True.
        """
        target = user or ctx.author
        if profile := db_handling.search(
            PlayerProfile, cond=lambda x: x.owner_id == target.id
        ):
            await ctx.send_response(embed=profile.embed(), ephemeral=ephemeral)
        else:
            await ctx.send_response("🫥 Player profile not found.", ephemeral=True)


def setup(bot: discord.Bot):
    bot.add_cog(ProfileCog(bot))
    log.info("Cog initialized")
