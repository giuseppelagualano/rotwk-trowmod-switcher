import customtkinter as ctk
import logging
from tkinter import scrolledtext
from PIL import Image

from core.archiver import create_trowmod_ini_big_archive
from core.config import *
from core.mod_retriever import update_rotwk_with_latest_mod
from core.registry import find_rotwk_install_path
from core.utils import is_admin, resource_path

# --- Configuration ---

REPO_FULL_NAME = f"{REPO_OWNER}/{REPO_NAME}"

# Set up logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logger = logging.getLogger(__name__)

# --- GUI Setup ---

def setup_logging_to_text(log_console):
    class TextHandler(logging.Handler):
        def emit(self, record):
            msg = self.format(record)
            log_console.configure(state='normal')
            log_console.insert(ctk.END, msg + '\n')
            log_console.configure(state='disabled')
            log_console.see(ctk.END)
            log_console.update_idletasks()

    handler = TextHandler()
    handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(handler)

def clear_log():
    log_console.config(state='normal')
    log_console.delete('1.0', ctk.END)
    log_console.config(state='disabled')

def update_flag(success):
    if success:
        flag_label.configure(text="Update completed!", text_color="green")
    else:
        flag_label.configure(text="ERROR!!", text_color="red")

def on_remote_update_click():
    logger.info("Update started!")
    flag_label.configure(text="Waiting for update...", text_color="white")

    rotwk_install_path = find_rotwk_install_path(REGISTRY_PATHS_ROTWK)

    if not rotwk_install_path:
        logger.critical("Could not find RoTWK installation path in the registry. Script cannot continue.")
        update_flag(False)

    if update_rotwk_with_latest_mod(repo_full_name=REPO_FULL_NAME, game_path=rotwk_install_path):
        update_flag(True)
        logger.info("Update completed.")
    else:
        update_flag(False)

def on_local_update_click():
    logger.info("Update started!")
    flag_label.configure(text="Waiting for update...", text_color="white")

    rotwk_install_path = find_rotwk_install_path(REGISTRY_PATHS_ROTWK)

    if not rotwk_install_path:
        logger.critical("Could not find RoTWK installation path in the registry. Script cannot continue.")
        update_flag(False)

    source_content_path = local_path_entry.get()

    if not source_content_path.strip():  # .strip() rimuove spazi bianchi iniziali e finali
        logger.warning("Local content path is empty. Update cannot proceed.")
        flag_label.configure(text="Error: Local path cannot be empty.", text_color="yellow")
        return  # Esci dalla funzione se il campo è vuoto

    logger.info(f"Using local content path: {source_content_path}")

    if create_trowmod_ini_big_archive(
                    source_dir_path=source_content_path,
                    output_dir_path=rotwk_install_path,
                    archive_name=DEFAULT_ARCHIVE_NAME
                ):
        update_flag(True)
        logger.info("Update completed.")
    else:
        update_flag(False)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

root = ctk.CTk()
root.resizable(False, False)  # Disabilita il ridimensionamento della finestra
root.geometry("1200x900")
root.title("RoTWK Mod Updater")

# Carica immagine di sfondo (assicurati di avere un'immagine adatta)
try:
    bg_image = ctk.CTkImage(light_image=Image.open(resource_path('src/assets/bg_ai_gen.jpeg')), dark_image=Image.open(resource_path('src/assets/bg_ai_gen.jpeg')), size=(1200, 1000))
    background_label = ctk.CTkLabel(root, image=bg_image, text="")
    background_label.place(x=0, y=0, relwidth=1, relheight=1)
except Exception as e:
    print("error: ", e)

# Frame principale per i widget
main_frame = ctk.CTkFrame(root, corner_radius=10, width=700, height=500) # Width e height passati al costruttore
main_frame.place(relx=0.5, rely=0.5, anchor=ctk.CENTER)

# --- REMOTE UPDATE SECTION ---
remote_frame = ctk.CTkFrame(main_frame)
remote_frame.pack(pady=(10, 20), fill="x", padx=40) # SOME VERTICAL PADDING ABOVE AND BELOW TO VISUALLY SEPARATE SECTIONS

remote_update_button = ctk.CTkButton(
    remote_frame,
    text="Update to latest released RoTWK Mod",
    font=PRIMARY_BUTTON_FONT,
    text_color=TEXT_PRIMARY,
    command=on_remote_update_click,
    fg_color=BUTTON_PRIMARY_BG,
    hover_color=BUTTON_PRIMARY_HOVER,
    border_color=BUTTON_PRIMARY_BORDER,
    border_width=1,
)
remote_update_button.pack(pady=5, fill="x", padx=40) # VERTICAL PADDING FOR THE BUTTON AND FILL TO EXPAND HORIZONTALLY WITHIN ITS FRAME

# --- LOCAL UPDATE SECTION ---
local_frame = ctk.CTkFrame(main_frame)
local_frame.pack(pady=(0, 10), fill="x", padx=20) # SOME VERTICAL PADDING BELOW

local_path_entry = ctk.CTkEntry(local_frame, font=TEXT_FONT, placeholder_text="Path to local RoTWK Mod folder")
local_path_entry.pack(side="left", padx=(0, 5), fill="x", expand=True) # ALIGNS TO THE LEFT, ADDS A SMALL RIGHT PADDING, EXPANDS HORIZONTALLY

local_update_button = ctk.CTkButton(
    local_frame,
    text="Update local RoTWK Mod",
    font=SECONDARY_BUTTON_FONT,
    text_color=BUTTON_TEXT_SECONDARY,
    command=on_local_update_click,
    fg_color=BUTTON_SECONDARY_BG,
    hover_color=BUTTON_SECONDARY_BG,
    border_color=BUTTON_SECONDARY_HOVER,
    border_width=2,
)
local_update_button.pack(side="left", padx=(5, 0)) # ALIGNS TO THE LEFT (NEXT TO THE ENTRY), ADDS A SMALL LEFT PADDING

# --- ADMIN FLAG SECTION ---
flag_frame = ctk.CTkFrame(main_frame)
flag_frame.pack(pady=(10, 10), fill="x", padx=40)

if is_admin():
    flag_label = ctk.CTkLabel(flag_frame, text="Waiting for action...", font=LABEL_FONT)
else:
    flag_label = ctk.CTkLabel(flag_frame, text="ERROR! Please, run the software as admin.", font=LABEL_FONT, text_color="red")
flag_label.pack(fill="x") # FILLS THE HORIZONTAL SPACE OF ITS FRAME

# --- LOG CONSOLE SECTION ---
log_frame = ctk.CTkFrame(main_frame)
log_frame.pack(padx=10, pady=(15, 10), fill="both", expand=True) # HORIZONTAL AND VERTICAL PADDING, FILLS AVAILABLE SPACE

log_label = ctk.CTkLabel(log_frame, text="Log Console:", font=TEXT_FONT)
log_label.pack(anchor="w", pady=(0, 5), padx=40) # ANCHORS TO THE WEST (LEFT), ADDS SOME BOTTOM PADDING

log_console = scrolledtext.ScrolledText(log_frame, wrap=ctk.WORD, height=10, state='disabled', bg="#333", fg="white")
log_console.pack(fill="both", expand=True) # FILLS BOTH HORIZONTAL AND VERTICAL SPACE, AND EXPANDS IF THE WINDOW IS RESIZED
setup_logging_to_text(log_console)

clear_log_button = ctk.CTkButton(
    log_frame,
    text="Clear Log",
    command=clear_log,
    fg_color="#555",  # DARK GRAY
    hover_color="#777" # LIGHTER GRAY
)
clear_log_button.pack(pady=(5, 0), anchor="e") # VERTICAL PADDING, ANCHORS TO THE EAST (RIGHT)

# EXAMPLE USAGE OF THE LOG CONSOLE
logger.info("Starting application...")
logger.info("Checking administrator privileges...")
if not is_admin():
    logger.error("Error: application not run as administrator.")
else:
    logger.info("Administrator privileges verified.")

root.mainloop()