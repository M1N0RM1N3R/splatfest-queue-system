# Not fully implemented
import logging
from math import ceil
import discord

from classes import *

log = logging.getLogger(__name__)

class GameConfirmView(discord.ui.View):
    def __init__(self, winners, losers):
        self.winners = winners
        self.losers = losers
        self.confirmed = []

    def min_confirmers(self) -> int:
        return ceil(len(self.winners + self.losers) / 2 + 0.001)

    @discord.ui.button(label="Looks good!", emoji="✅")
    async def button_confirm(self, button, interaction: discord.Interaction):
        if interaction.user.id not in self.winners + self.losers:
            await interaction.response.send_message("❌ You are not involved in this reported game.", ephemeral=True)
        elif interaction.user.id in self.confirmed:
            await interaction.response.send_message("✅✅ You have already confirmed this game.", ephemeral=True)
        else:
            self.confirmed.append(interaction.user.id)
            if len(self.confirmed) >= self.min_confirmers():
                self.disable_all_items()
                self.stop()
            await interaction.response.edit_message(embed=self.embed(), view=self)

    def embed(self):
        embed = discord.Embed(title="Game Report", description=f"{self.min_confirmers()} of {len(self.winners + self.losers)} players must confirm this game for it to be finalized.")
        for k, v in {
            "Winners": '\n'.join([f"{'✅' if _ in self.confirmed else '⬛'} <@{_}>" for _ in self.winners]),
            "Losers": '\n'.join([f"{'✅' if _ in self.confirmed else '⬛'} <@{_}>" for _ in self.losers]),
        }.items():
            embed.add_field(k, v)
        return embed

async def adjust_ranks(winners, losers):
    w_players = [get_player_by_id(id) for id in winners]
    l_players = [get_player_by_id(id) for id in losers]
    absolute = sum(_.rank + 1 for _ in l_players) / sum(_.rank + 1 for _ in w_players) * config['lanarchy']['diff_multiplier']

    for player in w_players:
        player.rank_points += absolute
        if player.rank_points >= config['lanarchy']['ranks'][player.rank]['points_target']:
            player.rank += 1
            player.rank_points = 150
    for player in l_players:
        player.rank_points -= absolute
        if player.rank_points < 0:
            player.rank -= 1
            player.rank_points = 150


class DevCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(
        name='lanarchy', description='Commands pertaining to the LANarchy system.')

    @root.command(name='game-report', description='Report a game outcome.')
    async def submit(self, ctx: discord.ApplicationContext,
                     winner1: discord.Member,
                     loser1: discord.Member,
                     winner2: discord.Member = None,
                     winner3: discord.Member = None,
                     winner4: discord.Member = None,
                     loser2: discord.Member = None,
                     loser3: discord.Member = None,
                     loser4: discord.Member = None
                     ):
        # Create lists of winners and losers
        winners = [_.id for _ in [winner1, winner2,
                                  winner3, winner4] if _ is not None]
        losers = [_.id for _ in [loser1, loser2,
                                 loser3, loser4] if _ is not None]
        # Confirm result with other players
        confirm_view = GameConfirmView(winners, losers)
        await ctx.send_response(
            f"🗳️ {''.join([f'<@{_}>' for _ in winners+losers])} Please verify that the game result below is correct.",
            view=confirm_view,
            embed=confirm_view.embed()
        )
        await confirm_view.wait()
        # Apply adjustments to ranks if confirmation passes
        if len(confirm_view.confirmed) >= confirm_view.min_confirmers():
            # Game confirmation passed -- apply adjustments
            adjust_ranks(winners, losers)
        else:
            # Game confirmation failed -- don't apply adjustments
            await ctx.send_followup("⌛ Confirmation timed out.")

def setup(bot: discord.Bot):
    bot.add_cog(DevCog(bot))
    log.info("LANarchy cog initialized")
