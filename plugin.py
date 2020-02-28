import os
import sys
import asyncio
import logging
import subprocess
import modules.psutil as psutil
import ffxiv_localgame
import ffxiv_tools

from typing import List
from version import __version__
from ffxiv_api import FFXIVAPI
from modules.galaxy.api.errors import BackendError, InvalidCredentials
from modules.galaxy.api.consts import Platform, LicenseType, LocalGameState
from modules.galaxy.api.plugin import Plugin, create_and_run_plugin
from modules.galaxy.api.types import Achievement, Authentication, NextStep, Dlc, LicenseInfo, Game, GameTime, LocalGame, FriendInfo

class FinalFantasyXIVPlugin(Plugin):
    SLEEP_CHECK_STATUS = 5
    SLEEP_CHECK_RUNNING_ITER = 0.01

    def __init__(self, reader, writer, token):
        super().__init__(Platform.FinalFantasy14, __version__, reader, writer, token)
        self._ffxiv_api = FFXIVAPI()
        self._game_instances = None
        self._task_check_for_running  = None
        self._check_statuses_task = None
        self._cached_game_statuses = {}

    def tick(self):
        if self._check_statuses_task is None or self._check_statuses_task.done():
            self._check_statuses_task = asyncio.create_task(self._check_statuses())

    async def _check_statuses(self):
        local_games = await self.get_local_games()

        if local_games:
            for game in local_games:
                game.local_game_state = await self._is_running()
                if game.local_game_state == self._cached_game_statuses.get(game.game_id):
                    continue
                self.update_local_game_status(LocalGame(game.game_id, game.local_game_state))
                self._cached_game_statuses[game.game_id] = game.local_game_state
        else:
            self.update_local_game_status(LocalGame("final_fantasy_xiv_shadowbringers", LocalGameState.None_))
            self._cached_game_statuses["final_fantasy_xiv_shadowbringers"] = LocalGameState.None_

        await asyncio.sleep(self.SLEEP_CHECK_STATUS)

    async def authenticate(self, stored_credentials=None):
        if not stored_credentials:
            logging.info("No stored credentials")

            AUTH_PARAMS = {
                "window_title": "Login to Final Fantasy XIV Lodestone",
                "window_width": 640,
                "window_height": 460,
                "start_uri": self._ffxiv_api.auth_server_uri(),
                "end_uri_regex": ".*finished"
            }

            if not self._ffxiv_api.auth_server_start():
                raise BackendError()

            return NextStep("web_session", AUTH_PARAMS)

        else:
            auth_passed = self._ffxiv_api.do_auth_character(stored_credentials['character_id'])

            if not auth_passed:
                logging.warning("plugin/authenticate: stored credentials are invalid")

                raise InvalidCredentials()
            
            return Authentication(self._ffxiv_api.get_character_id(), self._ffxiv_api.get_character_name())

    async def pass_login_credentials(self, step, credentials, cookies):
        self._ffxiv_api.auth_server_stop()

        character_id = self._ffxiv_api.get_character_id()

        if not character_id:
            logging.error("plugin/pass_login_credentials: character_id is None!")

            raise InvalidCredentials()

        self.store_credentials({'character_id': character_id})

        return Authentication(self._ffxiv_api.get_character_id(), self._ffxiv_api.get_character_name())

    async def get_local_games(self):
        self._game_instances = ffxiv_localgame.get_game_instances()
        
        if len(self._game_instances) == 0:
            return []

        return [ LocalGame(game_id='final_fantasy_xiv_shadowbringers', local_game_state = LocalGameState.Installed)]

    async def get_owned_games(self):
        dlcs = list()
        install_folder = ffxiv_tools.get_installation_folder()
        license_type = LicenseType.SinglePurchase

        if (
            (install_folder is None) or
            (not os.path.exists(install_folder))
        ):
            return [ Game(game_id = 'final_fantasy_xiv_shadowbringers', game_title = 'Final Fantasy XIV: A Realm Reborn', dlcs = dlcs, license_info = LicenseInfo(license_type = license_type)) ]

        dlc_folder = install_folder + "\\game\\sqpack\\"
        dlclist = [ item for item in os.listdir(dlc_folder) if os.path.isdir(os.path.join(dlc_folder, item)) ]

        for dlc in dlclist:
            if dlc == "ffxiv":
                continue

            if dlc == "ex1":
                dlc_id = "Heavensward"
                dlc_name = "Final Fantasy XIV: Heavensward"

            if dlc == "ex2":
                dlc_id = "Stormblood"
                dlc_name = "Final Fantasy XIV: Stormblood"

            if dlc == "ex3":
                dlc_id = "Shadowbringers"
                dlc_name = "Final Fantasy XIV: Shadowbringers"

            dlcs.append(Dlc(dlc_id = dlc_id, dlc_title = dlc_name, license_info = LicenseInfo(license_type = LicenseType.SinglePurchase)))

        return [ Game(game_id = 'final_fantasy_xiv_shadowbringers', game_title = 'Final Fantasy XIV: A Realm Reborn', dlcs = dlcs, license_info = LicenseInfo(license_type = license_type)) ]

    async def get_game_times(self):
        pass

    async def import_game_times(self, game_ids: List[str]) -> None:
        pass
    
    async def get_friends(self):
        friends = list()
        account_friends = self._ffxiv_api.get_account_friends()

        for friend in account_friends:
            friends.append(FriendInfo(str(friend['ID']), friend['Name']))

        return friends

    async def launch_game(self, game_id):
        if game_id != 'final_fantasy_xiv_shadowbringers':
            return

        self._game_instances[0].run_game()
        self.update_local_game_status(LocalGame(game_id, LocalGameState.Installed | LocalGameState.Running))

    async def install_game(self, game_id: str):
        installer_path = self._ffxiv_api.get_installer()

        if (
            (installer_path is None) or
            (not os.path.exists(installer_path))
        ):
            return

        subprocess.Popen(installer_path, creationflags=0x00000008)

    async def uninstall_game(self, game_id: str):
        self._game_instances[0].delete_game()

    async def get_unlocked_achievements(self, game_id: str, context) -> List[Achievement]:
        achievements = list()

        for achievement in self._ffxiv_api.get_account_achievements():
            achievements.append(Achievement(int(achievement['Date']), str(achievement['ID'])))

        return achievements

    async def start_achievements_import(self, game_ids: List[str]) -> None:
        # self.requires_authentication()
        await super()._start_achievements_import(game_ids)

    async def _is_running(self):
        target_exes = [
            "ffxivlauncher64.exe",
            "ffxiv.exe",
            "ffxiv_dx11.exe",
            "ffxivlauncher.exe"
        ]

        running = False

        for process in psutil.process_iter():
            try:
                if process.name().lower() in target_exes:
                    running = True
                    break
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue

            await asyncio.sleep(self.SLEEP_CHECK_RUNNING_ITER)

        return LocalGameState.Installed | LocalGameState.Running if running else LocalGameState.Installed

def main():
    create_and_run_plugin(FinalFantasyXIVPlugin, sys.argv)

if __name__ == "__main__":
    main()
