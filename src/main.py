import customtkinter as ctk
import logging
import threading  # Imported for multithreading
from tkinter import scrolledtext
from PIL import Image
from tkinter import filedialog

# Assuming 'core' directory is structured correctly relative to this script
from core.archiver import create_trowmod_ini_big_archive
from core.config import * # Ensure constants like REPO_OWNER, TEXT_FONT etc. are defined here
from core.mod_retriever import update_rotwk_with_latest_mod
from core.registry import find_rotwk_install_path
from core.utils import is_admin, resource_path

# --- Configuration ---
# Ensure REPO_OWNER and REPO_NAME are defined in core.config
REPO_FULL_NAME = f"{REPO_OWNER}/{REPO_NAME}"

# Set up logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logger = logging.getLogger(__name__)

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


def _run_local_update_thread(source_dir_path, output_dir_path, archive_name):
    """Target function for the local update worker thread."""
    success = False
    try:
        # Log start (will be scheduled to GUI thread by the handler)
        logger.info(f"Starting local update thread from {source_dir_path}...")
        # --- Blocking Operation ---
        success = create_trowmod_ini_big_archive(
            source_dir_path=source_dir_path,
            output_dir_path=output_dir_path,
            archive_name=archive_name
        )
        # --- End Blocking Operation ---
        if success:
            logger.info("Local update thread finished successfully.")
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

    # Disable buttons before starting the thread
    set_buttons_state('disabled')
    # Optionally update status label to "Running..."
    # schedule_gui_update(flag_label.configure, text="Update running...", text_color="yellow")

    # Create and start the worker thread
    thread = threading.Thread(target=_run_local_update_thread, args=(source_content_path, rotwk_path, DEFAULT_ARCHIVE_NAME), daemon=True)
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

def browse_local_dev_path():
    """Opens a dialog to browse for the local DEV mod folder path."""
    directory = filedialog.askdirectory(title="Select Local DEV Mod Folder")
    if directory:
        directory = (directory + "/").replace("/", "\\")
        local_path_entry.delete(0, ctk.END)
        local_path_entry.insert(0, directory)
        logger.info(f"Local DEV Mod path set to: {directory}")

###### MAIN - GUI Construction (Original Code Preserved) ####
rotwk_default_path = find_rotwk_install_path(REGISTRY_PATHS_ROTWK)
if not rotwk_default_path:
    rotwk_default_path = "NOT FOUND!" # Original placeholder

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

root = ctk.CTk()
root.resizable(False, False)
root.geometry("1200x900")
root.title("RoTWK Mod Updater")

# Load background image (Original Code)
try:
    # Ensure resource_path works and points to the correct asset location
    bg_image = ctk.CTkImage(
        light_image=Image.open(resource_path('src/assets/bg_ai_gen.jpeg')),
        dark_image=Image.open(resource_path('src/assets/bg_ai_gen.jpeg')),
        size=(1200, 1000) # Original size
    )
    background_label = ctk.CTkLabel(root, image=bg_image, text="")
    background_label.place(x=0, y=0, relwidth=1, relheight=1)
except FileNotFoundError:
    logger.error("Background image file not found. Please check the path provided to resource_path().")
except Exception as e:
    # Log the specific error during image loading
    logger.error(f"Error loading background image: {e}", exc_info=True)


# Main frame for widgets (Original Code)
main_frame = ctk.CTkFrame(root, corner_radius=10, width=700, height=500) # Original fixed size
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
rotwk_path_entry.insert(0, rotwk_default_path)

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

local_path_entry = ctk.CTkEntry(local_frame, font=TEXT_FONT, placeholder_text="Insert DEV Mod folder path here")
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
logger.info("Application started.")
if is_admin_flag: # Use the stored flag
    logger.info("Running with administrator privileges.")
else:
    logger.error("Running without administrator privileges.") # Original error message


# --- Start UI ---
root.mainloop()