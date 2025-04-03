import sys
import os
import ctypes
import logging


# Set up logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logger = logging.getLogger(__name__)


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
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
    if os.name == 'nt':  # Check if the OS is Windows ('nt' stands for New Technology)
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
        return False # For this context, return False if not Windows
