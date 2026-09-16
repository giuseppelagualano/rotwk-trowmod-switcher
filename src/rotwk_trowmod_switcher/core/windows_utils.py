# core/registry.py
import logging
import re
import winreg
from pathlib import Path

import pefile
from windows_toasts import (
    Toast,
    ToastDisplayImage,
    ToastImage,
    ToastImagePosition,
    WindowsToaster,
)

from rotwk_trowmod_switcher.core.utils import resource_path
from rotwk_trowmod_switcher.gui.theme import APP_TITLE, ICON_FILE_PATH

# Make sure to import REGISTRY_PATHS_ROTWK from config if needed directly,
# or pass it as an argument from the GUI layer. Passing as argument is cleaner.

logger = logging.getLogger(__name__)

# Setup toast notifier
toaster = WindowsToaster(APP_TITLE)
toastImage = ToastImage(resource_path(ICON_FILE_PATH))
toastDP_logo = ToastDisplayImage(toastImage, altText="App logo", position=ToastImagePosition.AppLogo, circleCrop=True)
newToast = Toast(images=(toastDP_logo,))


def windows_notify(title: str, message: str):
    newToast.text_fields = [title, message]
    toaster.show_toast(newToast)


def find_rotwk_install_path(registry_paths: list[str]) -> Path | None:
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
                        logger.warning(f"Registry path found ('{install_location_str}'), but it's not a valid directory.")
                except FileNotFoundError:
                    logger.warning(f"'InstallPath' value not found in key: {path_str}")
                except Exception as e:
                    logger.error(f"Error reading value from key {path_str}: {e}", exc_info=True)
                finally:
                    if "key" in locals():  # Ensure key was successfully opened before trying to close
                        winreg.CloseKey(key)
            except FileNotFoundError:
                logger.debug(f"Registry key not found: HKEY_LOCAL_MACHINE\\{path_str}")
                continue
            except Exception as e:
                logger.error(f"Error opening registry key {path_str}: {e}", exc_info=True)
            finally:
                if "hklm" in locals():  # Ensure connection was successful before trying to close
                    winreg.CloseKey(hklm)
        except Exception as e:
            logger.error(f"Failed to connect to HKEY_LOCAL_MACHINE: {e}", exc_info=True)
            break

    logger.warning("RoTWK installation path not found in any specified registry locations.")
    return None


def find_rotwk_patch_version(game_path: str | Path) -> str:
    """Return the 2.02 patch version reported by AllInOneLauncher markers."""
    path = Path(game_path)
    if not path.is_dir():
        return "Path does not exist or is not a directory"

    marker_pattern = re.compile(r"202_v(?P<version>\d+(?:\.\d+){1,2})\.big$", re.IGNORECASE)
    for marker_path in path.glob("*202_v*.big"):
        match = marker_pattern.search(marker_path.name)
        if match:
            return f"2.02 v{match.group('version')}"

    if (path / "__patch202.big").is_file() or (path / "################202.big").is_file():
        return "2.02 (< 9.0.0 - no version marker)"
    return "No marker found"


def check_rotwk_4gb_patch(game_path: str | Path) -> dict[str, bool | str]:
    """Check the Large Address Aware flag on both RotWK executables."""
    path = Path(game_path)
    results: dict[str, bool | str] = {}
    for filename in ("lotrbfme2ep1.exe", "game.dat"):
        file_path = path / filename
        if not file_path.is_file():
            results[filename] = "File not found"
            continue

        try:
            with pefile.PE(str(file_path), fast_load=True) as pe:
                results[filename] = bool(pe.FILE_HEADER.Characteristics & pefile.IMAGE_CHARACTERISTICS["IMAGE_FILE_LARGE_ADDRESS_AWARE"])
        except (OSError, pefile.PEFormatError) as error:
            results[filename] = f"Check failed: {error}"

    results["all_patched"] = all(results.get(filename) is True for filename in ("lotrbfme2ep1.exe", "game.dat"))
    return results
