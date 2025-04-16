# src/core/updater.py

import json
import logging
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

import certifi
from packaging import version  # For robust version comparison

# Import necessary config values
from rotwk_trowmod_switcher.config import (
    __APP_NAME__,
    __APP_VERSION__,
    UPDATER_GITHUB_REPO,
)

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
        ssl_context = ssl.create_default_context(cafile=certifi.where())

        request = urllib.request.Request(api_url, headers={"User-Agent": f"{__APP_NAME__}-Updater-Client"})
        with urllib.request.urlopen(request, context=ssl_context) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                latest_tag = data.get("tag_name", "").lstrip("v")  # Remove leading 'v' if present (e.g., v1.0.1 -> 1.0.1)
                release_notes = data.get("body", "")  # <-- Extract the release notes body

                if not latest_tag:
                    logger.warning("Could not find 'tag_name' in the latest release API response.")
                    return False, None, None, None

                try:
                    current_v = version.parse(__APP_VERSION__)
                    latest_v = version.parse(latest_tag)
                except version.InvalidVersion:
                    logger.error(f"Invalid version format in config ({__APP_VERSION__}) or tag ({latest_tag}). Cannot compare.")
                    return False, None, None, None

                logger.info(f"Current app version: {current_v}, Latest GitHub release tag: {latest_tag}")

                if latest_v > current_v:
                    logger.info(f"Newer version found: {latest_v}")
                    assets = data.get("assets", [])
                    download_url = None
                    expected_asset_name = f"{__APP_NAME__}.exe"  # e.g., TROWModUpdater.exe

                    for asset in assets:
                        if asset.get("name") == expected_asset_name:
                            download_url = asset.get("browser_download_url")
                            logger.info(f"Found download asset: {download_url}")
                            break

                    if download_url:
                        return True, latest_tag, download_url, release_notes
                    else:
                        logger.error(f"Update found ({latest_tag}), but the required asset '{expected_asset_name}' was not found in the release assets.")
                        return False, latest_tag, None, None
                else:
                    logger.info("Application is up-to-date.")
                    return False, latest_tag, None, None
            else:
                logger.error(f"Failed to fetch release info. Status code: {response.status} {response.reason}")
                return False, None, None, None
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP Error checking for updates: {e.code} {e.reason}")
        # Read the response body even for errors, it might contain useful info
        try:
            error_details = e.read().decode("utf-8")
            logger.error(f"GitHub API response body: {error_details}")
        except Exception:
            pass  # Ignore if reading error body fails
        return False, None, None, None
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON response from GitHub API.")
        return False, None, None, None
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while checking for updates: {e}",
            exc_info=True,
        )
        return False, None, None, None


def download_update(url):
    """
    Downloads the update file to a temporary location with enhanced logging.

    Args:
        url (str): The download URL for the new executable.

    Returns:
        str | None: Path to the downloaded file, or None on failure.
    """
    temp_dir = tempfile.gettempdir()
    temp_filename = os.path.join(temp_dir, f"{__APP_NAME__}_update_{os.getpid()}.exe")

    # Log the exact URL being passed
    logger.info(f"Attempting to download update from URL: {url}")
    logger.info(f"Target temporary file: {temp_filename}")

    try:
        # Clean up potential leftovers from previous failed attempts
        if os.path.exists(temp_filename):
            logger.debug(f"Removing existing temp file: {temp_filename}")
            os.remove(temp_filename)

        logger.debug("Creating SSL context using certifi...")
        ssl_context = ssl.create_default_context(cafile=certifi.where())

        logger.debug(f"Creating request object for URL: {url}")
        # Use the correct App Name in User-Agent
        request = urllib.request.Request(url, headers={"User-Agent": f"{__APP_NAME__}-Updater-Client"})

        logger.debug("Attempting to open URL with urlopen...")
        with urllib.request.urlopen(request, context=ssl_context) as response:
            # Log the response status code and headers
            status_code = response.getcode()
            headers = response.info()  # or response.getheaders() for list of tuples
            logger.info(f"Received response status: {status_code}")
            logger.debug(f"Response headers: \n{headers}")

            # Check if the status code indicates success (e.g., 200 OK)
            if not (200 <= status_code < 300):
                logger.error(f"Download failed: Server returned status code {status_code}")
                # You might want to read the response body here for error details from server
                # try:
                #     error_body = response.read().decode(errors='ignore')
                #     logger.error(f"Server response body: {error_body[:500]}...") # Log first 500 chars
                # except Exception:
                #     pass
                return None  # Exit if status is not OK

            logger.debug(f"Attempting to open temporary file for writing: {temp_filename}")
            with open(temp_filename, "wb") as out_file:
                logger.debug("Starting download copy using shutil.copyfileobj...")
                # Copy the content from the response to the local file
                # shutil.copyfileobj reads in chunks, efficient for large files
                shutil.copyfileobj(response, out_file)
                logger.debug("Finished shutil.copyfileobj.")

        # Log the size of the downloaded file
        if os.path.exists(temp_filename):
            try:
                file_size = os.path.getsize(temp_filename)
                logger.info(f"Update downloaded successfully to: {temp_filename} (Size: {file_size} bytes)")
                if file_size == 0:
                    logger.warning("Downloaded file is empty!")
                # Only return filename if download was successful and file exists
                return temp_filename
            except OSError as e:
                logger.error(f"Error getting size or accessing downloaded file '{temp_filename}': {e}")
                return None  # Treat as failure if we can't access the file post-download
        else:
            # This case should ideally not happen if copyfileobj finished without error,
            # but good to log defensively.
            logger.error("Download seemed complete according to copyfileobj, but the temporary file does not exist!")
            return None

    except urllib.error.URLError as e:
        logger.error(f"URL Error downloading update: {e.reason}", exc_info=True)
        if isinstance(e.reason, ssl.SSLError):
            logger.error("SSL Error detail: Failed to verify certificate.")
    except OSError as e:
        # This catches errors during os.remove, open(temp_filename...), os.path.getsize etc.
        logger.error(
            f"OS Error (e.g., disk full, permissions, file access) during download/file handling: {e}",
            exc_info=True,
        )
    except Exception as e:
        # Catch any other unexpected errors during the process
        logger.error(f"An unexpected error occurred during download: {e}", exc_info=True)

    # Cleanup in case of failure (code before return None in except blocks or if checks fail)
    logger.debug("Download function reached cleanup section (download failed or post-download check failed).")
    if os.path.exists(temp_filename):
        try:
            os.remove(temp_filename)
            logger.debug(f"Cleaned up potentially incomplete file: {temp_filename}")
        except OSError as e:
            # Log warning if cleanup fails, but proceed to return None
            logger.warning(f"Could not remove potentially incomplete file '{temp_filename}': {e}")

    # Return None to indicate failure
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
    if sys.platform != "win32":
        logger.error("Auto-update process is currently only supported on Windows.")
        return False

    current_exe_path = sys.executable  # Path to the currently running .exe
    logger.info(f"Current exe path: {current_exe_path}")

    # script_dir = os.path.dirname(current_exe_path)
    batch_filename = os.path.join(tempfile.gettempdir(), f"updater_{__APP_NAME__}_{os.getpid()}.bat")

    batch_script_content = f"""@echo off
        title {__APP_NAME__} Updater - Do Not Close This Window
        echo.
        echo Applying update for {__APP_NAME__}... Please wait.
        echo Closing application and waiting for file release...
        timeout /t 3 /nobreak > nul
        echo.
        echo Replacing files...
        echo Replaced "{current_exe_path}" with "{downloaded_exe_path}"
        del /Q /F "{current_exe_path}"
        move /Y "{downloaded_exe_path}" "{current_exe_path}"
        echo.
        echo Update applied. Starting the new version...
        echo.
        echo Cleaning up updater script...
        del "%~f0"
    """
    try:
        logger.info(f"Creating update batch script at: {batch_filename}")
        with open(batch_filename, "w", encoding="utf-8") as f:
            f.write(batch_script_content)

        logger.info("Executing update batch script...")
        # Use subprocess.Popen to launch the batch script detached from the current process.
        # DETACHED_PROCESS allows the script to continue running after this Python app exits.
        # CREATE_NEW_CONSOLE shows the batch script window (useful for debugging).
        # Use 0 (or CREATE_NO_WINDOW) instead of CREATE_NEW_CONSOLE if you want it hidden.
        # creation_flags = subprocess.DETACHED_PROCESS
        subprocess.Popen(
            [batch_filename],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            close_fds=True,
        )

        logger.info("Update script launched. Exiting application to allow update.")
        # Exit the current Python application immediately
        sys.exit(0)

    except OSError as e:
        logger.error(f"OS Error creating/executing update script: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Failed to create or execute update script: {e}", exc_info=True)

    # Clean up if script execution failed before exiting
    if os.path.exists(batch_filename):
        try:
            os.remove(batch_filename)
        except OSError:
            pass
    # Also clean up the downloaded file if we failed to launch the updater
    if os.path.exists(downloaded_exe_path):
        try:
            os.remove(downloaded_exe_path)
        except OSError:
            pass

    return False  # Indicate failure to launch the script
