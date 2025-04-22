# src/gui/app.py
import json
import logging
import os
import subprocess
import sys
import threading
import tkinter
from tkinter import filedialog, messagebox, scrolledtext

import customtkinter as ctk
import psutil
from PIL import Image

from rotwk_trowmod_switcher import config
from rotwk_trowmod_switcher.config import (  # Import app name if used in paths/messages
    __APP_NAME__,
    __APP_VERSION__,
    APPDATA_FOLDER,
    CONFIG_FILE_NAME,
    CONFIG_PATH_SECTION,
    GAME_EXE_NAME,
    GAME_PROCESS_NAME,
    LOCAL_CONTENT_KEY,
    REGISTRY_PATHS_ROTWK,
    REPO_NAME,
    REPO_OWNER,
    ROTWK_CONTENT_KEY,
    UPDATE_INFO_FILE_NAME,
)

# --- Core Imports ---
# Note: Assuming 'src' is in PYTHONPATH or handled by the execution context
from rotwk_trowmod_switcher.core.big_archiver.archiver import (
    create_big_archives,
)
from rotwk_trowmod_switcher.core.mod_manager import remove_mod_files
from rotwk_trowmod_switcher.core.mod_retriever import get_latest_release_tag, update_rotwk_with_latest_mod
from rotwk_trowmod_switcher.core.switcher_updater import (
    check_for_updates,
    download_update,
    trigger_update_restart,
)
from rotwk_trowmod_switcher.core.utils import (
    is_admin,
    load_config,
    resource_path,
    save_config,
)
from rotwk_trowmod_switcher.core.windows_utils import (
    find_rotwk_install_path,
    windows_notify,
)

# --- GUI Theme/Constants Import ---
from .theme import (
    APP_TITLE,
    BG_IMG_FILE_PATH,
    BUTTON_PRIMARY_BG,
    BUTTON_PRIMARY_BORDER,
    BUTTON_PRIMARY_HOVER,
    BUTTON_SECONDARY_BG,
    BUTTON_SECONDARY_HOVER,
    BUTTON_TERTIARY_BG,
    BUTTON_TEXT_SECONDARY,
    FLAG_FONT,
    GAME_IMG_FILE_PATH,
    ICON_FILE_PATH,
    INITIAL_WINDOW_SIZE,
    PRIMARY_BUTTON_FONT,
    SECONDARY_BUTTON_FONT,
    TERTIARY_BUTTON_FONT,
    TEXT_FONT,
    TEXT_PRIMARY,
)

# --- Logger Setup ---
# Logger is configured in main.py, get the existing logger instance
logger = logging.getLogger(__name__)
log_format = "%(asctime)s - %(levelname)s - %(message)s"  # Define format needed for handler

# Global variable for the root window - necessary for schedule_gui_update
root = None
# Global vars for widgets that need updating from callbacks/threads
log_console = None
flag_label = None
disable_mod_button = None
remote_update_button = None
local_update_button = None
launch_game_button = None
kill_game_button = None
browse_button_remote = None
browse_button_local = None
rotwk_path_entry = None
local_path_entry = None


def show_changelog_if_exists():
    update_info_path = os.path.join(APPDATA_FOLDER, UPDATE_INFO_FILE_NAME)

    if os.path.exists(update_info_path):  # Check file existence directly
        logger.info(f"Update info file found at '{update_info_path}'. Attempting to display changelog.")
        version = "N/A"
        notes = "Could not read update notes."  # Default message
        try:
            with open(update_info_path, encoding="utf-8") as f:
                update_data = json.load(f)
            version = update_data.get("version", version)
            # Get the raw notes text, strip leading/trailing whitespace
            notes = update_data.get("notes", notes).strip()
            if not notes:  # Handle case where notes might be empty string
                notes = "No specific notes provided for this update."

            # --- Display using messagebox ---
            title = f"Update Successful - What's New in v{version}"
            message = f"Successfully updated to version {version}!\n\n--- Changelog ---\n\n{notes}"

            # Schedule the messagebox call to run after the main window is ready
            # Using schedule_gui_update ensures it runs in the main GUI thread
            schedule_gui_update(messagebox.showinfo, title, message)

        except FileNotFoundError:
            logger.warning("Update info file existed but disappeared before reading.")
        except json.JSONDecodeError:
            logger.error("Update info file was corrupted (not valid JSON).")
            schedule_gui_update(
                messagebox.showerror,
                "Changelog Error",
                f"Could not read update notes for version {version}.\nThe update info file was corrupted.",
            )
        except Exception as e:
            logger.error(f"Failed to read, parse or display update info file: {e}", exc_info=True)
            schedule_gui_update(
                messagebox.showerror,
                "Changelog Error",
                f"Could not display update notes for version {version}.\nError: {e}",
            )
        finally:
            # --- CRITICAL: Clean up the file ---
            if os.path.exists(update_info_path):
                try:
                    os.remove(update_info_path)
                    logger.info(f"Removed update info file: {update_info_path}")
                except OSError as e:
                    logger.error(f"Failed to remove update info file '{update_info_path}': {e}")


# --- Helper Function for GUI Updates from Threads ---
def schedule_gui_update(callback, *args, **kwargs):
    """
    Schedules a function to run safely in the main GUI thread using root.after(),
    passing both positional and keyword arguments. Includes error handling for
    calls made after the main loop has stopped.

    Args:
        callback: The function to call in the main thread.
        *args: Positional arguments for the callback.
        **kwargs: Keyword arguments for the callback.
    """
    if root and root.winfo_exists():
        try:
            # Pass *args and **kwargs to the callback via root.after
            root.after(0, lambda: callback(*args, **kwargs))
        except tkinter.TclError as e:
            # This likely means the main loop is stopping or has stopped.
            # Log to stderr or a file logger instead of the GUI console.
            if "application has been destroyed" in str(e).lower() or "main thread is not in main loop" in str(e).lower():  # Check common TclError messages
                print(f"Debug: Suppressed GUI update after main loop exit for {callback.__name__}", file=sys.stderr)
            else:
                # Log other unexpected TclErrors
                logger.warning(f"TclError scheduling GUI update for {callback.__name__}: {e}", exc_info=False)  # exc_info=False to avoid recursive logging loop
        except Exception as e:
            # Catch any other unexpected errors during scheduling
            logger.error(f"Unexpected error scheduling GUI update for {callback.__name__}: {e}", exc_info=False)
    else:
        # Use f-string for logging
        logger.debug(f"Debug: GUI update ignored as root window no longer exists. Callback: {callback.__name__}")


# --- GUI Update Functions ---
def update_flag(success):
    """Updates the status flag label based on the success of an operation."""
    if not flag_label:
        return  # Guard against missing widget
    if success:
        schedule_gui_update(flag_label.configure, text="Update completed!", text_color="green")
        # Run notification in a separate thread to avoid blocking
        windows_notify("Update completed!", "You can now launch the game")
    else:
        schedule_gui_update(flag_label.configure, text="ERROR!! Please, see the logs below!", text_color="red")


def set_buttons_state(new_state):
    """Enables or disables relevant buttons during update operations."""
    widgets = [
        remote_update_button,
        local_update_button,
        launch_game_button,
        browse_button_remote,
        browse_button_local,
        kill_game_button,
        remove_mod_button,
    ]
    for widget in widgets:
        if widget:  # Check if widget exists
            widget.configure(state=new_state)


def clear_log():
    """Clears the content of the log console."""
    if not log_console:
        return
    log_console.configure(state="normal")
    log_console.delete("1.0", ctk.END)
    log_console.configure(state="disabled")


def _perform_update_download_and_restart(url, latest_v, release_notes):
    """Handles the download and restart process."""
    logger.info("Starting update download...")
    schedule_gui_update(flag_label.configure, text="Downloading update...", text_color="yellow")  # Optional status update

    downloaded_path = download_update(url)

    if downloaded_path:
        logger.info("Download complete. Saving update info...")

        # --- Save update info for the new version ---
        update_info_path = os.path.join(APPDATA_FOLDER, UPDATE_INFO_FILE_NAME)
        update_data = {"version": latest_v, "notes": release_notes}
        try:
            # Ensure the directory exists
            os.makedirs(APPDATA_FOLDER, exist_ok=True)
            with open(update_info_path, "w", encoding="utf-8") as f:
                json.dump(update_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Update info saved to {update_info_path}")
        except Exception as e:
            logger.error(f"Failed to save update info: {e}", exc_info=True)

        if not trigger_update_restart(downloaded_path):
            # If triggering fails, clean up the update info file too
            if os.path.exists(update_info_path):
                try:
                    os.remove(update_info_path)
                except OSError:
                    pass
            schedule_gui_update(set_buttons_state, "normal")
            schedule_gui_update(
                messagebox.showerror,
                "Update Error",
                "Failed to start the update process. The downloaded file might be removed. Please try updating manually or restarting the application.",
            )
    else:
        schedule_gui_update(set_buttons_state, "normal")
        schedule_gui_update(
            messagebox.showerror,
            "Update Error",
            "Failed to download the update file. Please check your internet connection and permissions, then try again.",
        )


def ask_user_to_update(latest_v, url, release_notes):
    """Asks the user (in the main thread) if they want to update."""
    if not root or not root.winfo_exists():
        logger.warning("Update confirmation skipped: Root window closed.")
        return

    confirm = messagebox.askyesno(
        "Update Available",
        f"A new version ({latest_v}) of {__APP_NAME__} is available.\n"
        f"Your current version is {__APP_VERSION__}.\n\n"
        "Do you want to download and install it now?\n"
        "You will have to re-run the application manually.",
    )

    if confirm:
        logger.info("User confirmed update. Preparing download.")
        set_buttons_state("disabled")
        _perform_update_download_and_restart(url, latest_v, release_notes)
    else:
        logger.info("User declined update.")


def perform_update_check(show_no_update_message=False):
    """Checks for updates and prompts the user if one is found."""

    def check_thread_target():
        logger.info("Running update check...")
        try:
            # Pass the correct repo for the *application itself*
            is_update, latest_v, url, release_notes = check_for_updates()  # Uses UPDATER_GITHUB_REPO from config

            if is_update and url:
                logger.info(f"Update available: Version {latest_v}")
                schedule_gui_update(ask_user_to_update, latest_v, url, release_notes)
            elif is_update and not url:
                logger.warning("Update check found a new version, but no download URL for the .exe asset.")
                if show_no_update_message:
                    schedule_gui_update(
                        messagebox.showinfo,
                        "Update Info",
                        f"A new version ({latest_v}) is available, but the download asset could not be found in the release.",
                    )
            elif show_no_update_message:
                logger.info("No update required or check failed.")
                schedule_gui_update(
                    messagebox.showinfo,
                    "Up-to-Date",
                    f"You are running the latest version ({__APP_VERSION__}).",
                )
            else:
                logger.info("No update required or check failed (silent).")

        except Exception as e:
            logger.error(f"Error during update check thread: {e}", exc_info=True)

    check_thread_target()


# --- Worker Thread Target Functions ---
def _run_remote_update_thread(repo_full_name, game_path):
    """Target function for the remote update worker thread."""
    success = False
    try:
        logger.info(f"Starting remote update thread for {repo_full_name}...")
        success = update_rotwk_with_latest_mod(repo_full_name=repo_full_name, game_path=game_path)
        if success:
            logger.info("Remote update thread finished successfully.")
            update_mod_version_display(game_path)
        else:
            logger.error("Remote update thread failed.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in remote update thread: {e}")
        success = False
    finally:
        schedule_gui_update(update_flag, success)
        schedule_gui_update(set_buttons_state, "normal")


def _run_local_update_thread(source_dir_path, output_dir_path):
    """Target function for the local update worker thread."""
    try:
        logger.info(f"Starting local update thread from {source_dir_path}...")
        success = create_big_archives(
            source_content_path=source_dir_path,
            game_path=output_dir_path,
            logger=logger,
            mod_version="LOCAL",
        )

        if success:
            logger.info("Local update thread finished successfully.")
            update_mod_version_display(output_dir_path)
        else:
            logger.error("Local update thread failed.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in local update thread: {e}")
        success = False
    finally:
        schedule_gui_update(update_flag, success)
        schedule_gui_update(set_buttons_state, "normal")


# --- GUI Event Handlers ---
def on_remote_update_click():
    """Handles the click event for the remote update button."""
    if not rotwk_path_entry or not flag_label:
        return
    logger.info("Remote Update started!")

    rotwk_path = rotwk_path_entry.get()
    if not rotwk_path or rotwk_path == "NOT FOUND!":
        logger.critical("Could not find RoTWK installation path. Update cannot continue.")
        schedule_gui_update(flag_label.configure, text="Error: RoTWK Path Invalid", text_color="red")
        return

    # Save the confirmed/entered path
    save_config(
        APPDATA_FOLDER + CONFIG_FILE_NAME,
        CONFIG_PATH_SECTION,
        ROTWK_CONTENT_KEY,
        rotwk_path,
    )

    set_buttons_state("disabled")
    schedule_gui_update(flag_label.configure, text="Update running...", text_color="yellow")  # Indicate running

    repo_full_name = f"{REPO_OWNER}/{REPO_NAME}"  # Mod repo
    thread = threading.Thread(target=_run_remote_update_thread, args=(repo_full_name, rotwk_path), daemon=True)
    thread.start()


def on_local_update_click():
    """Handles the click event for the local update button."""
    if not rotwk_path_entry or not local_path_entry or not flag_label:
        return
    logger.info("Local update started!")

    rotwk_path = rotwk_path_entry.get()
    if not rotwk_path or rotwk_path == "NOT FOUND!":
        logger.critical("Could not find RoTWK installation path. Update cannot continue.")
        schedule_gui_update(flag_label.configure, text="Error: RoTWK installation path cannot be empty!", text_color="red")
        return

    source_content_path = local_path_entry.get()
    if not source_content_path or source_content_path == "Insert DEV Mod folder path here" or not os.path.isdir(source_content_path):
        logger.error("Local content path is empty or invalid. Update cannot proceed.")
        schedule_gui_update(flag_label.configure, text="Error: Local path cannot be empty or is invalid!", text_color="red")
        return

    logger.info(f"Using local content path: {source_content_path}")
    # Save the confirmed/entered path
    save_config(
        APPDATA_FOLDER + CONFIG_FILE_NAME,
        CONFIG_PATH_SECTION,
        LOCAL_CONTENT_KEY,
        source_content_path,
    )

    set_buttons_state("disabled")
    schedule_gui_update(flag_label.configure, text="Update running...", text_color="yellow")  # Indicate running

    thread = threading.Thread(
        target=_run_local_update_thread,
        args=(source_content_path, rotwk_path),
        daemon=True,
    )
    thread.start()


def browse_rotwk_path():
    """Opens a dialog to browse for the RoTWK installation path."""
    if not rotwk_path_entry:
        return
    directory = filedialog.askdirectory(title="Select RoTWK Installation Folder")
    if directory:
        # Use os.path.join for robustness, ensure trailing slash consistency if needed
        # normalized_path = os.path.join(directory, '') # Adds trailing slash if missing
        normalized_path = os.path.normpath(directory)  # More standard way
        rotwk_path_entry.delete(0, ctk.END)
        rotwk_path_entry.insert(0, normalized_path)
        logger.info(f"RoTWK path set to: {normalized_path}")
        save_config(
            APPDATA_FOLDER + CONFIG_FILE_NAME,
            CONFIG_PATH_SECTION,
            ROTWK_CONTENT_KEY,
            normalized_path,
        )
        update_mod_version_display(normalized_path)


def browse_local_dev_path():
    """Opens a dialog to browse for the local DEV mod folder path."""
    if not local_path_entry:
        return
    directory = filedialog.askdirectory(title="Select Local DEV Mod Folder (containing data, arts, lang)")
    if directory:
        normalized_path = os.path.normpath(directory)
        local_path_entry.delete(0, ctk.END)
        local_path_entry.insert(0, normalized_path)
        logger.info(f"Local DEV Mod path set to: {normalized_path}")
        save_config(
            APPDATA_FOLDER + CONFIG_FILE_NAME,
            CONFIG_PATH_SECTION,
            LOCAL_CONTENT_KEY,
            normalized_path,
        )


def on_launch_game_click():
    """Attempts to launch the RotWK game executable."""
    if not rotwk_path_entry:
        return
    logger.info("Attempting to launch game...")
    rotwk_path = rotwk_path_entry.get()

    if not rotwk_path or rotwk_path == "NOT FOUND!" or not os.path.isdir(rotwk_path):
        logger.error("Invalid RotWK path provided for launching.")
        messagebox.showerror(
            "Launch Error",
            "The Rise of the Witch-king installation path is invalid or not set.",
        )
        return

    full_game_exe_path = os.path.join(rotwk_path, GAME_EXE_NAME)

    if not os.path.exists(full_game_exe_path):
        logger.error(f"Game executable not found at: {full_game_exe_path}")
        messagebox.showerror(
            "Launch Error",
            f"Could not find the game executable:\n{GAME_EXE_NAME}\n\nIn the specified path:\n{rotwk_path}",
        )
        return

    try:
        logger.info(f"Launching: {full_game_exe_path} in directory {rotwk_path}")
        subprocess.Popen([full_game_exe_path], cwd=rotwk_path)
        logger.info("Game launch command issued.")
    except OSError as e:
        logger.error(f"OS Error launching game: {e}", exc_info=True)
        messagebox.showerror("Launch Error", f"Operating system error while launching the game:\n{e}")
    except Exception as e:
        logger.error(f"Unexpected error launching game: {e}", exc_info=True)
        messagebox.showerror(
            "Launch Error",
            f"An unexpected error occurred while launching the game:\n{e}",
        )


def on_kill_game_click():
    """
    Attempts to find and forcefully terminate the RotWK game process.
    """
    process_found = False
    logger.info(f"Attempting to kill process: {GAME_PROCESS_NAME}")

    try:
        # Iterate over all running processes
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"].lower() == GAME_PROCESS_NAME.lower():
                process_found = True
                pid = proc.info["pid"]
                logger.info(f"Found process {GAME_PROCESS_NAME} with PID {pid}. Attempting to kill.")
                try:
                    process_to_kill = psutil.Process(pid)
                    process_to_kill.kill()  # Forceful termination (SIGKILL/TerminateProcess)
                    # Check if it actually terminated (kill might take a moment)
                    try:
                        process_to_kill.wait(timeout=0.5)  # Wait briefly
                    except psutil.TimeoutExpired:
                        logger.warning(f"Process {pid} did not terminate instantly after kill signal.")
                        # Could try terminate() first then kill() for more grace, but user asked for kill
                    except psutil.NoSuchProcess:
                        pass  # Process already gone, good.

                    # Re-check if process still exists after attempting kill
                    if not psutil.pid_exists(pid):
                        logger.info(f"Process {pid} successfully terminated.")
                        break  # Exit loop once killed
                    else:
                        logger.error(f"Attempted to kill process {pid}, but it still exists.")
                        break  # Exit loop

                except psutil.NoSuchProcess:
                    logger.warning(f"Process {pid} disappeared before kill could be completed.")
                    break
                except psutil.AccessDenied:
                    logger.error(f"Access denied when trying to kill process {pid}. Try running as administrator.")
                    messagebox.showerror("Error", "Access denied when trying to kill the game process.\nPlease ensure this switcher is running as Administrator.")
                    break
                except Exception as kill_err:
                    logger.error(f"An unexpected error occurred while killing process {pid}: {kill_err}", exc_info=True)
                    break

        if not process_found:
            logger.info(f"Process {GAME_PROCESS_NAME} not found running.")

    except Exception as search_err:
        logger.error(f"An error occurred while searching for processes: {search_err}", exc_info=True)


# --- Define Helper Function ---
def update_mod_version_display(game_dir_path):
    """Reads trowmod_version.json from game_dir_path and updates the GUI label."""
    global mod_version_label
    if not mod_version_label:  # Check if label widget exists
        logger.debug("mod_version_label widget not ready yet.")
        return

    version = "Unknown"
    color = BUTTON_TEXT_SECONDARY  # Default color (e.g., gray)
    version_file_path = ""

    if not game_dir_path or game_dir_path == "NOT FOUND!" or not os.path.isdir(game_dir_path):
        logger.debug(f"Invalid game directory path for version check: {game_dir_path}")
        version = "N/A (Set RoTWK Path)"
        color = "orange"
    else:
        try:
            # Use the constant defined in mod_retriever (or define it here too)
            # from core.mod_retriever import VERSION_MARKER_FILENAME # Option 1: Import
            VERSION_MARKER_FILENAME = "trowmod_version.json"  # Option 2: Redefine

            version_file_path = os.path.join(game_dir_path, VERSION_MARKER_FILENAME)
            logger.debug(f"Checking for mod version file at: {version_file_path}")

            if os.path.exists(version_file_path):
                with open(version_file_path, encoding="utf-8") as f:
                    data = json.load(f)
                version = data.get("version", "Error: Key Missing")
                if version != "Error: Key Missing":
                    color = TEXT_PRIMARY  # Success color (e.g., main text color)
                    logger.info(f"Found installed mod version: {version}")
                else:
                    color = "red"
                    logger.error(f"'version' key missing in {version_file_path}")

            else:
                logger.info(f"Mod version file not found at {version_file_path}.")
                version = "Unknown (Update Mod?)"
                color = "orange"  # Indicate file not found

        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {version_file_path}.", exc_info=True)
            version = "Error: Corrupt File"
            color = "red"
        except OSError as e:
            logger.error(f"Error reading version file {version_file_path}: {e}", exc_info=True)
            version = "Error: Read Failed"
            color = "red"
        except Exception as e:
            logger.error(f"Unexpected error checking mod version: {e}", exc_info=True)
            version = "Error"
            color = "red"

    # Schedule GUI update for the label
    schedule_gui_update(mod_version_label.configure, text=f"Installed Mod Version: {version}", text_color=color)


def fetch_and_display_latest_mod_version():
    """Fetches the latest mod tag from GitHub and updates the GUI label."""
    global latest_mod_available_label
    if not latest_mod_available_label:
        return  # Label not ready

    logger.info("Checking for latest available mod version...")
    schedule_gui_update(latest_mod_available_label.configure, text="Latest Available: Checking...")

    mod_repo_full_name = f"{config.REPO_OWNER}/{config.REPO_NAME}"  # Get mod repo from config
    latest_tag = None
    error_msg = None

    try:
        # This function handles the network request and basic error logging
        latest_tag = get_latest_release_tag(mod_repo_full_name)
    except Exception as e:
        # Catch potential exceptions from the underlying function if needed,
        # though get_latest_release_tag should handle basic network errors.
        logger.error(f"Error calling get_latest_release_tag: {e}", exc_info=True)
        error_msg = "Error checking"

    # Update GUI based on result
    if latest_tag:
        logger.info(f"Latest available mod version found: {latest_tag}")
        schedule_gui_update(latest_mod_available_label.configure, text=f"Latest Available: {latest_tag}", text_color=TEXT_PRIMARY)
    elif error_msg:
        logger.warning("Could not determine latest available mod version due to error.")
        schedule_gui_update(latest_mod_available_label.configure, text=f"Latest Available: {error_msg}", text_color="orange")
    else:
        logger.warning("Could not determine latest available mod version (no tag found?).")
        schedule_gui_update(latest_mod_available_label.configure, text="Latest Available: Not Found", text_color="orange")


def start_fetch_latest_mod_version_thread():
    """Starts the background thread to fetch the latest mod version."""
    fetch_thread = threading.Thread(target=fetch_and_display_latest_mod_version, daemon=True)
    fetch_thread.start()


def _run_remove_mod_thread(rotwk_path):
    """Target function for the remove mod worker thread."""
    success = False
    try:
        success = remove_mod_files(rotwk_path, logger)

        if success:
            logger.info("Mod removal thread finished successfully.")
            # Schedule GUI updates from the thread
            schedule_gui_update(flag_label.configure, text="Mod removed successfully!", text_color="green")
            schedule_gui_update(update_mod_version_display, rotwk_path)
            schedule_gui_update(windows_notify, "Mod Removed", f"The mod has been removed from {os.path.basename(rotwk_path)}.")
        else:
            logger.error("Mod removal thread failed (core function returned False). Check logs.")
            schedule_gui_update(flag_label.configure, text="ERROR removing mod! See logs.", text_color="red")
            schedule_gui_update(messagebox.showerror, "Removal Error", "An error occurred while removing the mod files. Please check the logs.")

    except Exception as e:
        logger.exception(f"An unexpected error occurred in remove mod thread: {e}")
        success = False
        schedule_gui_update(flag_label.configure, text="FATAL ERROR removing mod! See logs.", text_color="red")
        schedule_gui_update(messagebox.showerror, "Removal Error", f"An unexpected error occurred: {e}")
    finally:
        schedule_gui_update(set_buttons_state, "normal")


def on_remove_mod_click():
    """Handles the click event for the Remove Mod button."""
    global rotwk_path_entry, flag_label  # Use the correct global 'remove_mod_button' if needed directly

    if not rotwk_path_entry or not flag_label:
        logger.warning("Remove Mod clicked but required widgets are missing.")
        return

    rotwk_path = rotwk_path_entry.get()

    # 1. Validate Path
    if not rotwk_path or rotwk_path == "NOT FOUND!" or not os.path.isdir(rotwk_path):
        logger.error("Invalid RotWK path provided for removing mod.")
        schedule_gui_update(flag_label.configure, text="Error: RoTWK Path Invalid", text_color="red")
        messagebox.showerror(
            "Removal Error",
            "The Rise of the Witch-king installation path is invalid or not set. Cannot remove mod.",
        )
        return

    # 2. Ask for Confirmation
    confirm = messagebox.askyesno(
        "Confirm Mod Removal",
        f"Are you sure you want to remove the mod files from:\n"
        f"'{rotwk_path}'?\n\n"
        "This action will attempt to revert the game to its state before the mod was applied.\n"
        "Make sure the game is not running.",
        icon="warning",
    )

    # 3. Check Confirmation Result
    if not confirm:
        logger.info("User cancelled mod removal.")
        return

    # 4. Start Background Thread if Confirmed
    logger.info(f"User confirmed. Starting remove mod thread for: {rotwk_path}")
    set_buttons_state("disabled")
    schedule_gui_update(flag_label.configure, text="Removing mod...", text_color="yellow")

    # Create and start the daemon thread
    thread = threading.Thread(target=_run_remove_mod_thread, args=(rotwk_path,), daemon=True)
    thread.start()


# --- Logging Setup for GUI Console ---
class TextHandler(logging.Handler):
    """Custom logging handler to redirect logs to the Tkinter Text widget"""

    def emit(self, record):
        msg = self.format(record)
        if log_console:  # Check if log_console has been initialized
            try:
                # Schedule log update in the main thread
                schedule_gui_update(self._update_log_console, msg)
            except Exception as e:
                print(
                    f"Error updating log console: {e}\nLog message: {msg}",
                    file=sys.stderr,
                )  # Fallback print

    def _update_log_console(self, msg):
        if not log_console or not log_console.winfo_exists():
            return  # Extra safety check
        original_state = log_console.cget("state")
        log_console.configure(state="normal")
        log_console.insert(ctk.END, msg + "\n")
        log_console.configure(state=original_state)
        log_console.see(ctk.END)


def setup_logging_to_text_widget():
    """Sets up the logging handler for the GUI Text widget."""
    # Get the root logger
    root_logger = logging.getLogger()
    # Remove existing handlers if necessary to avoid duplicates (optional)
    # for handler in root_logger.handlers[:]:
    #    root_logger.removeHandler(handler)

    # Add the custom TextHandler
    text_handler = TextHandler()
    text_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(text_handler)
    # Ensure the root logger level is appropriate (e.g., INFO)
    if not root_logger.hasHandlers():  # Set level only if no handlers exist (likely set in main.py now)
        root_logger.setLevel(logging.INFO)


# --- Main GUI Construction Function ---
def run_gui():
    """Creates and runs the main application window."""
    global root, log_console, flag_label, remote_update_button, local_update_button
    global launch_game_button, kill_game_button, browse_button_remote, browse_button_local
    global rotwk_path_entry, local_path_entry
    global latest_mod_available_label, mod_version_label, remove_mod_button

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    root = ctk.CTk()
    root.resizable(False, False)
    root.geometry(INITIAL_WINDOW_SIZE)

    try:
        root.iconbitmap(resource_path(ICON_FILE_PATH))
    except Exception as e:
        logger.error(f"Failed to set window icon: {e}")
    root.title(f"{APP_TITLE} - v.{__APP_VERSION__}")

    # Load background image
    try:
        bg_image = ctk.CTkImage(
            light_image=Image.open(resource_path(BG_IMG_FILE_PATH)),
            dark_image=Image.open(resource_path(BG_IMG_FILE_PATH)),
            size=(1000, 900),
        )
        game_ico = ctk.CTkImage(
            light_image=Image.open(resource_path(GAME_IMG_FILE_PATH)),
            dark_image=Image.open(resource_path(GAME_IMG_FILE_PATH)),
            size=(32, 32),
        )
        background_label = ctk.CTkLabel(root, image=bg_image, text="")
        background_label.place(x=0, y=0, relwidth=1, relheight=1)
    except Exception as e:
        logger.error(f"Error loading GUI assets: {e}", exc_info=True)
        game_ico = None  # Ensure variable exists even on failure

    # Main frame
    main_frame = ctk.CTkFrame(root, corner_radius=20, fg_color="transparent")
    main_frame.place(relx=0.5, rely=0.5, anchor=ctk.CENTER)
    main_frame.grid_columnconfigure(0, weight=1)
    # Configure rows as before...
    main_frame.grid_rowconfigure(6, weight=1)  # Log Frame row needs weight to expand

    # --- REMOTE UPDATE HEADING AND VERSION (Row 0) ---
    remote_heading_label = ctk.CTkLabel(main_frame, text="Remote Update (Latest Official Mod)", font=("Arial", 16, "bold"))
    remote_heading_label.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")

    # Place mod version label in column 2, aligned right within its cell
    global mod_version_label
    mod_version_label = ctk.CTkLabel(main_frame, text="Installed Mod Version: Checking...")
    # Note: Initial text might be updated shortly after by update_mod_version_display
    mod_version_label.grid(row=0, column=0, padx=(0, 20), pady=(15, 5), sticky="e")

    # --- LATEST AVAILABLE VERSION LABEL (Row 1) ---
    global latest_mod_available_label
    latest_mod_available_label = ctk.CTkLabel(main_frame, text="Latest Available: Checking...")
    latest_mod_available_label.grid(row=0, column=0, padx=(0, 20), pady=(45, 0), sticky="e")

    rotwk_path_label = ctk.CTkLabel(main_frame, text="RoTWK Installation Path:", font=TEXT_FONT)
    rotwk_path_label.grid(row=1, column=0, padx=20, pady=(5, 0), sticky="w")

    remote_frame = ctk.CTkFrame(main_frame)
    remote_frame.grid(row=2, column=0, padx=20, pady=(5, 10), sticky="ew")
    remote_frame.grid_columnconfigure(0, weight=1)  # Entry expands

    rotwk_path_entry = ctk.CTkEntry(remote_frame, font=TEXT_FONT)
    rotwk_path_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
    rotwk_default_path = find_rotwk_install_path(REGISTRY_PATHS_ROTWK) or "NOT FOUND!"
    loaded_rotwk_path = load_config(
        APPDATA_FOLDER + CONFIG_FILE_NAME,
        CONFIG_PATH_SECTION,
        ROTWK_CONTENT_KEY,
        rotwk_default_path,
    )
    rotwk_path_entry.insert(0, loaded_rotwk_path)

    browse_button_remote = ctk.CTkButton(
        remote_frame,
        text="Browse...",
        font=TERTIARY_BUTTON_FONT,
        command=browse_rotwk_path,
        width=80,
        fg_color=BUTTON_TERTIARY_BG,
        hover_color=BUTTON_PRIMARY_HOVER,
        border_color=BUTTON_PRIMARY_BORDER,
        border_width=1,
    )
    browse_button_remote.grid(row=0, column=1, padx=5, pady=10)

    remote_update_button = ctk.CTkButton(
        remote_frame,
        text="Remote Update",
        font=PRIMARY_BUTTON_FONT,
        text_color=TEXT_PRIMARY,
        command=on_remote_update_click,
        fg_color=BUTTON_PRIMARY_BG,
        hover_color=BUTTON_PRIMARY_HOVER,
        border_color=BUTTON_PRIMARY_BORDER,
        border_width=1,
    )
    remote_update_button.grid(row=0, column=2, padx=(5, 10), pady=10)

    # --- LOCAL UPDATE SECTION ---
    local_heading_label = ctk.CTkLabel(main_frame, text="Local Update (Test Local Changes)", font=("Arial", 16, "bold"))
    local_heading_label.grid(row=3, column=0, padx=20, pady=(15, 5), sticky="w")

    local_frame = ctk.CTkFrame(main_frame)
    local_frame.grid(row=4, column=0, padx=20, pady=(5, 10), sticky="ew")
    local_frame.grid_columnconfigure(0, weight=1)  # Entry expands

    local_path_entry = ctk.CTkEntry(local_frame, font=TEXT_FONT)
    local_path_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
    loaded_local_path = load_config(
        APPDATA_FOLDER + CONFIG_FILE_NAME,
        CONFIG_PATH_SECTION,
        LOCAL_CONTENT_KEY,
        "Insert DEV Mod folder path here",
    )
    local_path_entry.insert(0, loaded_local_path)

    browse_button_local = ctk.CTkButton(
        local_frame,
        text="Browse...",
        font=TERTIARY_BUTTON_FONT,
        command=browse_local_dev_path,
        width=80,
        fg_color=BUTTON_TERTIARY_BG,
        hover_color=BUTTON_PRIMARY_HOVER,
        border_color=BUTTON_SECONDARY_HOVER,
        border_width=1,
    )
    browse_button_local.grid(row=0, column=1, padx=5, pady=10)

    local_update_button = ctk.CTkButton(
        local_frame,
        text="Local Update",
        font=SECONDARY_BUTTON_FONT,
        text_color=BUTTON_TEXT_SECONDARY,
        command=on_local_update_click,
        fg_color=BUTTON_SECONDARY_BG,
        hover_color=BUTTON_PRIMARY_HOVER,
        border_color=BUTTON_SECONDARY_HOVER,
        border_width=2,
    )
    local_update_button.grid(row=0, column=2, padx=(5, 10), pady=10)

    # --- STATUS FLAG & LAUNCH (Row 5) ---
    # REVERT this section to its original state (before adding disable_mod_button here)
    flag_frame = ctk.CTkFrame(main_frame)
    flag_frame.grid(row=5, column=0, padx=20, pady=(10, 10), sticky="ew")
    # Configure columns: 0 for label (stretches), 1 for Kill, 2 for Launch
    flag_frame.grid_columnconfigure(0, weight=1)  # Label takes available space
    flag_frame.grid_columnconfigure(1, weight=0)  # Kill button fixed width
    flag_frame.grid_columnconfigure(2, weight=0)  # Launch button fixed width

    is_admin_flag = is_admin()
    flag_text = "Administrator privileges verified." if is_admin_flag else "ERROR! Please, run the software as admin."
    flag_color = "green" if is_admin_flag else "red"
    flag_label = ctk.CTkLabel(flag_frame, text=flag_text, font=FLAG_FONT, text_color=flag_color)
    flag_label.grid(row=0, column=0, padx=10, pady=5, sticky="ew")  # Column 0

    # --- Kill Game button --- # (Back to Column 1)
    kill_game_button = ctk.CTkButton(
        flag_frame,
        text="Kill Game",
        font=TERTIARY_BUTTON_FONT,
        command=on_kill_game_click,
        fg_color="#6c1f0e",
        hover_color="#B22222",
        text_color="white",
        border_color="#FF6347",
        border_width=1,
        width=120,
    )
    kill_game_button.grid(row=0, column=1, padx=(5, 5), pady=5, sticky="e")  # Column 1

    # --- Launch Game button --- # (Back to Column 2)
    launch_game_button = ctk.CTkButton(
        flag_frame,
        text="Launch Game",
        image=game_ico,  # Make sure game_ico is loaded earlier
        font=SECONDARY_BUTTON_FONT,
        command=on_launch_game_click,
        fg_color="#1c2c2c",
        hover_color=BUTTON_PRIMARY_HOVER,
        border_color=BUTTON_SECONDARY_HOVER,
        border_width=1,
        width=120,
    )
    launch_game_button.grid(row=0, column=2, padx=(0, 10), pady=5, sticky="e")  # Column 2

    # --- LOG CONSOLE ---
    log_frame = ctk.CTkFrame(main_frame)
    log_frame.grid(row=6, column=0, padx=10, pady=(10, 10), sticky="nsew")
    log_frame.grid_rowconfigure(1, weight=1)  # Make text area expand
    log_frame.grid_columnconfigure(0, weight=1)

    log_label = ctk.CTkLabel(log_frame, text="Log Console:", font=TEXT_FONT)
    log_label.grid(row=0, column=0, sticky="w", pady=(5, 5), padx=10)

    log_console = scrolledtext.ScrolledText(
        log_frame,
        wrap=ctk.WORD,
        height=10,
        state="disabled",
        relief="flat",
        borderwidth=1,
    )
    log_console.configure(bg="#2B2B2B", fg="#DCE4EE", insertbackground="#DCE4EE")
    log_console.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="nsew")

    # --- Buttons in the Log Frame (Row 2) ---

    # --- Remove Mod button --- #
    remove_mod_button = ctk.CTkButton(
        log_frame,
        text="Remove Mod",
        font=TERTIARY_BUTTON_FONT,
        command=on_remove_mod_click,
        fg_color="#505050",
        hover_color="#686868",
        text_color="#D0D0D0",
        border_color="#404040",
        border_width=1,
        width=120,
    )
    # Column 1 for Remove Mod button
    remove_mod_button.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="w")  # sticky="e" aligns right within the cell

    # Clear Log button
    clear_log_button = ctk.CTkButton(
        log_frame,
        text="Clear Log",
        command=clear_log,
        fg_color="#555",
        hover_color="#777",
    )
    clear_log_button.grid(row=2, column=0, pady=(5, 10), padx=10, sticky="e")

    # --- Final Setup ---
    setup_logging_to_text_widget()  # Connect logger to the GUI console

    # Log initial status messages *after* logger is connected to GUI
    logger.info(f"Application started. Version: {__APP_VERSION__}")
    if is_admin_flag:
        logger.info("Running with administrator privileges.")
    else:
        logger.error("Running without administrator privileges.")

    # Display changelog if exits
    show_changelog_if_exists()

    # Perform initial update check (silent unless update found)
    perform_update_check(show_no_update_message=False)

    update_mod_version_display(loaded_rotwk_path)
    start_fetch_latest_mod_version_thread()

    root.mainloop()


# Note: This file now only defines the GUI structure and logic.
# It should be run via the main.py entry point.
