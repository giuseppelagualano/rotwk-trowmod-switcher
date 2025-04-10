import customtkinter as ctk
import logging
import threading  # Imported for multithreading
from PIL import Image
from tkinter import scrolledtext, filedialog, messagebox

import sys # Needed for updater
import os  # Needed for updater

# Assuming 'core' directory is structured correctly relative to this script
from core.archiver import *
from core.config import * # Ensure constants like REPO_OWNER, TEXT_FONT etc. are defined here
from core.config import __APP_VERSION__, __APP_NAME__
from core.mod_retriever import update_rotwk_with_latest_mod
from core.registry import find_rotwk_install_path
from core.utils import is_admin, load_config, resource_path, save_config
from core.switcher_updater import check_for_updates, download_update, trigger_update_restart

# --- Configuration ---
# Ensure REPO_OWNER and REPO_NAME are defined in core.config
REPO_FULL_NAME = f"{REPO_OWNER}/{REPO_NAME}"

# Set up logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logger = logging.getLogger(__name__)

# --- Auto-Updater Integration ---
def update_progress_handler(downloaded_bytes, total_bytes, percent):
    """ Placeholder for showing download progress in the GUI """
    # In a real implementation, you'd update a progress bar widget
    if total_bytes > 0:
        print(f"Downloading update: {downloaded_bytes} / {total_bytes} ({percent:.1f}%)")
    else:
        print(f"Downloading update: {downloaded_bytes} bytes (total size unknown)")
    # Make sure GUI updates happen safely (e.g., via schedule_gui_update)
    # schedule_gui_update(my_progress_bar.set, percent / 100.0)

def _perform_update_download_and_restart(url):
    """
    Handles the download and restart process in a separate thread
    to avoid blocking the GUI while asking for confirmation.
    """
    logger.info("Starting update download...")
    # This part (download/restart) should ideally run after user confirmation
    # and potentially show progress. For simplicity, direct call here.
    # In a real GUI app, you'd disable buttons, show a progress indicator.

    # For a responsive UI during download, consider another thread + progress bar.
    # Simplified synchronous download here:
    downloaded_path = download_update(url, progress_callback=update_progress_handler)

    if downloaded_path:
        logger.info("Download complete. Triggering update restart.")
        # This call will attempt to exit the application
        if not trigger_update_restart(downloaded_path):
            # If triggering fails, re-enable GUI and show error
            schedule_gui_update(set_buttons_state, 'normal')
            schedule_gui_update(messagebox.showerror, "Update Error", "Failed to start the update process. The downloaded file might be removed. Please try updating manually or restarting the application.")
    else:
        # If download fails, re-enable GUI and show error
        schedule_gui_update(set_buttons_state, 'normal')
        schedule_gui_update(messagebox.showerror, "Update Error", "Failed to download the update file. Please check your internet connection and permissions, then try again.")

def perform_update_check(show_no_update_message=False):
    """
    Checks for updates and prompts the user if one is found.
    Runs the check itself in a separate thread to avoid blocking startup.
    """

    def check_thread_target():
        logger.info("Running update check in background thread...")
        try:
            is_update, latest_v, url = check_for_updates()

            if is_update and url:
                logger.info(f"Update available: Version {latest_v}")
                # Schedule the confirmation dialog back in the main GUI thread
                schedule_gui_update(ask_user_to_update, latest_v, url)
            elif is_update and not url:
                logger.warning("Update check found a new version, but no download URL for the .exe asset.")
                if show_no_update_message: # Only show if manually triggered?
                     schedule_gui_update(messagebox.showinfo, "Update Info", f"A new version ({latest_v}) is available, but the download asset could not be found in the release.")
            elif show_no_update_message:
                logger.info("No update required or check failed.")
                schedule_gui_update(messagebox.showinfo, "Up-to-Date", f"You are running the latest version ({__APP_VERSION__}).")
            else:
                 logger.info("No update required or check failed (silent).")


        except Exception as e:
            logger.error(f"Error during update check thread: {e}", exc_info=True)
            # Optionally inform the user via schedule_gui_update + messagebox

    # Start the check in a daemon thread so it doesn't block app exit
    thread = threading.Thread(target=check_thread_target, daemon=True)
    thread.start()

def ask_user_to_update(latest_v, url):
    """
    Asks the user (in the main thread) if they want to update.
    Must be called via schedule_gui_update or run directly in main thread.
    """
    if not root or not root.winfo_exists(): # Check if window exists
        logger.warning("Update confirmation skipped: Root window closed.")
        return

    confirm = messagebox.askyesno(
        "Update Available",
        f"A new version ({latest_v}) of {__APP_NAME__} is available.\n"
        f"Your current version is {__APP_VERSION__}.\n\n"
        "Do you want to download and install it now?\n"
        "The application will restart."
    )

    if confirm:
        logger.info("User confirmed update. Preparing download and restart.")
        # Disable buttons while update happens
        set_buttons_state('disabled')
        # Optionally show a "downloading..." status
        # schedule_gui_update(flag_label.configure, text="Downloading update...", text_color="yellow")

        # Start the download/restart process. Could be in another thread
        # if download_update itself is blocking and needs progress UI.
        # Simplified: directly call the handler function.
        _perform_update_download_and_restart(url)
    else:
        logger.info("User declined update.")


# --- GUI Setup ---
def setup_logging_to_text(log_console):
    """Sets up logging to redirect output to the provided text widget."""
    class TextHandler(logging.Handler):
        def emit(self, record):
            msg = self.format(record)
            # Schedule log update in the main thread to avoid Tkinter errors from threads
            try:
                # Use .after() to make the GUI update thread-safe
                log_console.after(0, self._update_log_console, msg)
            except Exception as e:
                 # Fallback logging if the widget is somehow destroyed
                print(f"Error updating log console via .after(): {e}\nLog message: {msg}")

        def _update_log_console(self, msg):
             # This method will be called via root.after, ensuring it runs in the main GUI thread
            original_state = log_console.cget('state') # Store original state
            log_console.configure(state='normal')
            log_console.insert(ctk.END, msg + '\n')
            log_console.configure(state=original_state) # Restore original state (usually 'disabled')
            log_console.see(ctk.END)
            # log_console.update_idletasks() # Usually not needed when using .after()

    handler = TextHandler()
    handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(handler)
    # Set a base logging level if not configured elsewhere
    logging.getLogger().setLevel(logging.INFO)


def clear_log():
    """Clears the content of the log console."""
    log_console.configure(state='normal')
    log_console.delete('1.0', ctk.END)
    log_console.configure(state='disabled')

# --- Helper Function for GUI Updates from Threads (English Name) ---
def schedule_gui_update(callback, *args):
    """
    Schedules a function to run safely in the main GUI thread using root.after().
    Args:
        callback: The function to call in the main thread.
        *args: Arguments to pass to the callback function.
    """
    # Check if the root window still exists before scheduling
    if root and root.winfo_exists():
        root.after(0, callback, *args)
    else:
        # Log a warning if the window is closed while a thread tries to update it
        print(f"Warning: Attempted to schedule GUI update but root window no longer exists. Callback: {callback}")


# --- GUI Update Functions (Keep original names, but called via schedule_gui_update) ---
def update_flag(success):
    """Updates the status flag label based on the success of an operation."""
    if success:
        flag_label.configure(text="Update completed!", text_color="green")
    else:
        flag_label.configure(text="ERROR!! Please, see the logs below!", text_color="red") # Kept original error text

# --- Helper Function to Manage Button States (English Name) ---
def set_buttons_state(new_state):
    """
    Enables or disables relevant buttons during update operations.
    Args:
        new_state: 'normal' or 'disabled'.
    """
    remote_update_button.configure(state=new_state)
    local_update_button.configure(state=new_state)
    # Optionally disable browse buttons too, if desired
    browse_button_remote.configure(state=new_state)
    browse_button_local.configure(state=new_state)


# --- Worker Thread Target Functions (English Names) ---

def _run_remote_update_thread(repo_full_name, game_path):
    """Target function for the remote update worker thread."""
    success = False
    try:
        # Log start (will be scheduled to GUI thread by the handler)
        logger.info(f"Starting remote update thread for {repo_full_name}...")
        # --- Blocking Operation ---
        success = update_rotwk_with_latest_mod(repo_full_name=repo_full_name, game_path=game_path)
        # --- End Blocking Operation ---
        if success:
            logger.info("Remote update thread finished successfully.")
        else:
            logger.error("Remote update thread failed.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in remote update thread: {e}")
        success = False # Ensure failure state on exception
    finally:
        # Schedule final GUI updates back to the main thread
        schedule_gui_update(update_flag, success)
        schedule_gui_update(set_buttons_state, 'normal') # Re-enable buttons


def _run_local_update_thread(source_dir_path, output_dir_path):
    """Target function for the local update worker thread."""
    success = False
    try:
        # Log start (will be scheduled to GUI thread by the handler)
        logger.info(f"Starting local update thread from {source_dir_path}...")
        # --- Blocking Operation ---

        ini_success = create_trowmod_ini_big_archive(
            source_dir_path=source_dir_path, # Use the determined content path
            output_dir_path=output_dir_path,
            archive_name=DEFAULT_INI_ARCHIVE_NAME
        )

        arts_success = create_trowmod_arts_big_archive(
            source_dir_path=source_dir_path, # Use the determined content path
            output_dir_path=output_dir_path,
            archive_name=DEFAULT_ARTS_ARCHIVE_NAME
        )

        itlang_success = create_trowmod_itlang_big_archive(
            source_dir_path=source_dir_path, # Use the determined content path
            output_dir_path=output_dir_path,
            archive_name=DEFAULT_ITLANG_ARCHIVE_NAME
        )
        
        # --- End Blocking Operation ---
        if (ini_success and arts_success and itlang_success):
            logger.info("Local update thread finished successfully.")
            success = True
        else:
            logger.error("Local update thread failed.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in local update thread: {e}")
        success = False # Ensure failure state on exception
    finally:
        # Schedule final GUI updates back to the main thread
        schedule_gui_update(update_flag, success)
        schedule_gui_update(set_buttons_state, 'normal') # Re-enable buttons


# --- Original Button Click Handlers (Modified to start threads) ---

def on_remote_update_click():
    """Handles the click event for the remote update button by starting a thread."""
    logger.info("Update started!") # Original log message
    flag_label.configure(text="Waiting for update...", text_color="white") # Original status

    rotwk_path = rotwk_path_entry.get()
    # Use original check logic, but schedule flag update on failure
    if not rotwk_path or rotwk_path == "NOT FOUND!": # Added check for placeholder text
        logger.critical("Could not find RoTWK installation path. Script cannot continue.")
        schedule_gui_update(update_flag, False) # Update flag in main thread
        # Optionally set a more specific error message here if needed, using schedule_gui_update
        # schedule_gui_update(flag_label.configure, text="Error: RoTWK Path Invalid", text_color="red")
        return

    save_config(APPDATA_FOLDER + CONFIG_FILE_NAME, CONFIG_PATH_SECTION, ROTWK_CONTENT_KEY, rotwk_path)

    # Disable buttons before starting the thread
    set_buttons_state('disabled')
    # Optionally update status label to "Running..."
    # schedule_gui_update(flag_label.configure, text="Update running...", text_color="yellow")

    # Create and start the worker thread
    # daemon=True allows the main program to exit even if this thread is running
    thread = threading.Thread(target=_run_remote_update_thread, args=(REPO_FULL_NAME, rotwk_path), daemon=True)
    thread.start()


def on_local_update_click():
    """Handles the click event for the local update button by starting a thread."""
    logger.info("Local update started!") # Original log message
    flag_label.configure(text="Waiting for update...", text_color="white") # Original status

    rotwk_path = rotwk_path_entry.get()
    # Use original check logic, schedule flag update on failure
    if not rotwk_path or rotwk_path == "NOT FOUND!": # Added check for placeholder text
        logger.critical("Could not find RoTWK installation path. Update cannot continue.")
        flag_label.configure(text="Error: RoTWK installation path cannot be empty!", text_color="red")
        return

    source_content_path = local_path_entry.get()
    # Use original check logic, schedule flag update on failure
    if not source_content_path.strip():
        logger.error("Local content path is empty. Update cannot proceed.")
        flag_label.configure(text="Error: Local path cannot be empty!", text_color="red")
        return

    logger.info(f"Using local content path: {source_content_path}") # Original log
    save_config(APPDATA_FOLDER + CONFIG_FILE_NAME, CONFIG_PATH_SECTION, LOCAL_CONTENT_KEY, source_content_path)

    # Disable buttons before starting the thread
    set_buttons_state('disabled')
    # Optionally update status label to "Running..."
    # schedule_gui_update(flag_label.configure, text="Update running...", text_color="yellow")

    # Create and start the worker thread
    thread = threading.Thread(target=_run_local_update_thread, args=(source_content_path, rotwk_path), daemon=True)
    thread.start()


# --- Original Browse Functions (Unchanged) ---
def browse_rotwk_path():
    """Opens a dialog to browse for the RoTWK installation path."""
    directory = filedialog.askdirectory(title="Select RoTWK Installation Folder")
    if directory:
        directory = (directory + "/").replace("/", "\\")
        rotwk_path_entry.delete(0, ctk.END)
        rotwk_path_entry.insert(0, directory)
        logger.info(f"RoTWK path set to: {directory}")
        save_config(APPDATA_FOLDER + CONFIG_FILE_NAME, CONFIG_PATH_SECTION, ROTWK_CONTENT_KEY, rotwk_path_entry.get())

def browse_local_dev_path():
    """Opens a dialog to browse for the local DEV mod folder path."""
    directory = filedialog.askdirectory(title="Select Local DEV Mod Folder")
    if directory:
        directory = (directory + "/").replace("/", "\\")
        local_path_entry.delete(0, ctk.END)
        local_path_entry.insert(0, directory)
        logger.info(f"Local DEV Mod path set to: {directory}")
        save_config(APPDATA_FOLDER + CONFIG_FILE_NAME, CONFIG_PATH_SECTION, LOCAL_CONTENT_KEY, local_path_entry.get())


###### MAIN - GUI Construction (Original Code Preserved) ####
rotwk_default_path = find_rotwk_install_path(REGISTRY_PATHS_ROTWK)
if not rotwk_default_path:
    rotwk_default_path = "NOT FOUND!" # Original placeholder

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

root = ctk.CTk()
root.resizable(False, False)
root.geometry(INITIAL_WINDOW_SIZE)
root.iconbitmap(resource_path('src/assets/bg_ai_gen.ico'))
root.title("RoTWK Mod Switcher")

# Load background image (Original Code)
try:
    # Ensure resource_path works and points to the correct asset location
    bg_image = ctk.CTkImage(
        light_image=Image.open(resource_path('src/assets/bg_ai_gen.jpeg')),
        dark_image=Image.open(resource_path('src/assets/bg_ai_gen.jpeg')),
        size=(1200, 1200) # Original size
    )
    background_label = ctk.CTkLabel(root, image=bg_image, text="")
    background_label.place(x=0, y=0, relwidth=1, relheight=1)
except FileNotFoundError:
    logger.error("Background image file not found. Please check the path provided to resource_path().")
except Exception as e:
    # Log the specific error during image loading
    logger.error(f"Error loading background image: {e}", exc_info=True)


# Main frame for widgets (Original Code)
main_frame = ctk.CTkFrame(root, corner_radius=20) # Original fixed size
main_frame.place(relx=0.5, rely=0.5, anchor=ctk.CENTER) # Original placement

# Configure grid columns and rows inside main_frame (Original Code)
main_frame.grid_columnconfigure(0, weight=1)
main_frame.grid_rowconfigure(0, weight=0)  # Remote Section Heading
main_frame.grid_rowconfigure(1, weight=0)  # Remote Path Label
main_frame.grid_rowconfigure(2, weight=0)  # Remote Frame (Entry/Buttons)
main_frame.grid_rowconfigure(3, weight=0)  # Local Section Heading
main_frame.grid_rowconfigure(4, weight=0)  # Local Frame (Entry/Buttons)
main_frame.grid_rowconfigure(5, weight=0)  # Admin Flag Frame
main_frame.grid_rowconfigure(6, weight=1)  # Log Frame


# --- REMOTE UPDATE SECTION (Original Code) ---
remote_heading_label = ctk.CTkLabel(main_frame, text="Remote Update (pre-game alignment)", font=("Arial", 16, "bold"))
remote_heading_label.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")

rotwk_path_label = ctk.CTkLabel(main_frame, text="RoTWK Installation Path (detected, editable):", font=TEXT_FONT)
rotwk_path_label.grid(row=1, column=0, padx=20, pady=(5, 0), sticky="w")

remote_frame = ctk.CTkFrame(main_frame)
remote_frame.grid(row=2, column=0, padx=20, pady=(5, 10), sticky="ew")
remote_frame.grid_columnconfigure(0, weight=1)  # Entry
remote_frame.grid_columnconfigure(1, weight=0)  # Browse Btn
remote_frame.grid_columnconfigure(2, weight=0)  # Update Btn

rotwk_path_entry = ctk.CTkEntry(remote_frame, font=TEXT_FONT)
rotwk_path_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")

loaded_rotwk_path = load_config(APPDATA_FOLDER + CONFIG_FILE_NAME, CONFIG_PATH_SECTION, ROTWK_CONTENT_KEY, rotwk_default_path)
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
    remote_frame, text="Online Update", font=PRIMARY_BUTTON_FONT, text_color=TEXT_PRIMARY, command=on_remote_update_click, # Command changed
    fg_color=BUTTON_PRIMARY_BG, hover_color=BUTTON_PRIMARY_HOVER, border_color=BUTTON_PRIMARY_BORDER, border_width=1,
)
remote_update_button.grid(row=0, column=2, padx=(5, 10), pady=10)

# --- LOCAL UPDATE SECTION (Original Code) ---
local_heading_label = ctk.CTkLabel(main_frame, text="Local Update (test local changes)", font=("Arial", 16, "bold"))
local_heading_label.grid(row=3, column=0, padx=20, pady=(15, 5), sticky="w")

local_frame = ctk.CTkFrame(main_frame)
local_frame.grid(row=4, column=0, padx=20, pady=(5, 10), sticky="ew")
local_frame.grid_columnconfigure(0, weight=1)
local_frame.grid_columnconfigure(1, weight=0)
local_frame.grid_columnconfigure(2, weight=0)

loaded_local_path_entry = load_config(APPDATA_FOLDER + CONFIG_FILE_NAME, CONFIG_PATH_SECTION, LOCAL_CONTENT_KEY, "Insert DEV Mod folder path here")

local_path_entry = ctk.CTkEntry(local_frame, font=TEXT_FONT)
local_path_entry.insert(0, loaded_local_path_entry)

local_path_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")

browse_button_local = ctk.CTkButton(
    local_frame,
    text="Browse...",
    font=TERTIARY_BUTTON_FONT,
    command=browse_local_dev_path,
    width=80,
    fg_color=BUTTON_TERTIARY_BG,
    hover_color=BUTTON_PRIMARY_HOVER,
    border_color=BUTTON_SECONDARY_HOVER, # Original border color
    border_width=1,
)
browse_button_local.grid(row=0, column=1, padx=5, pady=10)

local_update_button = ctk.CTkButton(
    local_frame,
    text="Local Update",
    font=SECONDARY_BUTTON_FONT,
    text_color=BUTTON_TEXT_SECONDARY,
    command=on_local_update_click, # Command changed
    fg_color=BUTTON_SECONDARY_BG,
    hover_color=BUTTON_PRIMARY_HOVER, # Original hover color
    border_color=BUTTON_SECONDARY_HOVER, # Original border color
    border_width=2,
)
local_update_button.grid(row=0, column=2, padx=(5, 10), pady=10)

# --- ADMIN FLAG SECTION (Original Code) ---
flag_frame = ctk.CTkFrame(main_frame)
flag_frame.grid(row=5, column=0, padx=20, pady=(10, 10), sticky="ew")
flag_frame.grid_columnconfigure(0, weight=1)

# Check admin status once
is_admin_flag = is_admin()
if is_admin_flag:
    flag_text = "Administrator privileges verified." # Original text
    flag_color = "green" # Original color
else:
    flag_text = "ERROR! Please, run the software as admin." # Original text
    flag_color = "red" # Original color

flag_label = ctk.CTkLabel(flag_frame, text=flag_text, font=LABEL_FONT, text_color=flag_color)
flag_label.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

# --- LOG CONSOLE SECTION (Original Code) ---
log_frame = ctk.CTkFrame(main_frame)
log_frame.grid(row=6, column=0, padx=10, pady=(10, 10), sticky="nsew")
# Add grid config to allow log console to expand vertically if desired (optional aesthetic tweak, kept from original if present)
log_frame.grid_rowconfigure(1, weight=1) # Make row 1 (where ScrolledText is) expand
log_frame.grid_columnconfigure(0, weight=1) # Make column 0 expand

log_label = ctk.CTkLabel(log_frame, text="Log Console:", font=TEXT_FONT)
# Changed pack to grid for consistency within log_frame
log_label.grid(row=0, column=0, sticky="w", pady=(5, 5), padx=10)

log_console = scrolledtext.ScrolledText(log_frame, wrap=ctk.WORD, height=10, state='disabled', relief="flat", borderwidth=1)
log_console.configure(bg="#2B2B2B", fg="#DCE4EE", insertbackground="#DCE4EE") # Original styling
# Changed pack to grid
log_console.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="nsew")

# Setup the logger AFTER log_console is created and placed
setup_logging_to_text(log_console)

clear_log_button = ctk.CTkButton(log_frame, text="Clear Log", command=clear_log, fg_color="#555", hover_color="#777")
# Changed pack to grid
clear_log_button.grid(row=2, column=0, pady=(5, 10), padx=10, sticky="e") # Place below text, aligned right

# --- Initial Logs (Original messages) ---
logger.info(f"Application started. Local Version: {__APP_VERSION__}") # Log current version
if is_admin_flag: # Use the stored flag
    logger.info("Running with administrator privileges.")
else:
    logger.error("Running without administrator privileges.") # Original error message


# --- Start UI ---
# Perform initial check silently in the background after a short delay
root.after(1500, perform_update_check, False) # Check after 1.5s, don't show 'up-to-date' msg

root.mainloop()