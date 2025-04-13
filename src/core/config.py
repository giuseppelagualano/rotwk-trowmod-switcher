# config.py
import os

__APP_NAME__ = "rotwk-trowmod-switcher"
__APP_VERSION__ = "2.2.0"
UPDATER_GITHUB_REPO = "giuseppelagualano/rotwk-mod-switcher"

# --- Archive Settings ---
REPO_OWNER = "SymoniusGit"
REPO_NAME = "TROWMod"

# --- Registry Settings ---
REGISTRY_PATHS_ROTWK = [
    r"SOFTWARE\Wow6432Node\Electronic Arts\Electronic Arts\The Lord of the Rings, The Rise of the Witch-king",
    # Add others if needed
]

# LOCAL SAVINGS
APPDATA_FOLDER = os.getenv('LOCALAPPDATA') + "/RotWKModSwitcher/"
CONFIG_FILE_NAME = "config.ini"
CONFIG_PATH_SECTION = "paths"
LOCAL_CONTENT_KEY = "local_mod_path"
ROTWK_CONTENT_KEY = "rotwk_game_path"
