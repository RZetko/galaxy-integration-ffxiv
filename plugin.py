import os
import sys
import asyncio
import logging
import subprocess
import datetime
import time
import modules.psutil as psutil
import ffxiv_localgame
import ffxiv_tools

from typing import List, Optional
from version import __version__
from datetime import datetime, timezone, timedelta
from ffxiv_api import FFXIVAPI
from modules.galaxy.api.errors import BackendError, InvalidCredentials
from modules.galaxy.api.consts import Platform, LicenseType, LocalGameState
from modules.galaxy.api.plugin import Plugin, create_and_run_plugin
from modules.galaxy.api.types import Achievement, Authentication, NextStep, Dlc, LicenseInfo, Game, GameTime, LocalGame, FriendInfo

logger = logging.getLogger(__name__)

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
        self._cached_game_statuses_no_launcher = {}
        self._process_check_time = None

    def tick(self):
        if self._check_statuses_task is None or self._check_statuses_task.done():
            self._check_statuses_task = asyncio.create_task(self._check_statuses())

    async def _check_statuses(self):
        local_games = await self.get_local_games()

        if local_games:
            for game in local_games:
                main_process_state = await self._is_running_no_launcher()
                cached_state_no_launcher = self._cached_game_statuses_no_launcher.get(game.game_id) or LocalGameState.None_
                if bool(main_process_state & LocalGameState.Running):
                    #logger.debug("Game client is running")
                    # we were running before, so we need to update play time
                    if bool(cached_state_no_launcher & LocalGameState.Running):
                        current_time = datetime.now(timezone.utc)
                        delta = current_time - self._process_check_time
                        self._add_time_played(game.game_id, delta)
                        self._process_check_time = current_time
                        #logger.debug(f'Added {str(delta)} of play time')
                    # we started to play somewhere between, some time might've been lost, but that's ok
                    else:
                        logger.debug("Started play time tracking")
                        self._cached_game_statuses_no_launcher[game.game_id] = main_process_state
                        self._process_check_time = datetime.now(timezone.utc)
                else:
                    # we stopped playing since last check, so we need to push update play time stats to galaxy
                    if bool(cached_state_no_launcher & LocalGameState.Running):
                        time_played = int(self._get_time_played(game.game_id) / timedelta(minutes=1))
                        time_stamp = self._get_last_played_time(game.game_id)
                        self.update_game_time(GameTime(game.game_id, time_played, time_stamp))
                        self.push_cache()
                        logger.debug(f'Updated galaxy stats with {time_played} minutes of play time')
                    self._cached_game_statuses_no_launcher[game.game_id] = main_process_state

                game.local_game_state = await self._is_running()
                if game.local_game_state == self._cached_game_statuses.get(game.game_id):
                    continue

                #logger.debug(f'Game or launcher status changed to {game.local_game_state}')
                self.update_local_game_status(LocalGame(game.game_id, game.local_game_state))
                self._cached_game_statuses[game.game_id] = game.local_game_state
                self.push_cache()

        else:
            self.update_local_game_status(LocalGame("final_fantasy_xiv_shadowbringers", LocalGameState.None_))
            self._cached_game_statuses["final_fantasy_xiv_shadowbringers"] = LocalGameState.None_

        await asyncio.sleep(self.SLEEP_CHECK_STATUS)

    async def authenticate(self, stored_credentials=None):
        if not stored_credentials:
            logger.info("No stored credentials")

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
                logger.warning("plugin/authenticate: stored credentials are invalid")

                raise InvalidCredentials()
            
            return Authentication(self._ffxiv_api.get_character_id(), self._ffxiv_api.get_character_name())

    async def pass_login_credentials(self, step, credentials, cookies):
        self._ffxiv_api.auth_server_stop()

        character_id = self._ffxiv_api.get_character_id()

        if not character_id:
            logger.error("plugin/pass_login_credentials: character_id is None!")

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
        dlclist = [ item for item in os.listdir(dlc_folder) if os.path.isdir(os.path.join(dlc_folder, item)) ] if os.path.exists(dlc_folder) else []

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

            if dlc == "ex4":
                dlc_id = "Endwalker"
                dlc_name = "Final Fantasy XIV: Endwalker"

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

    async def get_game_time(self, game_id: str, context: None) -> GameTime:
        time_played = int(self._get_time_played(game_id) / timedelta(minutes=1))
        time_stamp = self._get_last_played_time(game_id)
        #logger.debug(f'Got game time: {time_played} minutes')
        return GameTime(
            game_id=game_id,
            time_played=time_played,
            last_played_time=time_stamp,
        )

    def _get_time_played(self, game_id: str) -> timedelta:
        key = self._time_played_key(game_id)
        days_key = f'{key}_d'
        if not days_key in self.persistent_cache:
            #logger.debug(f'Got no play time in persistent cache, returning default value')
            return timedelta()

        days = int(self.persistent_cache[days_key])
        seconds = int(self.persistent_cache[f'{key}_s'])
        microseconds = int(self.persistent_cache[f'{key}_t'])
        result = timedelta(days=days, seconds=seconds, microseconds=microseconds)
        #logger.debug(f'Got play time {str(result)} from persistent cache (d={days}, s={seconds}, t={microseconds})')
        return result

    def _set_time_played(self, game_id: str, delta: timedelta):
        key = self._time_played_key(game_id)
        days = int(delta / timedelta(days=1))
        seconds = int((delta - timedelta(days=days)) / timedelta(seconds=1))
        microseconds = int((delta - timedelta(days=days, seconds=seconds)) / timedelta(microseconds=1))
        self.persistent_cache[f'{key}_d'] = str(days)
        self.persistent_cache[f'{key}_s'] = str(seconds)
        self.persistent_cache[f'{key}_t'] = str(microseconds)
        #logger.debug(f'Set play time {str(delta)} to persistent cache (d={days}, s={seconds}, t={microseconds})')

    def _get_last_played_time(self, game_id: str) -> Optional[timedelta]:
        key = self._last_played_time_key(game_id)
        return int(self.persistent_cache[key]) if key in self.persistent_cache else None
    
    def _add_time_played(self, game_id: str, delta: timedelta):
        tracked_time = self._get_time_played(game_id)
        #logger.debug(f'Tracked time before: {str(tracked_time)} (+{str(delta)})')
        tracked_time += delta
        #logger.debug(f'Tracked time after: {str(tracked_time)}')
        self._set_time_played(game_id, tracked_time)
        self.persistent_cache[self._last_played_time_key(game_id)] = str(int(time.time()))

    async def _is_running_internal(self, target_exes):
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

    async def _is_running(self):
        target_exes = [
            "ffxiv_dx11.exe",
            "ffxivlauncher.exe",
            "ffxiv.exe",
            "ffxivupdater.exe",
            "ffxivlauncher64.exe",
            "ffxivupdater64.exe",
            "ffxivboot.exe",
            "ffxivboot64.exe"
        ]
        return await self._is_running_internal(target_exes)

    async def _is_running_no_launcher(self):
        target_exes = [
            "ffxiv_dx11.exe",
            "ffxiv.exe"
        ]
        return await self._is_running_internal(target_exes)

    @staticmethod
    def _time_played_key(game_id: str) -> str:
        return f'time{game_id}'

    @staticmethod
    def _last_played_time_key(game_id: str) -> str:
        return f'last{game_id}'

def main():
    create_and_run_plugin(FinalFantasyXIVPlugin, sys.argv)

if __name__ == "__main__":
    main()
