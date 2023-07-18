import itertools
import logging
import random
import subprocess
from typing import Optional, List, Tuple

import discord
import discord.ext.commands as cmd
from discord.ext import tasks

from classes import *

log = logging.getLogger(__name__)


class GameBoard(discord.ui.View):
    game_name = "Random Game"
    description = (
        "Description of the game, explaining the basic structure and rules of the game."
    )


class To2Button(discord.ui.Button["To2Board"]):
    def __init__(self, row: int, column: int):
        self.row = row
        self.column = column
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=row)

    async def callback(self, interaction: discord.Interaction):
        await self.view.click(self, interaction)


class To2Board(GameBoard):
    game_name = "TickoaTTwo"
    description = """TickoaTTwo is a two-player pen-and-paper style game similar to Tic-Tac-Toe, first described by Oats Jenkins in [this YouTube video](https://www.youtube.com/watch?v=ePxrVU4M9uA).
    The object of the game is to place the last stroke in a horizontal, vertical, or diagonal line of cross symbols. (+)
    Each player is assigned to either the vertical (|) or horizontal (-) stroke that makes up the cross and takes turns placing their stroke on spaces in a 3x3 grid.
    On your turn, you may place your stroke on any space that doesn't already have your stroke on it, except the space that your opponent last placed their stroke."""
    # This tells the IDE or linter that all our children will be GameButtons.
    # This is not required.
    children: List[To2Button]

    EMPTY = "\u200b"  # Empty character
    VERTICAL = "|"
    HORIZONTAL = "-"
    CROSS = "+"

    def __init__(self, player1: discord.Member, player2: discord.Member):
        super().__init__()
        self.board = [[self.EMPTY for _ in range(3)] for _ in range(3)]
        self.last_move: Tuple[int, int] = (None, None)
        self.players = [player1, player2]
        self.turn = random.randint(0, 1)
        for r, c in itertools.product(range(3), range(3)):
            self.add_item(To2Button(r, c))

    async def on_timeout(self) -> None:
        self.disable_all_items()
        await self.message.edit("⌛ This game has timed out.")

    def is_illegal_move(
        self, row: int, column: int, player: discord.Member
    ) -> str | None:
        """Checks if a move is legal.

        Args:
            row (int): The row of the space to check.
            column (int): The column of the space to check.
            player (discord.Member): The player attempting to make the move.

        Returns:
            str | None: An error message if the move is illegal, false otherwise
        """
        if player not in self.players:
            return "⛔ You are not in this game."
        elif player != self.players[self.turn]:
            return "⛔ It's not your turn."
        elif self.board[row][column] in [
            self.VERTICAL if self.turn else self.HORIZONTAL,
            self.CROSS,
        ]:
            return "⛔ You already placed your stroke there."
        elif (row, column) == self.last_move:
            return "⛔ Your opponent just placed their stroke there."
        return None

    async def game_over(self, interaction: discord.Interaction):
        """Handles ending the game when a player wins."""
        self.turn = not self.turn
        for button in self.children:
            button.label = self.board[button.row][button.column]
        self.disable_all_items()
        self.stop()
        await interaction.response.edit_message(
            content=f"🏁 {self.players[self.turn].mention} wins!", view=self
        )

    async def click(self, button: To2Button, interaction: discord.Interaction):
        """Handles the logic of making a move. Called by a game button (To2Button) on click.

        Args:
            button (To2Button): The button that was just clicked.
            interaction (discord.Interaction): The interaction info.
        """
        # Return an error if the move is illegal
        if message := self.is_illegal_move(button.row, button.column, interaction.user):
            return await interaction.response.send_message(message, ephemeral=True)

        # Place the stroke
        space = self.board[button.row][button.column]
        if space == self.EMPTY:
            new = self.VERTICAL if self.turn else self.HORIZONTAL
        elif space == self.HORIZONTAL if self.turn else self.VERTICAL:
            new = self.CROSS
        self.board[button.row][button.column] = new



        # Check for the win condition--three crosses in a horizontal, vertical, or diagonal line.
        def win_check(space1: Tuple[int, int], space2: Tuple[int, int], space3: Tuple[int,int]) -> bool:
            return self.board[space1[0]][space1[1]] == self.CROSS and self.board[space2[0]][space2[1]] == self.CROSS and self.board[space3[0]][space3[1]] == self.CROSS

        # Check horizontal lines
        for row in range(3):
            if win_check(*[(row, col) for col in range(3)]):
                await self.game_over(interaction)
                return

        # Check vertical lines
        for col in range(3):
            if win_check(*[(row, col) for row in range(3)]):
                await self.game_over(interaction)
                return

        # Check diagonal lines
        if win_check((0, 0), (1, 1), (2, 2)):
            await self.game_over(interaction)
            return
        if win_check((0, 2), (1, 1), (2, 0)):
            await self.game_over(interaction)
            return

        # Prepare for next turn
        self.last_move = (button.row, button.column)
        self.turn = not self.turn
        for button in self.children:
            button.disabled = self.is_illegal_move(
                button.row, button.column, self.players[self.turn]
            )
            button.label = self.board[button.row][button.column]

        await interaction.response.edit_message(
            content=f"✅ {self.players[self.turn].mention}'s turn!", view=self
        )


class ChallengeView(discord.ui.View):
    def __init__(
        self,
        challenger: discord.Member,
        opponent: Optional[discord.Member] = None,
        game_type=GameBoard,
    ):
        super().__init__()
        self.challenger = challenger
        self.opponent = opponent
        self.game_type = game_type

    @discord.ui.button(
        label="Accept challenge", emoji="🤝", style=discord.ButtonStyle.primary
    )
    async def accept(self, button, interaction:discord.Interaction):
        if self.opponent and self.opponent != interaction.user:
            return await interaction.response.send_message(
                "❌ This challenge is not for you.", ephemeral=True
            )
        self.opponent = interaction.user
        await interaction.response.edit_message(
            content=f"✅ {interaction.user.mention} accepted {self.challenger.mention}'s challenge!",
            embed=self.embed()
        )
        self.disable_all_items()
        self.stop()

    def embed(self):
        embed = discord.Embed(title=self.game_type.game_name, description=self.game_type.description)
        embed.add_field(name="Challenger", value=self.challenger.mention)
        embed.add_field(name="Opponent", value=self.opponent.mention if self.opponent else "Open challenge")
        embed.set_footer(text="Made with 💚 by M1N3R")
        return embed


class FunCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    root = discord.SlashCommandGroup(
        name="fun", description="Casual minigames, memes, and other random stuff."
    )

    @cmd.Cog.listener()
    async def on_ready(self):
        if not self.motd.is_running():
            self.motd.start()

    @root.command(name="tickoat2", description="Play a game of TickoaTTwo.")
    async def tickoat2(
        self, ctx: discord.ApplicationContext, opponent: Optional[discord.Member] = None
    ):
        """Challenge someone to a game of TickoaTTwo, a two-player pen-and-paper style game based on tic-tac-toe. Place the last stroke in a line of 3 crosses to win!


        Args:
            opponent (Member): The player you want to challenge. Your opponent must accept your challenge before the game will begin. Defaults to an open challenge that anyone can accept.
        """
        challenge = ChallengeView(ctx.author, opponent, To2Board)
        challenge_msg = await ctx.respond(f"⚔️ {opponent.mention} You have been challenged to a game of TickoaTTwo by {ctx.author.mention}!" if opponent else f"⚔️ {ctx.author.mention} is looking for an opponent to play TickoaTTwo!", view=challenge, embed=challenge.embed())
        if await challenge.wait():
            await challenge_msg.edit_original_response(content="⌛ This challenge has timed out.")
        else:
            assert challenge.opponent is not None
            game = To2Board(challenge.challenger, challenge.opponent)
            await challenge_msg.edit_original_response(
                content=f"▶️ The game has started! {game.players[0].mention} is vertical (|) and {game.players[1].mention} is horizontal (-). {game.players[game.turn].mention} won the coin toss and will go first.",
                view=game
            )

    @tasks.loop(minutes=1)
    async def motd(self):
        message = subprocess.run(
            ["fortune", "-n", "128", "-s", "fortunes", "literature", "riddles"],
            stdout=subprocess.PIPE,
        ).stdout.decode("utf-8")
        try:
            await self.bot.change_presence(activity=discord.Game(name=message))
        except Exception:
            log.info("Failed to change presence")


def setup(bot: discord.Bot):
    bot.add_cog(FunCog(bot))
    log.info("Cog initialized")

def teardown(bot:discord.Bot):
    bot.get_cog('FunCog').motd.stop()