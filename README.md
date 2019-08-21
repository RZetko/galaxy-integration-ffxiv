GOG Galaxy 2.0 Final Fantasy XIV integration

# Installation

1. Download latest release from https://github.com/RZetko/galaxy-integration-ffxiv/releases/latest
2. Extract it to `%localappdata%\GOG.com\Galaxy\plugins\installed\`
3. Restart your GOG Galaxy 2.0 client 
4. Set your character achievements and friends to public on Lodestone: https://eu.finalfantasyxiv.com/lodestone/my/setting/account/
5. Retrieve your FF XIV character ID from https://eu.finalfantasyxiv.com/lodestone/ (or https://na.finalfantasyxiv.com/lodestone/) and go to character profile. You'll find character ID in address bar.
6. Setup Final Fantasy XIV integration by clicking on gear in top left corner of GOG Galaxy client, select settings->integrations, scroll 
down to community integrations and click connect on Final Fantasy XIV integration

# Features

## Supported

* Launching and uninstalling game

* Detecting if game is running

* Syncing friends

## Unsupported

* Achievements syncing - unsupported by platform (already implemented in code, if platform receives support for it, it should automatically work)

* Installing game - unsupported by platform (already implemented in code, if platform receives support for it, it should automatically work)

* Playtime tracking - unsupported by XIVAPI

# Working with code

## Before starting
Install Python extensions (shuold not be needed) `pip install -r requirements.txt -t ./modules --implementation cp --python-version 37 --only-binary=:all:`

## Files and folders
* ./html/ - folder with html files that will popup when first connecting integration
* ./modules/ - folder with installed python modules required for proper functionality of integration
* ./ffxiv_api.py - handles logging in and retrieving character details
* ./ffxiv_localgame.py - handles tasks with local game - starting, deleting
* ./ffxiv_tools.py - helper functions
* ./plugin.py - main script responsible for launching integration
* ./version.py - contains current version of integration
* ./manifest.json - contains identification info about integration
* ./requirements.txt - contains python modules required for proper functionality of integration
    
# Changelog
* v. 1.1.0
   * Added implementation for downloading and installing game (currently unsupported by platform)
   * Fixed crashes when detecting installation folder
   * Fixed missing game in games library when it's not installed
   * Updated readme
* v. 1.0.2
   * Added more paths for FF XIV installation folder + better detection of it 
* v. 1.0.1
   * Fixed issues with detecting FF XIV installation folder for some users
* v. 1.0.0
   * First working release 
   * Supports launching game, uninstalling game, detecting game launch and if it's running, synchronizing friends
   * Installing game currently not supported - WIP
   * Achievements syncing currently not supported - needs more research, may be unable to support because of platform limitations

# Thanks

[@gogcom](https://github.com/gogcom) for making GOG Galaxy 2 and giving me access to beta 
https://github.com/gogcom/galaxy-integrations-python-api

[@Mixaill](https://github.com/Mixaill) for his GOG Galaxy Guild Wars 2 integration which I used as base for this integration. https://github.com/Mixaill/galaxy-integration-gw2

[@viion](https://twitter.com/viion) for A FINAL FANTASY XIV: Online REST API https://xivapi.com/
