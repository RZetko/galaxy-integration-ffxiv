import os
import sys
import logging
import subprocess
import xml.etree.ElementTree as ElementTree

from consts import WINDOWS_UNINSTALL_LOCATION
from typing import List

if sys.platform == 'win32':
    import winreg

class FFXIVLocalGame(object):
    def __init__(self, game_dir, game_executable):
        self._dir = game_dir.lower()
        self._executable = game_executable.lower()

    def exe_name(self) -> str:
        return self._executable

    def run_game(self) -> None:
        subprocess.Popen([os.path.join(self._dir,self._executable)], creationflags=0x00000008, cwd = self._dir)

    def is_local_game_installed(self, local_game):
        try:
            reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)

            with winreg.OpenKey(reg, WINDOWS_UNINSTALL_LOCATION) as key:
                winreg.OpenKey(key, local_game['registry_path'])
                
                if os.path.exists(local_game['path']):
                    return True
        except OSError:
            return False

def get_game_instances() -> List[FFXIVLocalGame]:
    result = list()
    config_dir = os.path.expandvars('%APPDATA%\\Guild Wars 2\\')

    if not os.path.exists(config_dir):
        return result

    for _, _, files in os.walk(config_dir):
        for file_n in files:
            file_name = file_n.lower()

            if file_name.startswith('gfxsettings') and file_name.endswith('.exe.xml'):
                config = ElementTree.parse(os.path.join(config_dir, file_name)).getroot()
                game_dir = config.find('APPLICATION/INSTALLPATH').attrib['Value']
                game_executable = config.find('APPLICATION/EXECUTABLE').attrib['Value']

                if os.path.exists(os.path.join(game_dir, game_executable)):
                    result.append(FFXIVLocalGame(game_dir, game_executable))

    return result
