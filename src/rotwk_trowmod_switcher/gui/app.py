# src/gui/app.py
import json
import logging
import os
import subprocess
import sys
import threading
from tkinter import filedialog, messagebox, scrolledtext

import customtkinter as ctk
from PIL import Image

from rotwk_trowmod_switcher.config import (  # Import app name if used in paths/messages
    __APP_NAME__,
    __APP_VERSION__,
    APPDATA_FOLDER,
    CONFIG_FILE_NAME,
    CONFIG_PATH_SECTION,
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
from rotwk_trowmod_switcher.core.mod_retriever import update_rotwk_with_latest_mod
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
remote_update_button = None
local_update_button = None
launch_game_button = None
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
def schedule_gui_update(callback, *args):
    """
    Schedules a function to run safely in the main GUI thread using root.after().
    Args:
        callback: The function to call in the main thread.
        *args: Arguments to pass to the callback function.
    """
    if root and root.winfo_exists():
        root.after(0, callback, *args)
    else:
        logger.warning(f"Warning: Attempted to schedule GUI update but root window no longer exists. Callback: {callback}")


# --- GUI Update Functions ---
def update_flag(success):
    """Updates the status flag label based on the success of an operation."""
    if not flag_label:
        return  # Guard against missing widget
    if success:
        flag_label.configure(text="Update completed!", text_color="green")
        # Run notification in a separate thread to avoid blocking
        windows_notify("Update completed!", "You can now launch the game")
    else:
        flag_label.configure(text="ERROR!! Please, see the logs below!", text_color="red")


def set_buttons_state(new_state):
    """Enables or disables relevant buttons during update operations."""
    widgets = [
        remote_update_button,
        local_update_button,
        launch_game_button,
        browse_button_remote,
        browse_button_local,
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
    flag_label.configure(text="Downloading update...", text_color="yellow")  # Optional status update

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
        logger.info("Running update check in background thread...")
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

    thread = threading.Thread(target=check_thread_target, daemon=True)
    thread.start()


# --- Worker Thread Target Functions ---
def _run_remote_update_thread(repo_full_name, game_path):
    """Target function for the remote update worker thread."""
    success = False
    try:
        logger.info(f"Starting remote update thread for {repo_full_name}...")
        success = update_rotwk_with_latest_mod(repo_full_name=repo_full_name, game_path=game_path)
        if success:
            logger.info("Remote update thread finished successfully.")
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
        )

        if success:
            logger.info("Local update thread finished successfully.")
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
        flag_label.configure(text="Error: RoTWK Path Invalid", text_color="red")
        return

    # Save the confirmed/entered path
    save_config(
        APPDATA_FOLDER + CONFIG_FILE_NAME,
        CONFIG_PATH_SECTION,
        ROTWK_CONTENT_KEY,
        rotwk_path,
    )

    set_buttons_state("disabled")
    flag_label.configure(text="Update running...", text_color="yellow")  # Indicate running

    repo_full_name = f"{REPO_OWNER}/{REPO_NAME}"  # Mod repo
    thread = threading.Thread(target=_run_remote_update_thread, args=(repo_full_name, rotwk_path), daemon=True)
    thread.start()


def on_local_update_click():
    """Handles the click event for the local update button."""
    if not rotwk_path_entry or not local_path_entry or not flag_label:
        return
    logger.info("Local update started!")
    flag_label.configure(text="Waiting for update...", text_color="white")

    rotwk_path = rotwk_path_entry.get()
    if not rotwk_path or rotwk_path == "NOT FOUND!":
        logger.critical("Could not find RoTWK installation path. Update cannot continue.")
        flag_label.configure(text="Error: RoTWK installation path cannot be empty!", text_color="red")
        return

    source_content_path = local_path_entry.get()
    if not source_content_path or source_content_path == "Insert DEV Mod folder path here" or not os.path.isdir(source_content_path):
        logger.error("Local content path is empty or invalid. Update cannot proceed.")
        flag_label.configure(text="Error: Local path cannot be empty or is invalid!", text_color="red")
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
    flag_label.configure(text="Update running...", text_color="yellow")  # Indicate running

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

    game_exe_name = "lotrbfme2ep1.exe"
    full_game_exe_path = os.path.join(rotwk_path, game_exe_name)

    if not os.path.exists(full_game_exe_path):
        logger.error(f"Game executable not found at: {full_game_exe_path}")
        messagebox.showerror(
            "Launch Error",
            f"Could not find the game executable:\n{game_exe_name}\n\nIn the specified path:\n{rotwk_path}",
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
    global launch_game_button, browse_button_remote, browse_button_local
    global rotwk_path_entry, local_path_entry

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

    # --- REMOTE UPDATE SECTION ---
    remote_heading_label = ctk.CTkLabel(
        main_frame,
        text="Remote Update (Latest Official Mod)",
        font=("Arial", 16, "bold"),
    )
    remote_heading_label.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")
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

    # --- STATUS FLAG & LAUNCH ---
    flag_frame = ctk.CTkFrame(main_frame)
    flag_frame.grid(row=5, column=0, padx=20, pady=(10, 10), sticky="ew")
    flag_frame.grid_columnconfigure(0, weight=1)  # Label takes available space

    is_admin_flag = is_admin()
    flag_text = "Administrator privileges verified." if is_admin_flag else "ERROR! Please, run the software as admin."
    flag_color = "green" if is_admin_flag else "red"
    flag_label = ctk.CTkLabel(flag_frame, text=flag_text, font=FLAG_FONT, text_color=flag_color)
    flag_label.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

    launch_game_button = ctk.CTkButton(
        flag_frame,
        text="Launch Game",
        image=game_ico,
        font=SECONDARY_BUTTON_FONT,
        command=on_launch_game_click,
        fg_color="#1c2c2c",
        hover_color=BUTTON_PRIMARY_HOVER,
        border_color=BUTTON_SECONDARY_HOVER,
        border_width=1,
        width=120,
    )
    launch_game_button.grid(row=0, column=1, padx=(5, 10), pady=5, sticky="e")

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

    root.mainloop()


# Note: This file now only defines the GUI structure and logic.
# It should be run via the main.py entry point.
