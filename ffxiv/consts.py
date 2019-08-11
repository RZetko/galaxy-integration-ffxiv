import sys

from tools import FFXIVTools

if (sys.platform == 'win32') and (FFXIVTools.is_os_64bit):
    WINDOWS_UNINSTALL_LOCATION = "SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
else:
    WINDOWS_UNINSTALL_LOCATION = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
