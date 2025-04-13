import configparser
import ctypes
import logging
import os
import sys

from win11toast import toast

# Set up logging
log_format = "%(asctime)s - %(levelname)s - %(message)s"
logger = logging.getLogger(__name__)


def windows_notify(message: str):
    toast(message, icon=resource_path("src/assets/bg_ai_gen.ico"))


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def is_admin():
    """
    Checks for admin privileges using ctypes.windll.shell32.IsUserAnAdmin().
    Note: This checks if the user *is* an admin, but with UAC enabled,
    the process might not be elevated unless explicitly run "as Administrator".
    However, it's often sufficient for many checks.

    Returns:
        bool: True if the user is part of the Administrators group, False otherwise.
              Returns False on non-Windows OS.
    """
    if os.name == "nt":  # Check if the OS is Windows ('nt' stands for New Technology)
        try:
            # Call the Windows API function IsUserAnAdmin
            # Returns non-zero (True) if the user is an admin, 0 (False) otherwise.
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except AttributeError:
            # Handle cases where the function might not be available (very unlikely on modern Windows)
            logger.warning("Warning: Could not call IsUserAnAdmin. Assuming not admin.")
            return False
        except Exception as e:
            logger.error(f"An error occurred checking admin status (simple): {e}")
            return False
    else:
        # Not Windows, so the concept of "running as admin" doesn't apply directly
        # On Unix-like systems (Linux, macOS), you'd check for root (UID 0)
        # return os.geteuid() == 0 # Uncomment if you need root check on Unix
        return False  # For this context, return False if not Windows


def remove_trailing_slashes(path):
    """
    Removes all trailing slashes from a path.

    Args:
      path: The path string.

    Returns:
      The path string with all trailing slashes removed.
    """
    return path.rstrip(os.sep)


def save_config(config_file_path, section, key, value):
    """
    Saves a configuration value to an INI file, creating parent directories if necessary.

    Args:
        config_file_path (str): The path to the configuration file.
        section (str): The section within the configuration file.
        key (str): The key of the parameter to save.
        value (str): The value of the parameter to save.
    """
    config = configparser.ConfigParser()
    if os.path.exists(config_file_path):
        config.read(config_file_path)

    if not config.has_section(section):
        config.add_section(section)

    config.set(section, key, value)

    # Ensure the directory exists
    os.makedirs(os.path.dirname(config_file_path), exist_ok=True)

    with open(config_file_path, "w") as configfile:
        config.write(configfile)
    print(
        f"Parameter '{key}' saved with value '{value}' in section '{section}' of '{config_file_path}'"
    )


def load_config(config_file_path, section, key, default=None):
    """
    Loads a configuration value from an INI file.

    Args:
        config_file_path (str): The path to the configuration file.
        section (str): The section within the configuration file.
        key (str): The key of the parameter to load.
        default (str, optional): The default value to return if the key does not exist. Defaults to None.

    Returns:
        str or None: The value of the parameter or the default value if not found.
    """
    config = configparser.ConfigParser()
    if os.path.exists(config_file_path):
        config.read(config_file_path)
        if config.has_section(section) and config.has_option(section, key):
            return config.get(section, key)
    return default
