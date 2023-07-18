import contextlib
import logging
import os
from abc import abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any, Optional
import datetime

import discord
from discord.ext.pages import Paginator

from bot import bot
from cogs.scheduled_tasks import Task, ignore_metadata
from helpers.command_arg_types import timedelta
from helpers.command_checks import (StaffLevel, get_staff_level,
                                    required_staff_level)
from helpers.db_handling_sdb import Resource, connection, now
from helpers.embed_templates import EmbedStyle

log = logging.getLogger(__name__)


@dataclass
class ModAction(Resource):
    issuer_id: int
    target_id: int
    reason: str = field(default=None, kw_only=True)
    auto_lift_task: Task = field(default=None, kw_only=True)

    @property
    def expires(self) -> Optional[datetime.datetime]:
        """Returns the time the restriction is automatically lifted from the auto-lift task."""

        return self.auto_lift_task.scheduled_for if self.auto_lift_task else None

    @property
    @abstractmethod
    def notification(self) -> dict[str, Any]:
        pass

    @abstractmethod
    async def apply(self, until: datetime.datetime = None, notify_target: bool = True):
        if until is not None:
            self._auto_lift_task = Task(
                scheduled_for=until,
                callback=self.lift,
                args=[replace(self, _auto_lift_task=None)],
                task_type=self.__class__.__name__,
            )
            self._auto_lift_task.schedule()
            await self._auto_lift_task.store()
        await self.store()
        try: await bot.get_user(self.target_id).send(**self.notification)
        except (discord.Forbidden, discord.HTTPException): pass

    @abstractmethod
    async def lift(self):
        if self._auto_lift_task and self._auto_lift_task.scheduled_for >= now():
            await self._auto_lift_task.cancel()
        await self.delete()

    @property
    def audit_reason_string(self):
        issuer = str(bot.get_user(self.issuer_id))

        return f"{issuer}: {self.reason}{f' (Expires {self.expires.isoformat()})' if self.expires else ''}"

    def embed(
        self, bot: discord.Bot, show_target: bool = True, show_issuer: bool = True
    ):
        e: discord.Embed = super().embed(bot)
        if show_target:
            e.add_field("Target", f"<@{self.target_id}>")
        if self.reason:
            e.add_field(name="Reason", value=self.reason)
        if self.expires:
            e.add_field(name="Expires", value=discord.utils.format_dt(self.expires))
        if show_issuer:
            issuer = bot.get_guild(config["guild"]).get_member(self.issuer_id)
            e.set_author(name=issuer.display_name, icon_url=issuer.display_avatar.url)


@dataclass
class ServerBan(ModAction):
    @property
    def notification(self):
        embed = EmbedStyle.Banned.value.embed(
            description="You have been banned from the Splatfest server. If you wish to appeal this ban, please click the link below to join the appeals server."
        )
        if self.reason:
            embed.add_field(name="The given reason for your ban is", value=self.reason)
        if self.expires:
            embed.add_field(
                name="Your ban expires", value=discord.utils.format_dt(self.expires)
            )
        appeal_button = discord.ui.View(
            discord.ui.Button(
                label="Appeal", emoji="🔗", url="https://discord.gg/HgjBcmrfa6"
            )
        )
        return {"embed": embed, "view": appeal_button}

    async def apply(self, until, notify_target, del_msg_days=0):
        await super().apply(until, notify_target)

        await bot.get_guild(config["guild"]).ban(
            discord.Object(self.target_id),
            delete_message_days=del_msg_days,
            reason=self.audit_reason_string,
        )

    async def lift(self):
        from bot import bot

        await super().lift()

        await bot.get_guild(config["guild"]).unban(discord.Object(self.target_id))


@dataclass
class Warning(ModAction):
    @property
    def notification(self):
        embed = EmbedStyle.Warning.value.embed(
            description="You have been warned in the Splatfest server. If you believe this is a mistake, please contact staff through ModMail."
        )
        if self.reason:
            embed.add_field(
                name="The given reason for this warning is", value=self.reason
            )
        if self.expires:
            embed.add_field(
                name="This warning expires", value=discord.utils.format_dt(self.expires)
            )
        return {"embed": embed}

    def embed(
        self, bot: discord.Bot, show_target: bool = True, show_issuer: bool = True
    ):
        return (
            super()
            .embed(bot, show_target, show_issuer)
            .add_field(name="Warning #", value=self.count)
        )


channel_mute_perms = discord.PermissionOverwrite(
    send_messages=False,
    send_messages_in_threads=False,
    create_private_threads=False,
    create_public_threads=False,
    add_reactions=False,
    speak=False,
    manage_permissions=False,
    manage_webhooks=False,
)


@dataclass
class ChannelMute(ModAction):
    channel_id: int

    @property
    def notification(self):
        embed = EmbedStyle.Muted.value.embed(
            description=f"You were muted in <#{self.channel_id}>. If you believe this is a mistake, please contact staff through ModMail."
        )
        if self.reason:
            embed.add_field(name="The given reason for this mute is", value=self.reason)
        if self.expires:
            embed.add_field(
                name="This mute expires",
                value=discord.utils.format_dt(self.expires),
            )
        return {"embed": embed}

    async def apply(self, until: datetime.datetime):
        await super().apply(until)

        await bot.get_channel(self.channel_id).set_permissions(
            discord.Object(self.target_id),
            overwrite=channel_mute_perms,
            reason=self.audit_reason_string,
        )

    async def lift(self):
        from bot import bot

        await super().lift()
        await bot.get_channel(self.channel_id).set_permissions(
            discord.Object(self.target_id), overwrite=None
        )


async def mod_checks(
    ctx: discord.ApplicationContext,
    target: discord.Member,
    moderate_target: bool = True,
):
    err = EmbedStyle.Error.value
    if target == ctx.author:
        await ctx.respond(
            embed=err.embed(
                title="Cannot moderate self",
                description="You can't do moderation actions on yourself.",
            ),
        )
        return False
    elif target == ctx.bot.user:
        await ctx.respond(
            embed=err.embed(
                title="Cannot moderate bot",
                description=f"I'm sorry, ~~Dave~~{ctx.author.mention}. I'm afraid I can't do that.",
            ),
        )

        return False
    elif get_staff_level(target) >= get_staff_level(ctx.author):
        await ctx.respond(
            embed=EmbedStyle.AccessDenied.value.embed(
                title="Insufficient staff level",
                description="You can't do moderation actions on someone of a higher or equal staff level than you.",
            )
        )

        return False
    elif moderate_target and target.top_role.position >= ctx.me.top_role.position:
        if target.top_role.position >= user.top_role.position:
            await ctx.respond(
                embed=err.embed(
                    title="Insufficient bot permissions",
                    description=f"I can't moderate {target.mention} because my top role ({ctx.me.top_role.mention}) is below or the same as their top role ({target.top_role.mention}).",
                ),
            )
            return False
    return True


class ModCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(
        name="mod",
        description="Commands for moderating and managing the server.",
        checks=[required_staff_level(StaffLevel.mod)],
    )

    @root.command()
    async def ban(
        self,
        ctx: discord.ApplicationContext,
        target: discord.Member,
        reason: str = None,
        duration: timedelta() = None,
        no_dm: bool = False,
        del_msg_days: discord.Option(int, min_value=0, max_value=7) = 0,
    ):
        """Ban a user from the server.

        Args:
            target (Member): The user to ban.
            reason (str, optional): The reason for the ban. Shows up in the audit log. Defaults to None.
            duration (timedelta, optional): The amount of time after which the ban should expire. Defaults to permanent.
            no_dm (bool, optional): Set True to ban the user without attempting to DM them. Defaults to False.
            del_msg_days (int (0..=7), optional): How many days of past messages to delete. Defaults to 0.
        """
        await ctx.defer()
        if not await mod_checks(ctx, target):
            return
        ban_restriction = ServerBan(
            issuer_id=ctx.author.id, target_id=target.id, reason=reason
        )
        expiration = now() + duration if duration else None
        await ban_restriction.apply(
            until=expiration, notify_target=not no_dm, del_msg_days=del_msg_days
        )
        resp_embed = EmbedStyle.Ok.value.embed(description=f"{target} is now b&.")
        if reason is not None:
            resp_embed.add_field(name="Reason", value=reason)
        if duration is not None:
            resp_embed.add_field(
                name="Expiration", value=discord.utils.format_dt(expiration)
            )
        if del_msg_days > 0:
            resp_embed.add_field(name="Days of messages deleted", value=del_msg_days)
        await ctx.respond(embed=resp_embed)

    @root.command()
    async def unban(
        self, ctx: discord.ApplicationContext, target: discord.User, reason: str = None
    ):
        """Revoke a member's ban.

        Args:
            target (User): The user to unban.
            reason (str, optional): The reason for the unban. Shows up in the audit log. Defaults to None.
        """
        await ctx.defer()
        if not await mod_checks(ctx, target):
            return
        # Check if this user's ban is in the database
        if existing_ban := await connection.run_query(
            ServerBan,
            "SELECT * FROM ServerBan WHERE target_id = $target_id",
            target_id=target.id,
        ):
            # If it's in the database, lift it
            existing_ban[0]: ServerBan
            await existing_ban[0].lift(reason=f"{ctx.author}: {reason}")
        else:
            # If it's not in the database, just revoke the ban in Discord
            await ctx.guild.unban(target, reason=f"{ctx.author}: {reason}")
        resp_embed = EmbedStyle.Ok.value.embed(description=f"{target} is now unb&.")
        if reason is not None:
            resp_embed.add_field(name="Reason", value=reason)
        await ctx.respond(embed=resp_embed)

    @root.command()
    async def warn(
        self, ctx: discord.ApplicationContext, target: discord.Member, reason: str
    ):
        await ctx.defer()
        if not await mod_checks(ctx, target):
            return

        existing_warns = connection.run_query(
            Warning,
            "SELECT * FROM Warning WHERE target_id = $target_id",
            target_id=target.id,
        )
        warn = Warning(
            issuer_id=ctx.author.id,
            target_id=target.id,
            reason=reason,
        )
        await warn.apply()

        await ctx.respond(
            embed=EmbedStyle.Ok.value.embed(
                description=f"{target.mention} has been warned."
            )
            .add_field(name="Reason", value=reason)
            .add_field(name="New warning count", value=len(existing_warns) + 1)
        )

    @root.command()
    async def remove_warning(self, ctx: discord.ApplicationContext, warning_id: str):
        await ctx.defer()
        warning: Warning = connection.get(Warning, warning_id)
        if not await mod_checks(ctx, ctx.guild.get_member(warning.target_id)):
            return
        await warning.lift()
        await ctx.respond(
            embed=EmbedStyle.Ok.value.embed(
                description="Warning removed. It's as if it never existed."
            )
        )

    @root.command()
    async def list_warnings(
        self, ctx: discord.ApplicationContext, user: discord.Member
    ):
        await ctx.defer()
        if existing_warns := connection.run_query(
            Warning,
            "SELECT * FROM Warning WHERE target_id = $target_id ORDER BY created_at;",
            target_id=user.id,
        ):
            warn_embeds = [w.embed(ctx.bot, show_target=False) for w in existing_warns]
            pages = [warn_embeds[i : i + 10] for i in range(0, len(warn_embeds), 10)]
            await Paginator(pages=pages).respond(ctx.interaction)
        else:
            await ctx.respond(
                embed=EmbedStyle.Ok.value.embed(
                    title="No warnings", description=f"{user.mention} has no warnings."
                )
            )

    @discord.slash_command()
    async def my_warnings(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        if existing_warns := connection.run_query(
            Warning,
            "SELECT * FROM Warning WHERE target_id = $target_id ORDER BY created_at;",
            target_id=ctx.author.id,
        ):
            warn_embeds = [
                w.embed(ctx.bot, show_target=False, show_issuer=False)
                for w in existing_warns
            ]
            pages = [warn_embeds[i : i + 10] for i in range(0, len(warn_embeds), 10)]
            await Paginator(pages=pages).respond(ctx.interaction)
        else:
            await ctx.respond(
                embed=EmbedStyle.Ok.value.embed(
                    title="No warnings",
                    description="You have no warnings. Good for you!",
                )
            )

    @root.command()
    async def channel_mute(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.abc.GuildChannel,
        target: discord.Member,
        reason: str = None,
        duration: timedelta() = None,
    ):
        await ctx.defer()
        if not await mod_checks(ctx, target):
            return

        mute = ChannelMute(issuer_id=ctx.author.id, target_id=target.id, reason=reason, channel_id=channel.id)
        expiration = now() + duration if duration else None
        await mute.apply(
            until=expiration
        )
        resp_embed = EmbedStyle.Ok.value.embed(description=f"{target} can no longer speak in {channel.mention}.")
        if reason is not None:
            resp_embed.add_field(name="Reason", value=reason)
        if duration is not None:
            resp_embed.add_field(
                name="Expiration", value=discord.utils.format_dt(expiration)
            )
        await ctx.respond(embed=resp_embed)



def setup(bot: discord.Bot):  # sourcery skip: instance-method-first-arg-name
    bot.add_cog(ModCog(bot))

    log.info("Cog initialized")
