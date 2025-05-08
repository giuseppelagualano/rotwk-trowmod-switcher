# config.py
import os

import pkg_resources

__APP_NAME__ = "rotwk-trowmod-switcher"
__APP_VERSION__ = pkg_resources.require("rotwk_trowmod_switcher")[0].version
UPDATER_GITHUB_REPO = "giuseppelagualano/rotwk-trowmod-switcher"
GAME_EXE_NAME = "lotrbfme2ep1.exe"
GAME_PROCESS_NAMES = ["lotrbfme2ep1.exe", "game.dat"]

# --- Archive Settings ---
REPO_OWNER = "SymoniusGit"
REPO_NAME = "TROWMod"

# --- Registry Settings ---
REGISTRY_PATHS_ROTWK = [
    r"SOFTWARE\Wow6432Node\Electronic Arts\Electronic Arts\The Lord of the Rings, The Rise of the Witch-king",
    # Add others if needed
]

# LOCAL SAVINGS
APPDATA_FOLDER = os.getenv("LOCALAPPDATA") + "/RotWKTROWModSwitcher/"
UPDATE_INFO_FILE_NAME = "update_info.json"
CONFIG_FILE_NAME = "config.ini"
CONFIG_PATH_SECTION = "paths"
LOCAL_CONTENT_KEY = "local_mod_path"
ROTWK_CONTENT_KEY = "rotwk_game_path"
VERSION_MARKER_FILENAME = "trowmod_version.json"
