import asyncio
import datetime
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List

import discord
from cuid2 import CUID
from glicko2 import Player as Glicko2
from ZODB import DB
from ZODB.FileStorage import FileStorage

config: Dict[str, str | int | float | list | dict] = json.load(open('config.json'))

async def wait_for(condition: Callable[..., bool], timeout: float = None, poll_interval: float = 0.1, *args, **kwargs) -> bool:

    if timeout:
        stop_time = datetime.datetime.now() + datetime.timedelta(seconds=timeout)
    while True:
        if condition(*args, **kwargs):
            return True
        elif timeout:
            if datetime.datetime.now() > stop_time:
                return False
        await asyncio.sleep(poll_interval)

# setup the database
print('Initializing database...', end='')
storage = FileStorage("database.fs")
db = DB(storage)
connection = db.open()
root = connection.root()
print('DONE!')


@dataclass
class Resource:
    id: str = field(default_factory=CUID().generate, kw_only=True)

    def embed(self, fields: Dict[str,str]):
        embed = discord.Embed(title=self.__class__.__name__)
        embed.set_footer(f"Internal ID: {self.id} | Made with <:splatlove:1057108266062196827> by M1N3R")
        for k, v in fields.items():
            embed.add_field(name=k, value=v)
        return embed


@dataclass
class Player(Resource):
    discord_id: int  # The player's Discord user ID.
    rank: int  # The player's rank tier. (0=C, 1=B, 2=A, 3=S, 4=X)
    rank_points: int  # The player's rank points.
    series_wins: int
    series_losses: int
    series_active: bool
    # Player experience, increased by playing matches. Not to be confused with X Power.
    xp: int
    # A Glicko2 rating, implemented using the glicko2 module. (https://pypi.org/project/glicko2/)
    glicko2: Glicko2
    # The player's NSO friend code. Defaults to "Not Set" and can also be set to "Banned" (self explanatory).
    friend_code: str
    # The LAN play server the player prefers to use. Defaults to "Not Set".
    main_lan_server: str
    xtag: str
    ign: str

    def embed(self):
        return super().embed({
            'Rank': f"{self.rank}/{self.rank_points}lrp",
            'XP': self.xp,
            'NSO Friend Code': self.friend_code,
            'Main LAN play server': self.main_lan_server,
            'XLink Kai username': self.xtag,
            'In-game name': self.ign
        })

new_player_info = lambda: {
    'rank': 0,
    'rank_points': 100,
    'series_wins': 0,
    'series_losses': 0,
    'series_active': False,
    'xp': 0,
    'glicko2': Glicko2(),
    'nso_friend_code': 'Not set',
    'main_lan_server': 'Not set',
    'xlink_kai_username': 'Not set'
}

try: root['players']
except KeyError: root['players'] = {}
def get_player_by_id(discord_id):
    try:
        player = root['players'][discord_id]
    except KeyError:
        player = Player(discord_id=discord_id, **new_player_info())
        root['players'][discord_id] = player
    finally:
        return player


class LobbyButtons(discord.ui.View):
    def __init__(self, lobby: 'Lobby'):
        super().__init__(timeout=None)
        self.lobby = lobby

    @discord.ui.button(label='Join', emoji='▶️')
    async def join(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.lobby.try_join(interaction)

    @discord.ui.button(label='Leave', emoji='◀️')
    async def leave(self, button, interaction: discord.Interaction):
        player = get_player_by_id(interaction.user.id)
        if self.lobby.state != LobbyState.JOINABLE:
            return await interaction.response.send_message("❌ That lobby is not joinable.", ephemeral=True)
        else:
            self.lobby.players.remove(player)
            await interaction.response.edit_message(embed=self.lobby.embed())


class CheckInView(discord.ui.View):
    checked_in: List[Player] = []

    def __init__(self, lobby: 'Lobby'):
        super().__init__(timeout=None)
        self.lobby = lobby

    @discord.ui.button(label='Check in', emoji='<:checkactive:1074013348116566086>')
    async def check_in(self, button, interaction: discord.Interaction):
        player = get_player_by_id(interaction.user.id)
        if player in self.checked_in:
            return await interaction.response.send_message("✅✅ You're already checked in.", ephemeral=True)
        elif player not in self.lobby.players:
            return await interaction.response.send_message("❌ You are not in this lobby.", ephemeral=True)
        else:
            return await interaction.response.edit_message(embed=self.embed())

    def embed(self):
        embed = discord.Embed(title="Check-in")
        embed.add_field(name=f'Players ({len(self.checked_in)}/{len(self.lobby.players)})', value='\n'.join(
            [f"{'<:checkactive:1074013348116566086>' if player in self.checked_in else '<:checkinactive:1074013350570242240>'} <@{player.discord_id}>" for player in self.lobby.players]))


class LobbyState(Enum):
    JOINABLE = 0
    CHECK_IN = 1
    IN_PROGRESS = 2
    RESULT_SUBMITTED = 3
    MOD_CALLED = 4
    COMPLETED = 5


active_lobbies: List['Lobby'] = []


def new_lobby_info(bot): return {
    'players': [],
    'bot': bot,
    'join_view': LobbyButtons(),
    'timeout': datetime.datetime.now() + datetime.timedelta(minutes=45),
    'state': LobbyState.JOINABLE
}

@dataclass
class Lobby(Resource):
    lobby_type: str
    players: List[Player]
    teams: List[List[Player]]
    bot: discord.Bot
    join_view: LobbyButtons
    message: discord.Message
    thread: discord.Thread
    timeout: datetime.datetime
    state: LobbyState
    method: str
    _valid_methods = ['nso', 'lan', 'kai']

    async def join_checks(self, player: Player):
        assert self.state == LobbyState.JOINABLE, "This lobby is not joinable."
        assert player not in self.players, "You are already in this lobby."
        for lobby in active_lobbies:
            assert player not in lobby.players, f"You are already in another active lobby at {lobby.message.jump_url}."

    async def try_join(self, interaction: discord.Interaction):
        player = get_player_by_id(interaction.user.id)
        try:
            self.join_checks(player)
        except AssertionError as e:
            return await interaction.response.send_message(f'❌ Could not join this lobby: {e.args[0]}', ephemeral=True)
        else:
            self.players.append(player)
            return await interaction.response.edit_message(embed=self.embed())

    async def is_viable(self):
        return len(self.players) >= 2

    async def check_in(self, punish_no_shows: bool = True):
        assert self.state == LobbyState.JOINABLE
        self.join_view.disable_all_items()
        self.join_view.stop()
        self.state = LobbyState.CHECK_IN
        self.thread = await self.message.create_thread(name=f"{self.lobby_type} Lobby {self.id}")
        check_in_time = 300
        check_in_view = CheckInView(self)
        check_in_msg = await self.thread.send(f"""{''.join([f'<@{player.discord_id}>' for player in self.players])}
        📃🙋 Welcome to the lobby thread! Please click the button below to check in. Any players that don't check in <t:{int(datetime.datetime.now().timestamp() + check_in_time)}:R> will be kicked from the lobby and potentially timeouted.""", view=check_in_view)
        await check_in_msg.pin()
        await wait_for(lambda: len(self.players) == len(check_in_view.checked_in), timeout=300)
        no_shows: List[Player] = []
        for player in self.players:
            if player not in check_in_view.checked_in:
                no_shows.append(player)
        for player in no_shows:
            self.players.remove(player)
        if not self.is_viable():
            for player in no_shows:
                await self.bot.get_guild(config['guild']).get_member(player.discord_id).timeout_for(datetime.timedelta(minutes=10), reason=f"No-showed in {self.lobby_type} lobby")
            await self.thread.send(f"🫥❌ The lobby has been cancelled because {', '.join([f'<@{player.discord_id}>' for player in no_shows])} failed to check in and made the lobby unviable. Players that failed to check in have been timed out for 10 minutes.")
            await self.thread.archive(locked=True)
            await self.bot.get_channel(config['log_channel']).send(f"🫥⏲ Timed out {', '.join([f'<@{player.discord_id}>' for player in no_shows])} for no-showing in {self.lobby_type} lobby. (10 mins)")
            return False
        elif no_shows:
            await self.thread.send(f"🫥✅ {', '.join([f'<@{player.discord_id}>' for player in no_shows])} have been removed from the lobby because they failed to check in. The lobby is still viable and will proceed without them.")

    def embed(self):
        embed = discord.Embed(title=f'{self.lobby_type} Lobby {self._doc_id}')
        for k, v in {
            'Players': '\n'.join([f'<@{player.discord_id}>' for player in self.players]),
            'Method': self.method,
            'Timeout': f'<t:{int(self.timeout.timestamp())}:R>'
        }.items():
            embed.add_field(name=k, value=v)
        return embed


class LANarchyOpenLobby(Lobby):
    lobby_type = "LANarchy (Open)"

    async def join_checks(self, player: Player):
        await super().join_checks(player)


class TriColorLobby(Lobby):
    _valid_methods = ['lan', 'kai']
