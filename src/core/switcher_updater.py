# src/core/updater.py

import urllib.request
import urllib.error
import json
import logging
import tempfile
import os
import sys
import subprocess
from packaging import version  # For robust version comparison

# Import necessary config values
from core.config import __APP_VERSION__, UPDATER_GITHUB_REPO, __APP_NAME__

logger = logging.getLogger(__name__)

def check_for_updates():
    """
    Checks GitHub for the latest release of this application.

    Returns:
        tuple: (is_update_available: bool, latest_version: str | None, download_url: str | None)
               Returns (False, None, None) on errors or if up-to-date.
    """
    if not UPDATER_GITHUB_REPO or "/" not in UPDATER_GITHUB_REPO:
        logger.error("UPDATER_GITHUB_REPO is not configured correctly in config.py.")
        return False, None, None

    api_url = f"https://api.github.com/repos/{UPDATER_GITHUB_REPO}/releases/latest"
    logger.info(f"Checking for application updates at: {api_url}")
    try:
        # Set a User-Agent header, as GitHub API requires it
        request = urllib.request.Request(api_url, headers={'User-Agent': f'{__APP_NAME__}-Updater-Client'})
        with urllib.request.urlopen(request) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                latest_tag = data.get('tag_name', '').lstrip('v') # Remove leading 'v' if present (e.g., v1.0.1 -> 1.0.1)

                if not latest_tag:
                    logger.warning("Could not find 'tag_name' in the latest release API response.")
                    return False, None, None

                try:
                    current_v = version.parse(__APP_VERSION__)
                    latest_v = version.parse(latest_tag)
                except version.InvalidVersion:
                    logger.error(f"Invalid version format in config ({__APP_VERSION__}) or tag ({latest_tag}). Cannot compare.")
                    return False, None, None

                logger.info(f"Current app version: {current_v}, Latest GitHub release tag: {latest_tag}")

                if latest_v > current_v:
                    logger.info(f"Newer version found: {latest_v}")
                    assets = data.get('assets', [])
                    download_url = None
                    expected_asset_name = f"{__APP_NAME__}.exe" # e.g., TROWModUpdater.exe

                    for asset in assets:
                        if asset.get('name') == expected_asset_name:
                            download_url = asset.get('browser_download_url')
                            logger.info(f"Found download asset: {download_url}")
                            break

                    if download_url:
                        return True, latest_tag, download_url
                    else:
                        logger.error(f"Update found ({latest_tag}), but the required asset '{expected_asset_name}' was not found in the release assets.")
                        return False, latest_tag, None
                else:
                    logger.info("Application is up-to-date.")
                    return False, latest_tag, None
            else:
                logger.error(f"Failed to fetch release info. Status code: {response.status} {response.reason}")
                return False, None, None
    except urllib.error.HTTPError as e:
         logger.error(f"HTTP Error checking for updates: {e.code} {e.reason}")
         # Read the response body even for errors, it might contain useful info
         try:
             error_details = e.read().decode('utf-8')
             logger.error(f"GitHub API response body: {error_details}")
         except Exception:
             pass # Ignore if reading error body fails
         return False, None, None
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON response from GitHub API.")
        return False, None, None
    except Exception as e:
        logger.error(f"An unexpected error occurred while checking for updates: {e}", exc_info=True)
        return False, None, None


def download_update(url, progress_callback=None):
    """
    Downloads the update file to a temporary location.

    Args:
        url (str): The download URL for the new executable.
        progress_callback (callable, optional): A function to call with download progress
                                                 (current_bytes, total_bytes).

    Returns:
        str | None: Path to the downloaded file, or None on failure.
    """
    temp_dir = tempfile.gettempdir()
    # Use a predictable but unique-ish temporary filename
    temp_filename = os.path.join(temp_dir, f"{__APP_NAME__}_update_{os.getpid()}.exe")

    logger.info(f"Attempting to download update from {url} to {temp_filename}")

    try:
        # Clean up potential leftovers from previous failed attempts
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

        # Define reporthook for progress
        def report_hook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if progress_callback:
                if total_size > 0:
                    # Calculate percentage, handle potential division by zero
                     percent = min(100, 100 * downloaded / total_size)
                     progress_callback(downloaded, total_size, percent)
                else:
                    # If total size is unknown, just report bytes downloaded
                    progress_callback(downloaded, -1, -1) # Indicate unknown total size/percent

        # Add User-Agent header
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent', f'{__APP_NAME__}-Updater-Client')]
        urllib.request.install_opener(opener)

        # Perform download
        urllib.request.urlretrieve(url, temp_filename, reporthook=report_hook if progress_callback else None)

        logger.info(f"Update downloaded successfully to: {temp_filename}")
        return temp_filename

    except urllib.error.URLError as e:
        logger.error(f"URL Error downloading update: {e.reason}", exc_info=True)
    except OSError as e:
        logger.error(f"OS Error (e.g., disk full, permissions) downloading update: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Failed to download update: {e}", exc_info=True)

    # Clean up the temporary file if the download failed
    if os.path.exists(temp_filename):
        try:
            os.remove(temp_filename)
            logger.debug(f"Cleaned up partially downloaded file: {temp_filename}")
        except OSError as e:
            logger.warning(f"Could not remove partially downloaded file '{temp_filename}': {e}")
    return None


def trigger_update_restart(downloaded_exe_path):
    """
    Creates and executes a helper batch script (Windows specific) to:
    1. Wait for the current process to exit.
    2. Replace the current executable with the downloaded one.
    3. Restart the application using the new executable.
    4. Clean up the batch script.

    Args:
        downloaded_exe_path (str): The full path to the downloaded new executable.

    Returns:
        bool: True if the script was launched successfully, False otherwise.
              Note: Returning True means the script was launched; success of the
              replacement operation itself happens after the Python app exits.
    """
    if sys.platform != 'win32':
        logger.error("Auto-update process is currently only supported on Windows.")
        return False

    current_exe_path = sys.executable  # Path to the currently running .exe
    script_dir = os.path.dirname(current_exe_path)
    batch_filename = os.path.join(tempfile.gettempdir(), f"updater_{__APP_NAME__}_{os.getpid()}.bat")

    # Batch script content explanation:
    # @echo off : Hide commands being run
    # title Updater : Set window title (optional cosmetic)
    # echo ... : Display messages to the user in the batch window
    # timeout /t 3 /nobreak > nul : Wait 3 seconds without interruption (gives Python time to exit and release file lock). Output is hidden.
    # del /Q /F "{current_exe_path}" : Delete the old executable quietly (/Q) and forcefully (/F). Might fail if still locked, but move should still work.
    # move /Y "{downloaded_exe_path}" "{current_exe_path}" : Move the downloaded file, overwriting (/Y) the original path. This is the core replacement step.
    # start "" "{current_exe_path}" : Launch the NEW executable now at the original path. The "" handles paths with spaces.
    # del "%~f0" : Delete this batch script itself after execution. %~f0 expands to the full path of the batch script.
    batch_script_content = f"""@echo off
        title {__APP_NAME__} Updater - Do Not Close This Window
        echo.
        echo Applying update for {__APP_NAME__}... Please wait.
        echo Closing application and waiting for file release...
        timeout /t 3 /nobreak > nul
        echo.
        echo Replacing files...
        del /Q /F "{current_exe_path}"
        move /Y "{downloaded_exe_path}" "{current_exe_path}"
        echo.
        echo Update applied. Starting the new version...
        start "" "{current_exe_path}"
        echo.
        echo Cleaning up updater script...
        del "%~f0"
    """
    try:
        logger.info(f"Creating update batch script at: {batch_filename}")
        with open(batch_filename, "w", encoding='utf-8') as f:
            f.write(batch_script_content)

        logger.info("Executing update batch script...")
        # Use subprocess.Popen to launch the batch script detached from the current process.
        # DETACHED_PROCESS allows the script to continue running after this Python app exits.
        # CREATE_NEW_CONSOLE shows the batch script window (useful for debugging).
        # Use 0 (or CREATE_NO_WINDOW) instead of CREATE_NEW_CONSOLE if you want it hidden.
        creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_CONSOLE
        subprocess.Popen(['cmd.exe', '/c', batch_filename], creationflags=creation_flags)

        logger.info("Update script launched. Exiting application to allow update.")
        # Exit the current Python application immediately
        sys.exit(0)

    except OSError as e:
        logger.error(f"OS Error creating/executing update script: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Failed to create or execute update script: {e}", exc_info=True)

    # Clean up if script execution failed before exiting
    if os.path.exists(batch_filename):
        try: os.remove(batch_filename)
        except OSError: pass
    # Also clean up the downloaded file if we failed to launch the updater
    if os.path.exists(downloaded_exe_path):
        try: os.remove(downloaded_exe_path)
        except OSError: pass

    return False # Indicate failure to launch the script