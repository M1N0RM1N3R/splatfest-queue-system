import asyncio
import logging
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from typing import Any, Callable, Iterable, Optional, TypeVar

import discord
from dataclasses_json import DataClassJsonMixin
from discord.ext.pages import Paginator
from marshmallow import fields
from PIL import Image

from bot import config
from helpers import emote_images
from helpers.command_checks import StaffLevel, in_channel, required_staff_level
from helpers.common_views import ButtonSelect, Confirm
from helpers.db_handling_sdb import (
    Resource,
    color_metadata,
    connection,
    emote_metadata,
    now,
)
from helpers.embed_templates import EmbedStyle
from helpers.image_recoloring import recolor
from helpers.interactive_input import reaction_input, text_input

log = logging.getLogger(__name__)


@dataclass
class FestScore(DataClassJsonMixin):
    open: int = 0
    tricolor: int = 0
    bivalves: int = 0


@dataclass
class FestTeam(DataClassJsonMixin):
    name: str
    emote: discord.Emoji | discord.PartialEmoji | str = field(metadata=emote_metadata)
    unicode_emoji: str
    role_id: int
    color: discord.Color = field(metadata=color_metadata)
    total_score: FestScore = field(default_factory=FestScore)

    def embed(self, show_score: bool = False):
        embed = discord.Embed(
            title=f"Team {self.name}",
            description=f"<@&{self.role_id}>",
            color=self.color,
        ).set_thumbnail(url=emote_images.url(self.emote))
        if show_score:
            embed.add_field(
                name="Clout Totals",
                value="\n".join(
                    f"**{k.title()}**: {v}"
                    for k, v in self.total_score.__dict__.items()
                ),
            )
        return embed


class FestTitle(Enum):
    FAN = 0
    FIEND = 1
    DEFENDER = 2
    CHAMPION = 3
    RULER = 4


"""@dataclass
class FestProfile(Resource):
    owner_id: int
    team: FestTeam
    score: FestScore = field(default_factory=FestScore)
    pro_g2: Glicko2 = field(default_factory=Glicko2)
    pro_peak_rating: int = 1500
    title: FestTitle = FestTitle.FAN
    progress: int = 0"""


class FestState(Enum):
    PENDING = 0
    SNEAK_PEEK = 1
    MAIN_EVENT = 2
    HALFTIME_REPORT = 3
    CLOSED = 4
    RESULTS_RELEASED = 5


@dataclass
class Fest(Resource):
    question: str
    teams: list[FestTeam]
    state: FestState = FestState.PENDING
    halftime_leaders: Optional[FestTeam] = None

    def embed(self, bot):
        return super().embed(
            bot,
            {
                "Question": self.question,
                "Status": self.state.name,
                "Halftime Leader": self.halftime_leaders.name
                if self.halftime_leaders
                else None,
            },
        )


T = TypeVar("T")


def next_filter_map(
    iter: Iterable[T],
    predicate: Callable[[T], Any],
) -> Optional[T]:
    """Returns the first truthy value returned by a mapping operation on the iterable.
    Args:
        iter (Iterable[T]): The iterable to search.
        predicate (Callable[[T], Any]): The predicate function to apply to the iterable.
    Returns:
        Optional[T]: The first truthy value returned, or None if all values are falsy.
    """
    try:
        return next(filter(lambda x: x, map(predicate, iter)))
    except StopIteration:
        return None


class PledgeBoxButton(discord.ui.Button):
    parent: "PledgeBox"
    team: FestTeam

    def __init__(self, parent, team):
        self.parent = parent
        self.team = team
        super().__init__(label=self.team.name, emoji=self.team.emote)

    async def callback(self, interaction: discord.Interaction):
        await self.parent.fest.refresh()
        if self.parent.fest.state not in [
            FestState.SNEAK_PEEK,
            FestState.MAIN_EVENT,
            FestState.HALFTIME_REPORT,
        ]:
            await interaction.response.send_message(
                embed=EmbedStyle.AccessDenied.value.embed(
                    title="Fest not open",
                    description="This fest is not currently open.",
                ),
                ephemeral=True,
            )
        elif team_role := next_filter_map(
            [team["role"] for team in config["fest"]["teams"]],
            lambda x: interaction.user.get_role(x),
        ):
            await interaction.response.send_message(
                embed=EmbedStyle.AccessDenied.value.embed(
                    title="Already joined team",
                    description=f"You have already joined Team {team_role.name}.",
                ),
                ephemeral=True,
            )
        else:
            confirm = Confirm()
            msg = await interaction.response.send_message(
                embed=EmbedStyle.Question.value.embed(
                    title="Join this team?",
                    description=f"Are you sure you want to join Team {self.team.name}? **You will not be able to switch teams later.**",
                ),
                view=confirm,
                ephemeral=True,
            )
            await confirm.wait()
            if confirm.value == True:
                await interaction.user.add_roles(
                    discord.Object(self.team.role_id),
                    reason="Selected team at pledge box",
                )
                await interaction.edit_original_response(
                    embed=EmbedStyle.Ok.value.embed(
                        description=f"You have joined Team {self.team.name}. Go get 'em!"
                    ),
                    view=None,
                )


class PledgeBox(discord.ui.View):
    fest: Fest

    def __init__(self, fest: Fest):
        self.fest = fest
        super().__init__(
            *[PledgeBoxButton(self, team) for team in self.fest.teams], timeout=None
        )

    def embed(self):
        return discord.Embed(
            title=self.fest.question,
            description="Select a team below to join the fest!\n**PLEASE NOTE**: By selecting a team, you consent to being pinged for matchmaking during the fest.",
        )


async def active_fest() -> Fest:
    result = await connection.run_query(
        Fest,
        "SELECT * FROM Fest WHERE state = $sneak_peek OR state = $main_event OR state = $halftime_report",
        sneak_peek=FestState.SNEAK_PEEK.value,
        main_event=FestState.MAIN_EVENT.value,
        halftime_report=FestState.HALFTIME_REPORT.value,
    )
    try:
        return result[0]
    except IndexError:
        return None


def recolor_logo(fest: Fest):
    """Helper function to recolor the Splatfest logo.

    Args:
        fest (Fest): The Fest whose colors to use.

    Returns:
        bytes: The recolored logo, in PNG format, ready to upload to Discord via Guild.edit().
    """
    image = Image.open("splatfest_logo.png")
    for base_color, team in zip(
        [(40, 81, 237), (247, 251, 83), (173, 174, 174)], fest.teams
    ):
        new_color = (team.color.r, team.color.g, team.color.b)
        image = recolor(image, base_color, new_color)

    container = BytesIO()
    image.save(container, format="png")
    return container.getvalue()


T = TypeVar("T")


async def button_prompt(
    title: str,
    description: str,
    options: list[T],
    ctx: discord.ApplicationContext,
    msg: discord.Message = None,
) -> tuple[T, discord.Message]:
    """Helper function for handling button prompts.

    Args:
        title (str): The heading of the prompt embed.
        description (str): The description (question) for the prompt.
        options (list[T]): A list of options the user may choose from. Maximum length is 25.
        ctx (discord.ApplicationContext): The ApplicationContext for the prompt to run under.
        msg (discord.Message, optional): The message to edit to display the prompt, omit or pass in None to post a new message. Defaults to None.

    Raises:
        TimeoutError: The prompt has timed out.

    Returns:
        tuple[T, discord.Message]: The option the user selected, and the edited message, that can be passed back into the function for a chain of prompts.
    """
    view = ButtonSelect(options, ctx.author)
    msg_params = dict(
        embed=EmbedStyle.Question.value.embed(
            title=title,
            description=description,
        ),
        view=view,
    )
    msg = await msg.edit(**msg_params) if msg else await ctx.respond(**msg_params)
    if await view.wait():
        raise TimeoutError()
    else:
        return (view.selected, msg)


async def respond(ctx: discord.ApplicationContext, embed_style: EmbedStyle, **kwargs):
    await ctx.respond(embed=embed_style.value.embed(**kwargs))


async def _clear_role(loop, role: discord.Role):
    """Removes all members from a role.

    Args:
        role (discord.Role): The role to clear.
    """
    await asyncio.gather(
        *[loop.create_task(member.remove_roles(role)) for member in list(role.members)]
    )


class FestCog(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    root = discord.SlashCommandGroup(
        name="fest",
        description="Commands for handling server custom Splatfests.",
    )
    admin = root.create_subgroup(
        name="admin",
        description="Administrative commands for controlling fests.",
        checks=[required_staff_level(StaffLevel.admin)],
    )

    @admin.command()
    async def new(
        self,
        ctx: discord.ApplicationContext,
        question: str,
        number_of_teams: int = len(config["fest"]["teams"]),
    ):
        """Run through the interactive setup process for a new fest.

        Args:
            question (str): The question the fest asks.
        """
        if number_of_teams not in range(2, len(config["fest"]["teams"]) + 1):
            await ctx.respond(
                embed=EmbedStyle.Error.value.embed(
                    title="Team count out of bounds",
                    description=f'There are {len(config["fest"]["teams"])} fest teams set up in the config file.',
                )
            )
        team_names: list[str] = []
        for i, team in zip(range(number_of_teams), config["fest"]["teams"]):
            await ctx.respond(
                embed=EmbedStyle.Question.value.embed(
                    title=f"Team names ({i+1}/{number_of_teams})",
                    description=f"What's the **new team name** for <@&{team['role']}>?",
                ).add_field(name="Example", value="Gear")
            )
            team_names.append(await text_input(ctx))
        team_icons: list[discord.Emoji | discord.PartialEmoji | str] = []
        for i, team_name in enumerate(team_names):
            msg = await ctx.respond(
                embed=EmbedStyle.Question.value.embed(
                    title=f"Team icons ({i+1}/{len(team_names)})",
                    description=f"React to this message with the emote for **Team {team_name}'s icon**.",
                )
            )
            team_icons.append(await reaction_input(ctx, msg))
        team_emojis: list[discord.Emoji | discord.PartialEmoji | str] = []
        for i, team_name in enumerate(team_names):
            msg = await ctx.respond(
                embed=EmbedStyle.Question.value.embed(
                    title=f"Team emojis ({i+1}/{len(team_names)})",
                    description=f"React to this message with the **Unicode emoji for Team {team_name}**.",
                )
            )
            team_emojis.append(await reaction_input(ctx, msg, allow_custom=False))
        team_colors: list[discord.Color] = []
        for i, team_name in enumerate(team_names):
            await ctx.respond(
                embed=EmbedStyle.Question.value.embed(
                    title=f"Team colors ({i+1}/{len(team_names)})",
                    description=f"Enter the **color code** for **Team {team_name}**.",
                ).add_field(
                    name="Examples", value="#8a19f7\nrgb(138, 25, 247)\ndark_purple"
                )
            )
            team_colors.append(
                await text_input(ctx, discord.ext.commands.ColorConverter())
            )
        compiled_team_data = zip(
            team_names,
            team_icons,
            team_emojis,
            config["fest"]["teams"],
            team_colors,
        )
        teams = [
            FestTeam(name, icon, emoji, config_team["role"], color)
            for name, icon, emoji, config_team, color in compiled_team_data
        ]
        fest = Fest(question, teams)
        confirm = Confirm()
        await ctx.respond(
            embeds=[
                EmbedStyle.Question.value.embed(
                    title="Confirmation",
                    description="Okay, here's what I got from you. Does this look good?",
                ).add_field(name="Question", value=question)
            ]
            + [team.embed() for team in teams],
            view=confirm,
        )
        await confirm.wait()
        if confirm.value:
            await fest.store()
            await ctx.respond(
                embed=EmbedStyle.Ok.value.embed(
                    description=f"Saved the fest under the ID `{fest.id}`."
                )
            )

    @admin.command(
        name="list", description="Thumb through the list of fests in the database."
    )
    async def _list(self, ctx: discord.ApplicationContext):
        """Thumb through the list of fests in the database, in reverse chronological order of creation. Handy for grabbing the ID for use in other commands."""
        await ctx.defer()
        fests: list[Fest] = await connection.run_query(
            Fest, "SELECT * FROM Fest ORDER BY created_at DESC"
        )
        pager = Paginator(
            [
                [fest.embed(ctx.bot)]
                + [team.embed(show_score=True) for team in fest.teams]
                for fest in fests
            ]
        )
        await pager.respond(ctx.interaction)

    @admin.command(description="Create a pledge box for a fest.")
    async def pledge_box(self, ctx: discord.ApplicationContext):
        """Regenerate the pledge box if it breaks."""
        fest = await active_fest()
        if not fest:
            await ctx.respond(
                embed=EmbedStyle.Error.value.embed(
                    title="No active fest",
                    description="There isn't an active fest to create a pledge box for.",
                )
            )
        box = PledgeBox(fest)
        channel = ctx.guild.get_channel(config["fest"]["pledge_box_channel"])
        await channel.send(view=box, embed=box.embed())
        await ctx.respond(
            embed=EmbedStyle.Ok.value.embed(
                description=f"Pledge box posted in {channel.mention}."
            )
        )

    async def multi_step(self, *futures: tuple[asyncio.Future, Optional[str]]):
        tasks = [
            self.bot.loop.create_task(future, name or task.__name__)
            for future, name in futures
        ]

        await asyncio.gather(tasks)
        return tasks

    @admin.command()
    async def sneak_peek(self, ctx: discord.ApplicationContext, fest_id: str):
        """Prepare the server for a fest.
        Edits roles, channels, and even recolors the server icon, all completely automatically. (Assuming nothing goes wrong)

        Args:
            fest_id (str): The fest to prepare for.
        """
        await ctx.defer()
        fest = await connection.get(Fest, fest_id)
        if not fest:
            await ctx.respond(
                embed=EmbedStyle.Error.value.embed(
                    title="Fest not found",
                    description=f"You can find the ID of the fest you're looking for with {self._list.mention}.",
                )
            )
            return
        confirm = Confirm()
        await ctx.respond(
            embed=EmbedStyle.Warning.value.embed(
                title="Edit server settings?",
                description=textwrap.dedent(
                    f"""\
                If you click "Confirm", I will:
                - Remove all members from team roles
                - Edit team roles with the team info for this fest
                - Change the server icon to a recolored version with the team colors
                - Create a pledge box message in <#{config['fest']['pledge_box_channel']}>
                - Rename the fest channels to match the fest
                Are you sure you want to continue?
                """
                ),
            ),
            view=confirm,
        )
        await confirm.wait()
        if not confirm.value:
            return

        box = PledgeBox(fest)
        tasks = self.multi_step(
            *[
                (
                    _clear_role(ctx.bot.loop, team.role),
                    f"Clearing team role {team.role.mention}",
                )
                for team in fest.teams
            ]
            + [
                (
                    team.role.edit(
                        name=team.name,
                        color=team.color,
                        icon=await ctx.bot.http.get_from_cdn(team.emote.url),
                        reason=f"{ctx.author} used /fest admin server_setup",
                    ),
                    f"Updating team role {team.role.mention}",
                )
                for team in fest.teams
            ]
            + [
                (
                    ctx.guild.get_channel(channel_id).edit(
                        name=f"{team.unicode_emoji}-{team.name.lower()}-chat",
                        topic=f"{team.unicode_emoji} Hang out, chat, and strategize with your teammates on Team {team.name}.",
                        reason=f"{ctx.author} used /fest admin server_setup",
                    ),
                    f"Updating <#{channel_id}>",
                )
                for team, channel_id in zip(
                    fest.teams, [team["chat"] for team in config["fest"]["teams"]]
                )
            ]
            + [
                (
                    ctx.guild.edit(
                        icon=recolor_logo(fest),
                        reason=f"{ctx.author} used /fest admin server_setup",
                    ),
                    "Changing server icon to recolored logo",
                ),
                (
                    ctx.guild.get_channel(config["fest"]["pledge_box_channel"]).send(
                        view=box, embed=box.embed()
                    ),
                    "Posting pledge box",
                ),
                (
                    ctx.guild.get_channel(config["fest"]["pledge_box_channel"]).edit(
                        name=f"{''.join([team.unicode_emoji for team in fest.teams])}-team-select",
                        topic=f"{''.join([team.unicode_emoji for team in fest.teams])} Join a team and climb to victory! Choose wisely, as once you take a side, there's no going back.",
                        reason=f"{ctx.author} used /fest admin server_setup",
                    ),
                    f'Updating <#{config["fest"]["pledge_box_channel"]}>',
                ),
                (
                    ctx.guild.get_channel(config["fest"]["open_channel"]).edit(
                        name=f"{''.join([team.unicode_emoji for team in fest.teams])}-open",
                        topic=f"{''.join([team.unicode_emoji for team in fest.teams])} Discuss the fest, matchmake, and log games, all in one place.",
                        reason=f"{ctx.author} used /fest admin server_setup",
                    ),
                    f'Updating <#{config["fest"]["open_channel"]}>',
                ),
                (
                    ctx.guild.get_channel(config["fest"]["category"]).edit(
                        name=f"{''.join([team.unicode_emoji for team in fest.teams])} {fest.question}",
                        reason=f"{ctx.author} used /fest admin server_setup",
                    ),
                    f'Updating <#{config["fest"]["category"]}>',
                ),
            ]
        )

        fest.state = FestState.SNEAK_PEEK
        await fest.store()

        results_list = []
        for task in tasks:
            if exc := task.exception():
                results_list.append(f"❌ {task.get_name()}: {exc}")
            else:
                results_list.append(f"✅ {task.get_name()}")
        results_text = "\n".join(results_list)
        await ctx.send_followup(
            embed=EmbedStyle.Ok.value.embed(
                title="Done!",
                description=f"Here's the results of all the operations:\n{results_text}\n\n✅ = success\n❌ = failed",
            )
        )

    @admin.command()
    async def start(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        fest = active_fest()
        if not fest:
            await ctx.respond

    @admin.command()
    async def halftime_report(self, ctx: discord.ApplicationContext):
        """Publish the halftime report."""
        await ctx.defer()
        fest = await active_fest()
        if not fest:
            return
        fest.halftime_leaders = max(fest.teams, key=lambda team: team.total_score.open)
        fest.state = FestState.HALFTIME_REPORT
        await fest.store()
        announce_channel: discord.TextChannel = ctx.guild.get_channel(
            config["announcements_channel"]
        )
        embed = EmbedStyle.Announcement.value.embed(
            title="Halftime!",
            description="It's time for a halftime Clout check! Who's in the lead so far, and who will be playing catch-up in Tricolor and Bicolor battles? Let's find out!",
        )
        for team in fest.teams:
            embed.add_field(name=team.name, value=f"||{team.total_score.open}||p")
        msg = await announce_channel.send(
            f"@announce @festers {' '.join([f'<@&{team.role_id}>' for team in fest.teams])}",
            embed=embed,
        )
        await msg.publish()

        await ctx.respond(
            embed=EmbedStyle.Ok.value.embed(
                description="Halftime report released, Tricolor/Bicolor battles opened."
            )
        )

    @admin.command()
    async def close(self, ctx: discord.ApplicationContext):
        """End the fest."""
        await ctx.defer()
        if fest := await active_fest():
            fest.state = FestState.CLOSED
            await fest.store()

            embed = EmbedStyle.Announcement.value.embed(
                title="Fest closed!",
                description="The fest has ended. Who will come out on top? Find out when the final results are released shortly.",
            )

            announce_channel: discord.TextChannel = ctx.guild.get_channel(
                config["announcements_channel"]
            )

            msg = await announce_channel.send(
                f"@announce @festers {' '.join([f'<@&{team.role_id}>' for team in fest.teams])}",
                embed=embed,
            )
            await msg.publish()

            await ctx.respond(
                embed=EmbedStyle.Ok.value.embed(
                    description="Fest has been closed. No more game reports or team selections are allowed."
                )
            )

    @admin.command()
    async def release_results(self, ctx: discord.ApplicationContext, fest_id: str):
        """Announce the final results of the fest.

        Args:
            fest_id (str): The fest whose results to announce.
        """
        await ctx.defer()
        fest: Fest = await connection.get(Fest, fest_id=fest_id)
        if not fest:
            await ctx.respond(
                embed=EmbedStyle.Error.value.embed(
                    title="Fest not found",
                    description=f"You can find the ID of the fest you're looking for with {self._list.mention}.",
                )
            )
            return
        elif fest.state == FestState.RESULTS_RELEASED:
            confirm = Confirm()
            await ctx.respond(
                embed=EmbedStyle.Question.value.embed(
                    title="Re-release results?",
                    description="The results for this fest have already been released. Are you sure you want to announce them again?",
                )
            )
            await confirm.wait()
            if not confirm.value:
                return

        total_scores = {team: 0 for team in fest.teams}

        def category(
            name: str,
            description: str,
            criteria: Callable[[FestTeam], int],
            point_value: int,
        ) -> discord.Embed:
            embed = discord.Embed(
                title=f"{name} | {point_value}p", description=description
            )
            winners = []
            highest = 0
            for team in fest.teams:
                score = criteria(team)
                embed.add_field(name=f"{team.emote} {team.name}", value=f"||{score}||")
                if score > highest:
                    winners = [team]
                    highest = score
                elif score == highest:
                    winners.append(team)
            embed.add_field(
                name="Winner",
                value=f"||{' & '.join([f'{team.emote} {team.name}'] for team in winners)}||",
                inline=False,
            )
            for team in winners:
                team.total_score += score
            return embed

        # Votes, worth 10p
        votes = category(
            name="Votes",
            description="This category goes to the team with the most members!",
            criteria=lambda team: len(ctx.guild.get_role(team.role_id).members),
            point_value=10,
        )

        # Open Clout, worth 12p
        open_clout = category(
            name="Open Clout",
            description="This category goes to the team with the most Open Clout!",
            criteria=lambda team: team.total_score.open,
            point_value=12,
        )

        # Tricolor Clout, worth 15p
        tricolor_clout = category(
            name="Tricolor Clout",
            description="This category goes to the team with the most Tricolor Clout!",
            criteria=lambda team: team.total_score.tricolor,
            point_value=15,
        )

        announcement_embed = EmbedStyle.Announcement.value.embed(
            name="Fest Results",
            description=f"The final results for {' vs '.join([team.name for team in fest.teams])} are in!",
        )

        total_scores_embed = category(
            "",
            description="It all comes down to this. Who will take it all?",
            criteria=lambda team: total_scores[team],
            point_value=0,
        )
        total_scores_embed.title = "FINAL RESULTS"

        thank_you_embed = discord.Embed(
            title="Thank you for playing!",
            description="On behalf of everyone on the Splatfest staff team, I'd like to thank everyone who came out to play, from the bottom of all three of my hearts.\nDon't forget to claim your LANarchy bonus by typing `.1st`, `.2nd`, or `.3rd` (depending on your final placement) in a LANarchy channel!",
        )

        announce_channel: discord.TextChannel = ctx.guild.get_channel(
            config["announcements_channel"]
        )

        msg = await announce_channel.send(
            f"@announce @festers {' '.join([f'<@&{team.role_id}>' for team in fest.teams])}",
            embeds=[
                announcement_embed,
                votes,
                open_clout,
                tricolor_clout,
                total_scores_embed,
                thank_you_embed,
            ],
        )
        await msg.publish()

        fest.state = FestState.RESULTS_RELEASED
        await fest.store()

        await ctx.respond(
            embed=EmbedStyle.Ok.value.embed(
                title="Results published",
                description="The results have been published! Take a deep breath. You did it! 🎉",
            )
        )

    @admin.command()
    async def server_cleanup(self, ctx: discord.ApplicationContext):
        """Handles the process of cleaning up after a fest has ended."""
        confirm = Confirm()
        await ctx.respond(
            embed=EmbedStyle.Warning.value.embed(
                title="Edit server settings?",
                description=textwrap.dedent(
                    f"""\
                If you click "Confirm", I will:
                - Remove all members from team roles
                - Change the server icon back to normal
                - Hide the fest category from @/everyone
                Are you sure you want to continue?
                """
                ),
            ),
            view=confirm,
        )
        await confirm.wait()
        if not confirm.value:
            return
        tasks = self.multi_step(
            *[
                (
                    _clear_role(ctx.bot.loop, ctx.guild.get_role(team["role"])),
                    f"Clearing <@&{team['role']}>",
                )
                for team in config["fest"]["teams"]
            ]
            + [
                (
                    ctx.guild.edit(
                        icon=open("splatfest_logo.png", "rb"),
                        reason=f"{ctx.author} used /fest admin server_cleanup",
                    ),
                    "Resetting server icon",
                ),
                (
                    ctx.guild.get_channel(config["fest"]["category"]).set_permissions(
                        ctx.guild.default_role,
                        view_channel=False,
                        reason=f"{ctx.author} used /fest admin server_cleanup",
                    ),
                    f"Hiding {ctx.guild.get_channel(config['fest']['category']).mention} from @/everyone",
                ),
            ]
        )
        results_list = []
        for task in tasks:
            if exc := task.exception():
                results_list.append(f"❌ {task.get_name()}: {exc}")
            else:
                results_list.append(f"✅ {task.get_name()}")
        results_text = "\n".join(results_list)
        await ctx.send_followup(
            embed=EmbedStyle.Ok.value.embed(
                title="Done!",
                description=f"Here's the results of all the operations:\n{results_text}\n\n✅ = success\n❌ = failed",
            )
        )

    report = root.create_subgroup(
        name="report",
        description="Commands for reporting game results",
    )

    @report.command(name="open", checks=[in_channel(config["fest"]["open_channel"])])
    async def report_open(self, ctx: discord.ApplicationContext):
        """Answer the questions to tally an Open game during a fest."""
        await ctx.defer()
        if fest := await active_fest():
            if fest.state not in [FestState.MAIN_EVENT, FestState.HALFTIME_REPORT]:
                await ctx.respond(
                    embed=EmbedStyle.AccessDenied.value.embed(
                        title="Fest not underway",
                        description="The fest is not currently open.",
                    )
                )

            (unbalanced, msg) = await button_prompt(
                title="Unbalanced match?",
                description="Was there an uneven number of players, or any disconnects?",
                options=["Yes", "No"],
                ctx=ctx,
            )
            if unbalanced == "Yes":
                (winners_count, msg) = await button_prompt(
                    title="Winning players count",
                    description="How many players were on the **winning** team at the end of the game?",
                    options=list(range(1, 5)),
                    ctx=ctx,
                    msg=msg,
                )
                (losers_count, msg) = await button_prompt(
                    title="Losing players count",
                    description="How many players were on the **losing** team at the end of the game?",
                    options=list(range(1, 5)),
                    ctx=ctx,
                    msg=msg,
                )
                ratio = losers_count / winners_count
            else:
                ratio = 1.0
            (winners, msg) = await button_prompt(
                title="Who won?",
                description="Select the team that won the game.",
                options=fest.teams,
                ctx=ctx,
                msg=msg,
            )
            points = int(ratio * 12)
            winners.total_score.open += points
            await fest.store()
            await msg.edit(
                embed=EmbedStyle.Ok.value.embed(
                    title="Game tallied", description="Open game has been tallied."
                )
                .add_field(name="Winners", value=winners.name)
                .add_field(
                    name="Open Clout awarded", value=f"**{winners.name}**: {points}"
                ),
                view=None,
            )
        else:
            await ctx.respond(
                embed=EmbedStyle.Error.value.embed(
                    title="No active fest",
                    description="There is no Casual Splatfest or Revengefest currently underway.",
                ),
            )

    @report.command(
        name="tricolor", checks=[in_channel(config["fest"]["tricolor_channel"])]
    )
    async def report_tricolor(self, ctx: discord.ApplicationContext):
        # sourcery skip: low-code-quality
        await ctx.defer()
        fest = await active_fest()
        if not fest:
            await ctx.respond(
                embed=EmbedStyle.Error.value.embed(
                    title="No active fest",
                    description="There is no Casual Splatfest or Revengefest currently underway.",
                ),
            )
            return
        elif fest.state != FestState.HALFTIME_REPORT:
            await respond(
                ctx,
                EmbedStyle.AccessDenied,
                title="Fest not in second half",
                description="The halftime report has not been released yet.",
            )
            return
        elif len(fest.teams) < 3:
            await respond(
                ctx,
                EmbedStyle.Error,
                title="Not enough teams",
                description="There must be at least 3 teams competing in a fest in order to play Tricolor Battles.",
            )
            return

        clout_awarded: dict[FestTeam, int] = {}
        (valid, msg) = await button_prompt(
            title="Valid match?",
            description="Tricolor matches are valid only if they are either 2v4v2 or 1v2v1, and there were no disconnects.",
            options=["Yes", "No"],
            ctx=ctx,
        )
        if valid == "No":
            await msg.edit(
                embed=EmbedStyle.AccessDenied.value.embed(
                    title="Invalid match",
                )
            )
            return

        teams = list(fest.teams)
        (defenders, msg) = await button_prompt(
            title="Defenders",
            description="Who was on the defending team this game?",
            options=teams,
            ctx=ctx,
            msg=msg,
        )
        teams.remove(defenders)

        (winning_side, msg) = await button_prompt(
            title="Winning side",
            description="Which side won the game?",
            options=["Defenders", "Attackers"],
            ctx=ctx,
            msg=msg,
        )

        if winning_side == "Defenders":
            clout_awarded[defenders] = 72 * (
                1.5 if defenders == fest.halftime_leaders else 1
            )

        else:
            (first_place, msg) = await button_prompt(
                title="First place",
                description="Which attacking team came in first place?",
                options=teams,
                ctx=ctx,
                msg=msg,
            )
            teams.remove(first_place)

            if len(teams) > 1:
                (second_place, msg) = await button_prompt(
                    title="Second place",
                    description="Which attacking team came in second place?",
                    options=teams,
                    ctx=ctx,
                    msg=msg,
                )

            else:
                second_place = teams.pop(0)

            clout_awarded[first_place] = 48 * (
                1.5 if first_place != fest.halftime_leaders else 1
            )
            clout_awarded[second_place] = 40 * (
                1.5 if first_place != fest.halftime_leaders else 1
            )

        for team, clout in clout_awarded.items():
            clout = int(clout * ((team.total_score.bivalves * 0.25) + 1))
            team.total_score.tricolor += clout

        await msg.edit(
            embed=EmbedStyle.Ok.value.embed(
                title="Game tallied", description="Tricolor game has been tallied."
            )
            .add_field(name="Defenders", value=defenders.name)
            .add_field(name="Winners", value=winning_side)
            .add_field(
                name="Tricolor Clout awarded",
                value="\n".join(
                    f"**{team.name}**: {clout}{f' (Bivalve Bonus: {(((team.total_score.bivalves + 1) * 0.25) + 1)}x)' if team.total_score.bivalves > 0 else ''}"
                    for team, clout in clout_awarded.items()
                ),
            ),
            view=None,
        )

        for team in clout_awarded:
            team.total_score.bivalves = max(0, team.total_score.bivalves - 1)
        await fest.store()

    @report.command(
        name="bicolor", checks=[in_channel(config["fest"]["tricolor_channel"])]
    )
    async def report_bicolor(self, ctx: discord.ApplicationContext):
        """Answer the questions to tally a Bicolor game during a fest."""
        await ctx.defer()
        fest = await active_fest()
        if not fest:
            await ctx.respond(
                embed=EmbedStyle.AccessDenied.value.embed(
                    title="No active fest",
                    description="There is no Casual Splatfest or Revengefest currently underway.",
                ),
            )
            return
        elif fest.state != FestState.HALFTIME_REPORT:
            await respond(
                ctx,
                EmbedStyle.AccessDenied,
                title="Fest not in second half",
                description="The halftime report has not been released yet.",
            )
            return
        clout_awarded: dict[FestTeam, int] = {}
        (valid, msg) = await button_prompt(
            title="Valid match?",
            description="Bicolor matches must be even, with no disconnects.",
            options=["Yes", "No"],
            ctx=ctx,
        )
        if valid == "No":
            return await msg.edit(
                embed=EmbedStyle.AccessDenied.value.embed(
                    title="Invalid match",
                )
            )
        (winners, msg) = await button_prompt(
            title="Who won?",
            description="Select the team that won the game.",
            options=fest.teams,
            ctx=ctx,
            msg=msg,
        )
        winners.total_score.bivalves += 1
        await fest.store()
        await msg.edit(
            embed=EmbedStyle.Ok.value.embed(
                title="Game tallied", description="Bicolor game has been tallied."
            )
            .add_field(name="Winners", value=winners.name)
            .add_field(
                name="Bivalves awarded",
                value=f"**{winners.name}**: 1 (Total: {winners.total_score.bivalves})",
            ),
            view=None,
        )


def setup(bot: discord.Bot):
    bot.add_cog(FestCog(bot))
    log.info("Cog initialized")
