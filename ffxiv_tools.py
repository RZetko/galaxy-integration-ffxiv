import platform
import sys
import os

if sys.platform == 'win32':
    import winreg

def set_arch_keys():        
    if platform.machine().endswith('64'):
        arch_keys = {winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY}
    else:
        arch_keys = {0}

    return arch_keys

def get_installation_folder():
    arch_keys = set_arch_keys()

    for arch_key in arch_keys:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0, winreg.KEY_READ | arch_key)
        
        for i in range(0, winreg.QueryInfoKey(key)[0]):
            skey_name = winreg.EnumKey(key, i)
            skey = winreg.OpenKey(key, skey_name)

            try:
                display_name = winreg.QueryValueEx(skey, 'DisplayName')[0].lower()

                if (
                        (display_name == "FINAL FANTASY XIV - A Realm Reborn".lower()) or
                        (display_name == "FINAL FANTASY XIV ONLINE".lower()) or
                        (display_name == "FINAL FANTASY XIV".lower())
                    ):
                    install_location = winreg.QueryValueEx(skey, 'InstallLocation')[0] + "\\FINAL FANTASY XIV - A Realm Reborn"
                    skey.Close()
                    
                    return install_location
            except OSError:
                pass
            finally:
                skey.Close()

def get_uninstall_exe():
    arch_keys = set_arch_keys()

    for arch_key in arch_keys:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0, winreg.KEY_READ | arch_key)
        
        for i in range(0, winreg.QueryInfoKey(key)[0]):
            skey_name = winreg.EnumKey(key, i)
            skey = winreg.OpenKey(key, skey_name)

            try:
                if (winreg.QueryValueEx(skey, 'DisplayName')[0] == "FINAL FANTASY XIV - A Realm Reborn"):
                    uninstall_exe = winreg.QueryValueEx(skey, 'UninstallString')[0]
                    skey.Close()
                    
                    return uninstall_exe
            except OSError:
                pass
            finally:
                skey.Close()
