import datetime
import logging
import random
from dataclasses import dataclass
import discord
import discord.ext.commands as cmd
from captcha.audio import AudioCaptcha
from captcha.image import ImageCaptcha
from classes import config
from helpers.command_checks import is_admin_or_dev
from helpers.response_embeds import EmbedStyle

audio = AudioCaptcha()
image = ImageCaptcha()
log = logging.getLogger(__name__)
unverified_role = lambda bot: bot.get_guild(config["guild"]).get_role(
    config["captcha"]["unverified_role"]
)  # Using a lambda becase this will return None before the bot is authenticated with Discord.


class StartView(discord.ui.View):
    def __init__(self, bot: discord.Bot, member: discord.Member):
        super().__init__(timeout=None)
        self.bot = bot
        self.member = member
        self.cooldown_until = datetime.datetime.now()

    @discord.ui.button(label="Start verification", style=discord.ButtonStyle.green)
    async def start(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                embed=EmbedStyle.AccessDenied.value.embed(
                    title="Cannot verify others",
                    description=f"You can't start verification for someone else! Please find and use your own verification prompt, or regenerate it with {self.bot.get_command('captcha regenerate').mention}.",
                ),
                ephemeral=True,
            )
        elif not interaction.user.get_role(config["captcha"]["unverified_role"]):
            await interaction.response.send_message(
                embed=EmbedStyle.Ok.value.embed(
                    title="Already verified",
                    description="Looks like you've already passed verification!",
                ),
                ephemeral=True,
            )
        elif self.cooldown_until > datetime.datetime.now():
            await interaction.response.send_message(
                embed=EmbedStyle.Wait.value.embed(
                    description="You can't start verification right now!",
                ).add_field(
                    name="Retry", value=f"<t:{int(self.cooldown_until.timestamp())}:R>"
                ),
                ephemeral=True,
            )
        else:
            # Generate a captcha image
            chars = "".join(
                [
                    random.choice("1234567890QWERTYUIOPASDFGHJKLZXCVBNM")
                    for _ in range(5)
                ]
            )
            captcha = image.generate(chars, format="png")
            # Send the captcha image
            try:
                await self.member.send(
                    embed=EmbedStyle.Question.value.embed(
                        title="Solve the CAPTCHA!",
                        description="Please enter the text displayed in the attached CAPTCHA image.",
                    )
                    .add_field(
                        name="Timeout",
                        value=f"<t:{int(datetime.datetime.now().timestamp()) + 120}:R>",
                    ),
                    file=discord.File(captcha, filename="captcha.png")
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    embed=EmbedStyle.Error.value.embed(
                        description="I can't send you DMs! Please allow DMs from server members, then try again.",
                    ),
                    ephemeral=True,
                )
            else:
                self.cooldown_until = datetime.datetime.now() + datetime.timedelta(
                    minutes=2
                )
                await interaction.response.send_message(
                    embed=EmbedStyle.Info.value.embed(
                        title="CAPTCHA sent",
                        description="I just sent you a DM with further instructions.",
                    ),
                    ephemeral=True,
                )
                try:
                    response = await self.bot.wait_for(
                        "message",
                        check=lambda message: message.channel.id
                        == self.member.dm_channel.id
                        and message.author == self.member,
                        timeout=120,
                    )
                except asyncio.TimeoutError:
                    await interaction.response.send_message(
                        embed=EmbedStyle.Error.value.embed(
                            title="Timed out",
                            description="You didn't respond in time! Please try again.",
                        ),
                        ephemeral=True,
                    )
                if response.content.lower() == chars.lower():
                    await self.member.remove_roles(
                        unverified_role(self.bot),
                        reason="Verification passed",
                    )
                    await self.member.send(
                        embed=EmbedStyle.Ok.value.embed(
                            description="You've passed verification! You're ready to fest now.",
                        )
                    )
                else:
                    await self.member.send(
                        embed=EmbedStyle.Error.value.embed(
                            title="Verification failed",
                            description="You entered an incorrect response. You may try again when the current CAPTCHA times out.",
                        )
                    )


prompt_generated: list[int] = []  # list of user IDs that have prompts already generated


class CaptchaCog(discord.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    root = discord.SlashCommandGroup(
        name="captcha",
        description="Commands pertaining to the CAPTCHA verification system",
    )

    @cmd.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Fires when a new member joins the server.

        Args:
            member (discord.Member): The new member.
        """
        global prompt_generated
        prompt_generated.append(member.id)
        await member.add_roles(
            unverified_role(self.bot), reason="Starting verification"
        )
        await self.bot.get_channel(config["captcha"]["verification_channel"]).send(
            member.mention,
            embed=EmbedStyle.Question.value.embed(
                title="Verification required",
                description=f"Welcome to Splatfest, {member.mention}! I just need to make sure that you're not a bot. Click the button below to begin the verification process.",
            ),
            view=StartView(self.bot, member),
        )

    @root.command(checks=[is_admin_or_dev])
    async def verify(self, ctx: discord.ApplicationContext, member: discord.Member):
        """Manually put a member through verification, or regenerate the prompt after a restart.

        Args:
            member (discord.Member): The member to verify.
        """
        await self.on_member_join(member)
        await ctx.send_response(
            embed=EmbedStyle.Ok.value.embed(
                description=f"Started verification for {member.mention}."
            ),
            ephemeral=True,
        )

    @root.command()
    async def regenerate(self, ctx: discord.ApplicationContext):
        """Manually regenerate your verification prompt, in case of a bot restart."""
        global prompt_generated
        if not ctx.author.get_role(config["captcha"]["unverified_role"]):
            await ctx.send_response(
                embed=EmbedStyle.Ok.value.embed(
                    title="Already verified",
                    description="You're already verified! You don't need to regenerate your prompt.",
                ),
                ephemeral=True,
            )
        elif ctx.author.id in prompt_generated:
            await ctx.send_response(
                embed=EmbedStyle.Error.value.embed(
                    description="Your prompt has already been generated!",
                ),
                ephemeral=True,
            )
        else:
            await self.on_member_join(ctx.author)
            await ctx.send_response(
                embed=EmbedStyle.Ok.value.embed(description="Prompt regenerated."),
                ephemeral=True,
            )


def setup(bot: discord.Bot):
    bot.add_cog(CaptchaCog(bot))
    log.info("Cog initialized")
