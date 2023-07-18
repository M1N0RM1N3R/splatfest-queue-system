import datetime
import os
from abc import abstractmethod
from dataclasses import dataclass, field, replace

import discord

from cogs.scheduled_tasks import Task
from helpers.command_arg_types import timestamp
from helpers.db_handling_sdb import Resource, connection, now
from helpers.embed_templates import EmbedStyle
from math import ceil

bot: discord.Bot


@dataclass
class PollOption:
    name: str
    voter_ids: list[int] = field(default_factory=list)


@dataclass
class Poll(Resource):
    question: str
    channel_id: int = None
    msg_id: int = None
    _close_task: Task = None

    @property
    def ends_at(self) -> datetime.datetime:
        return self._close_task.scheduled_for if self._close_task else None

    @property
    def is_open(self) -> bool:
        return self._close_task.scheduled_for < now() if self._close_task else False

    async def open(self, until: datetime.datetime):
        self._close_task = Task(
            scheduled_for=now() + datetime.timedelta(hours=24),
            callback=self.close,
            args=[replace(self, _close_task=None)],
            task_type=self.__class__.__name__,
        )
        self._close_task.schedule()

    async def close(self):
        await self.get_channel(self.channel_id).get_partial_message(self.msg_id).edit(
            embed=await self.embed()
        )

    async def embed(self, bot: discord.Bot):
        e: discord.Embed = super().embed(bot)
        e.title = self.question
        if poll.is_open:
            e.add_field(
                name="Poll closes", value=discord.utils.format_dt(self.ends_at, "R")
            )
        else:
            e.description = "This poll is closed."
        return e


@dataclass
class MultiChoicePoll(Poll):
    options: list[PollOption] = field(default_factory=list)

    async def embed(self, bot: discord.Bot):
        e = await super().embed(bot)
        if poll.is_open:
            e.description = "Vote for one of the options below."
        else:
            for option in self.options:
                e.add_field(name=option.name, value=f"{len(option.voter_ids)} x ☑️")


class PollOptionButton(discord.ui.Button):
    poll: MultiChoicePoll
    option_index: int

    def __init__(self, poll: MultiChoicePoll, option_index: int):
        self.poll = poll
        self.option_index = option_index
        self.label = poll.options[option_index]

    @property
    def option(self):
        return self.poll.options[self.option_index]

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # Refresh the poll
        await self.poll.refresh()
        # Check that the poll is open
        if not self.poll.is_open():
            await interaction.followup.send_message(
                embed=EmbedStyle.AccessDenied.value.embed(
                    title="Poll closed", description="This poll has ended."
                ),
            )
            return
        # Check that the user hasn't voted on this poll yet
        for option in self.poll.options:
            if interaction.user.id in option.voter_ids:
                await interaction.followup.send_message(
                    embed=EmbedStyle.AccessDenied.value.embed(
                        title="Already voted",
                        description=f"You already voted for **{option.name}**.",
                    )
                )
                return
        # Tally the user's vote
        self.option.voter_ids.append(interaction.user.id)
        await interaction.followup.send_message(
            embed=EmbedStyle.Ok.value.embed(
                title="Vote tallied", description=f"You voted for **{option.name}**."
            )
        )


@dataclass
class ForumPoll(Poll):
    thread_id: int = None

    async def vote_count(self):
        thumbs_ups = [
            "👍",
            "👍🏻",
            "👍🏼",
            "👍🏽",
            "👍🏾",
            "👍🏿",
        ]
        thumbs_downs = [
            "👎",
            "👎🏻",
            "👎🏼",
            "👎🏽",
            "👎🏾",
            "👎🏿",
        ]
        votes: dict[str, tuple[int, int]] = {}
        thread = bot.get_channel(self.thread_id)
        async for message in thread.history(limit=None):
            if message.edited_at or len(message.content) > 1024:
                continue
            up = 0
            down = 0
            for reaction in message.reactions:
                if reaction.emoji in thumbs_ups:
                    up += reaction.count
                elif reaction.emoji in thumbs_downs:
                    down += reaction.count
            votes[message.content] = (up, down)
        return votes

    async def embed(self, bot: discord.Bot):
        e = await super().embed(bot)
        if poll.is_open:
            e.description = "Read through the answers in the thread, and vote for/against them by reacting to them with 👍 or 👎.\nYou may also contribute your own answers.\n**Please note:** Your answer must be less than 1024 characters and not be edited in order for it to count."
        else:
            votes: dict[str, tuple[int, int]] = await self.vote_count()
            top_answers = sorted(votes.items(), key=lambda i: i[1][0] - i[1][1], reverse=True)[:25]
            for answer, votes in top_answers:
                e.add_field(name=f"({votes[0]} x 👍) - ({votes[1]} x 👎) = {v[0] - v[1]}", value=answer)


    async def open(self, until: datetime.datetime):
        await super().open(until)
        thread: discord.Thread = await (
            await bot.get_channel(self.channel_id).fetch_message(self.msg_id)
        ).create_thread(name=self.question)
        await thread.edit(slowmode_delay=21600)
        self.thread_id = thread.id

    async def close(self):
        await bot.get_channel(self.thread_id).archive(locked=True)
        await super().close()


class PollsCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(
        name="polls", description="Set up polls for people to vote in."
    )

    @root.command()
    async def multiple_choice(
        self,
        ctx: discord.ApplicationContext,
        question: str,
        option1: str,
        option2: str,
        option3: str = None,
        option4: str = None,
        option5: str = None,
        close_at: timestamp() = None,
    ):
        await ctx.defer()
        if close_at and close_at < now():
            await ctx.respond(
                embed=EmbedStyle.Error.value.embed(
                    description="You can't set a poll to close in the past."
                )
            )
        poll = MultiChoicePoll(
            question=question,
            options=[
                PollOption(i)
                for i in [option1, option2, option3, option4, option5, option6]
                if i is not None
            ],
            ends_at=close_at or now() + datetime.timedelta(hours=24),
        )
        view = discord.ui.View(
            *[PollOptionButton(poll, i) for i in range(len(poll.options))], timeout=None
        )
        await ctx.respond(embed=await poll.embed(), view=view)


def setup(_bot: discord.Bot):
    global bot
    bot = _bot
    _bot.add_cog(PollsCog(_bot))
