# core/registry.py
import logging
import winreg
from pathlib import Path
from typing import List, Optional

# Make sure to import REGISTRY_PATHS_ROTWK from config if needed directly,
# or pass it as an argument from the GUI layer. Passing as argument is cleaner.

logger = logging.getLogger(__name__)


def find_rotwk_install_path(registry_paths: List[str]) -> Optional[Path]:
    """
    Attempts to find the RoTWK installation path in the Windows Registry.

    Args:
        registry_paths: A list of registry path strings to check.

    Returns:
        A Path object to the installation directory if found, otherwise None.
    """
    logger.info("Attempting to find RoTWK installation path in registry...")
    for path_str in registry_paths:
        logger.debug(f"Checking registry path: HKEY_LOCAL_MACHINE\\{path_str}")
        try:
            hklm = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
            try:
                key = winreg.OpenKey(hklm, path_str, 0, winreg.KEY_READ)
                try:
                    install_location_str, _ = winreg.QueryValueEx(key, "InstallPath")
                    install_path = Path(install_location_str)
                    if install_path.is_dir():
                        logger.info(f"Found RoTWK installation path: {install_path}")
                        return install_location_str
                    else:
                        logger.warning(
                            f"Registry path found ('{install_location_str}'), but it's not a valid directory."
                        )
                except FileNotFoundError:
                    logger.warning(f"'InstallPath' value not found in key: {path_str}")
                except Exception as e:
                    logger.error(
                        f"Error reading value from key {path_str}: {e}", exc_info=True
                    )
                finally:
                    if (
                        "key" in locals()
                    ):  # Ensure key was successfully opened before trying to close
                        winreg.CloseKey(key)
            except FileNotFoundError:
                logger.debug(f"Registry key not found: HKEY_LOCAL_MACHINE\\{path_str}")
                continue
            except Exception as e:
                logger.error(
                    f"Error opening registry key {path_str}: {e}", exc_info=True
                )
            finally:
                if (
                    "hklm" in locals()
                ):  # Ensure connection was successful before trying to close
                    winreg.CloseKey(hklm)
        except Exception as e:
            logger.error(f"Failed to connect to HKEY_LOCAL_MACHINE: {e}", exc_info=True)
            break

    logger.warning(
        "RoTWK installation path not found in any specified registry locations."
    )
    return None
