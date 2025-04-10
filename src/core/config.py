# config.py
import os

__APP_NAME__ = "rotwk-trowmod-switcher"
__APP_VERSION__ = "2.1.0"
UPDATER_GITHUB_REPO = "giuseppelagualano/rotwk-mod-switcher"

# --- Archive Settings ---
REPO_OWNER = "SymoniusGit"
REPO_NAME = "TROWMod"
DEFAULT_INI_ARCHIVE_NAME = "!TROWMOD_INI.big"
DEFAULT_ARTS_ARCHIVE_NAME = "!trowmod.big"
DEFAULT_ITLANG_ARCHIVE_NAME = "Italian.big"

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

# --- GUI Settings ---
APP_TITLE = "LOTR: Rise of the Witch-king Archiver"
INITIAL_WINDOW_SIZE = "1200x1200"

# LORD OF THE RINGS THEMED COLORS
TEXT_PRIMARY = "#b99767"
TEXT_SECONDARY = "#D3D3D3"
BUTTON_PRIMARY_BG = "#34474b"
BUTTON_SECONDARY_BG = "#42575a"
BUTTON_PRIMARY_BORDER = "#b99767"
BUTTON_PRIMARY_HOVER = "#5d6f6d"
BUTTON_SECONDARY_HOVER = "#112222"
BUTTON_TEXT_PRIMARY = "#FFD700"
BUTTON_TEXT_SECONDARY = "#112222"
BUTTON_TERTIARY_BG = "#26383c"

PRIMARY_BUTTON_FONT = ("Arial", 20, "bold")
SECONDARY_BUTTON_FONT = ("Arial", 16, "bold")
TERTIARY_BUTTON_FONT = ("Arial", 16)
LABEL_FONT = ("Arial", 14, "bold")
FLAG_FONT = ("Arial", 15, "bold")
TEXT_FONT = ("Arial", 16)