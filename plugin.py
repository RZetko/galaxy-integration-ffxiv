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
    SLEEP_CHECK_RUNNING = 5
    SLEEP_CHECK_RUNNING_ITER = 0.01

    def __init__(self, reader, writer, token):
        super().__init__(Platform.FinalFantasy14, __version__, reader, writer, token)
        self._ffxiv_api = FFXIVAPI()
        self._game_instances = None
        self._task_check_for_running  = None
        self._last_state = LocalGameState.None_

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
            self._last_state = LocalGameState.None_

            return []

        self._last_state = LocalGameState.Installed

        return [ LocalGame(game_id='final_fantasy_xiv', local_game_state = self._last_state)]

    async def get_owned_games(self):
        dlcs = list()
        install_folder = ffxiv_tools.get_installation_folder() + "\\game\\sqpack\\"
        dlclist = [ item for item in os.listdir(install_folder) if os.path.isdir(os.path.join(install_folder, item)) ]

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

        license_type = LicenseType.SinglePurchase

        return [ Game(game_id = 'final_fantasy_xiv', game_title = 'Final Fantasy XIV: A Realm Reborn', dlcs = dlcs, license_info = LicenseInfo(license_type = license_type)) ]

    async def get_game_times(self):
        pass

    async def import_game_times(self, game_ids: List[str]) -> None:
        pass
    
    async def get_friends(self):
        friends = list()
        account_friends = self._ffxiv_api.get_account_friends()

        for friend in account_friends:
            friends.append(FriendInfo(friend['ID'], friend['Name']))

        return friends

    async def launch_game(self, game_id):
        if game_id != 'final_fantasy_xiv':
            return

        self._game_instances[0].run_game()

    async def install_game(self, game_id):
        # subprocess.Popen(await self._ffxiv_api.download_installer(), creationflags=0x00000008)
        pass

    async def uninstall_game(self, game_id: str):
        self._game_instances[0].delete_game()
        pass

    async def get_unlocked_achievements(self, game_id: str, context) -> List[Achievement]:
        achievements = list()

        for achievement in self._ffxiv_api.get_account_achievements():
            achievements.append(Achievement(int(achievement['Date']), achievement['ID']))

        return achievements

    async def start_achievements_import(self, game_ids: List[str]) -> None:
        # self.requires_authentication()
        await super()._start_achievements_import(game_ids)

    def tick(self):
        if not self._task_check_for_running or self._task_check_for_running.done():
            self._task_check_for_running = asyncio.create_task(self.task_check_for_running_func())

    async def task_check_for_running_func(self):

        if self._last_state == LocalGameState.None_:
            await asyncio.sleep(self.SLEEP_CHECK_RUNNING)
            return

        if not self._game_instances:
            await asyncio.sleep(self.SLEEP_CHECK_RUNNING)
            return

        #get exe names
        target_exes = list()
        target_exes.append("ffxivlauncher64.exe")
        target_exes.append("ffxiv.exe")
        target_exes.append("ffxiv_dx11.exe")
        target_exes.append("ffxivlauncher.exe")

        #check processes
        running = False

        for process in psutil.process_iter():
            try:
                if process.name().lower() in target_exes:
                    running = True
                    break
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue

            await asyncio.sleep(self.SLEEP_CHECK_RUNNING_ITER)

        #update state
        new_state = None

        if running:
            new_state = LocalGameState.Installed | LocalGameState.Running
        else:
            new_state = LocalGameState.Installed

        if self._last_state != new_state:
            self.update_local_game_status(LocalGame("final_fantasy_xiv", new_state))
            self._last_state = new_state

        await asyncio.sleep(self.SLEEP_CHECK_RUNNING)

def main():
    create_and_run_plugin(FinalFantasyXIVPlugin, sys.argv)

if __name__ == "__main__":
    main()