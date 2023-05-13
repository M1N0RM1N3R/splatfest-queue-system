from dataclasses import dataclass
import logging
import discord
from cogs.db_handling_sdb import run_query, Resource, NoResultError

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
    user_id: int

    def __init__(self, user_id: int):
        self.user_id = user_id

    async def build(self) -> 'ProfileEditor':
        super().__init__(title="Profile Editor")
        try:
            self.profile: PlayerProfile = (await run_query(
                PlayerProfile,
                "SELECT * FROM PlayerProfile WHERE owner_id = $id",
                id=self.user_id,
            ))[0]
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
        return self

    async def callback(self, interaction: discord.Interaction):
        for i, v in enumerate(["friend_code", "main_lan_server", "xtag", "ign"]):
            self.profile.__setattr__(v, self.children[i].value)
        await self.profile.store()
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
        await ctx.send_modal(await ProfileEditor(ctx.author.id).build())

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
        try:
            profile = (await run_query(
                PlayerProfile,
                "SELECT * FROM PlayerProfile WHERE owner_id = $id",
                id=target.id,
            ))[0]
        except IndexError:
            await ctx.send_response("🫥 Player profile not found.", ephemeral=True)
        else:
            await ctx.send_response(embed=profile.embed(), ephemeral=ephemeral)


def setup(bot: discord.Bot):
    bot.add_cog(ProfileCog(bot))
    log.info("Cog initialized")
