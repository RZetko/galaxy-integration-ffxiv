import asyncio
import logging
import os
import sys
import modules.psutil as psutil

from typing import List
from version import __version__
from ffxiv.localgame import FFXIVLocalGame
from ffxiv.tools import FFXIVTools
from modules.galaxy.api.errors import BackendError, InvalidCredentials
from modules.galaxy.api.consts import Platform, LicenseType, LocalGameState
from modules.galaxy.api.plugin import Plugin, create_and_run_plugin
from modules.galaxy.api.types import Authentication, NextStep, Dlc, LicenseInfo, Game, GameTime, LocalGame


class FinalFantasyXIVPlugin(Plugin):

    SLEEP_CHECK_RUNNING = 5
    SLEEP_CHECK_RUNNING_ITER = 0.01

    def __init__(self, reader, writer, token):
        super().__init__(Platform.FinalFantasy14, __version__, reader, writer, token)
        # self._gw2_api = GW2API()
        self._game_instances = None
        self._task_check_for_running  = None
        self._last_state = LocalGameState.None_

    async def authenticate(self, stored_credentials=None):
        if not stored_credentials:
            logging.info('No stored credentials')

            AUTH_PARAMS = {
                "window_title": "Login to Guild Wars 2",
                "window_width": 640,
                "window_height": 460,
                "start_uri": self._gw2_api.auth_server_uri(),
                "end_uri_regex": '.*finished'
            }

            if not self._gw2_api.auth_server_start():
                raise BackendError()

            return NextStep("web_session", AUTH_PARAMS)

        else:
            auth_passed = self._gw2_api.do_auth_apikey(stored_credentials['api_key'])
            if not auth_passed:
                logging.warning('plugin/authenticate: stored credentials are invalid')
                raise InvalidCredentials()
            
            return Authentication(self._gw2_api.get_account_id(), self._gw2_api.get_account_name())

    async def pass_login_credentials(self, step, credentials, cookies):
        self._gw2_api.auth_server_stop()

        api_key = self._gw2_api.get_api_key()
        if not api_key:
            logging.error('plugin/pass_login_credentials: api_key is None!')
            raise InvalidCredentials()

        self.store_credentials({'api_key': api_key})
        return Authentication(self._gw2_api.get_account_id(), self._gw2_api.get_account_name())

    async def get_local_games(self):
        self._game_instances = gw2_localgame.get_game_instances()
        
        if len(self._game_instances) == 0:
            self._last_state = LocalGameState.None_
            return []

        self._last_state = LocalGameState.Installed
        return [ LocalGame(game_id='guild_wars_2', local_game_state = self._last_state)]

    async def get_owned_games(self):
        free_to_play = False
        dlcs = list()
        
        for dlc in self._gw2_api.get_owned_games():
            if dlc == 'PlayForFree':
                free_to_play = True
                continue
            if dlc == 'GuildWars2':
                continue

            dlc_id = dlc
            dlc_name = dlc
            if dlc_id == 'HeartOfThorns':
                dlc_name = 'Heart of Thorns'
            elif dlc_id == 'PathOfFire':
                dlc_name = 'Path of Fire'

            dlcs.append(Dlc(dlc_id = dlc_id, dlc_title = dlc_name, license_info = LicenseInfo(license_type = LicenseType.SinglePurchase)))

        license_type = LicenseType.SinglePurchase
        if free_to_play:
            license_type = LicenseType.FreeToPlay

        return [ Game(game_id = 'guild_wars_2', game_title = 'Guild Wars 2', dlcs = dlcs, license_info = LicenseInfo(license_type = license_type)) ]


    async def get_game_times(self):
        pass


    async def import_game_times(self, game_ids: List[str]) -> None:
        pass

    async def launch_game(self, game_id):
        if game_id != 'final_fantasy_xiv':
            return
        
        self._game_instances[0].run_game()


    async def install_game(self, game_id):
        # http://gdl.square-enix.com/ffxiv/inst/ffxivsetup.exe
        pass

    async def uninstall_game(self, game_id: str):
        pass

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
        for instance in self._game_instances:
            target_exes.append(instance.exe_name().lower())

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
            self.update_local_game_status(LocalGame('final_fantasy_xiv', new_state))
            self._last_state = new_state

        await asyncio.sleep(self.SLEEP_CHECK_RUNNING)

    def detect_game_version(self):
        # D:\Program Files\SquareEnix\FINAL FANTASY XIV - A Realm Reborn\game\sqpack
        # ffxiv = base game
        # ex1 = heavensward 
        # ex2 = stormblood
        # ex3 = shadowbringers
        return

def main():
    create_and_run_plugin(FinalFantasyXIVPlugin, sys.argv)

if __name__ == "__main__":
    main()