import customtkinter as ctk
import logging
from tkinter import scrolledtext
from PIL import Image

from core.config import REGISTRY_PATHS_ROTWK, REPO_OWNER, REPO_NAME
from core.mod_retriever import update_rotwk_with_latest_mod
from core.registry import find_rotwk_install_path
from core.utils import is_admin, resource_path

# --- Configuration ---

REPO_FULL_NAME = f"{REPO_OWNER}/{REPO_NAME}"

# Set up logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logger = logging.getLogger(__name__)

# --- GUI Setup ---

def setup_logging_to_text(text_widget):
    class TextHandler(logging.Handler):
        def emit(self, record):
            msg = self.format(record)
            text_widget.configure(state='normal')
            text_widget.insert(ctk.END, msg + '\n')
            text_widget.configure(state='disabled')
            text_widget.see(ctk.END)
            text_widget.update_idletasks()

    handler = TextHandler()
    handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(handler)

def update_flag(success):
    if success:
        flag_label.configure(text="Update completed!", text_color="green")
    else:
        flag_label.configure(text="ERROR!!", text_color="red")

def on_update_click():
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

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

root = ctk.CTk()
root.resizable(False, False)  # Disabilita il ridimensionamento della finestra
root.geometry("1200x600")
root.title("RoTWK Mod Updater")

# Carica immagine di sfondo (assicurati di avere un'immagine adatta)
try:
    bg_image = ctk.CTkImage(light_image=Image.open(resource_path('src/assets/bg.jpg')), dark_image=Image.open(resource_path('src/assets/bg.jpg')), size=(1200, 600))
    background_label = ctk.CTkLabel(root, image=bg_image, text="")
    background_label.place(x=0, y=0, relwidth=1, relheight=1)
except Exception as e:
    print("error: ", e)

# Frame principale per i widget
main_frame = ctk.CTkFrame(root, corner_radius=10, width=700, height=500) # Width e height passati al costruttore
main_frame.place(relx=0.5, rely=0.5, anchor=ctk.CENTER)

# Logo (puoi sostituirlo con il tuo logo ROTWK)
logo_label = ctk.CTkLabel(main_frame, text="RoTWK Updater", font=("Arial", 24, "bold"))
logo_label.pack(pady=20)

# Pulsante di aggiornamento
update_button = ctk.CTkButton(main_frame, text="Update to latest RoTWK Mod", font=("Arial", 24, "bold"), command=on_update_click)
update_button.pack(pady=10)

# Flag label
if is_admin():
    flag_label = ctk.CTkLabel(main_frame, text="", font=("Arial", 15, "bold"))
else:
    flag_label = ctk.CTkLabel(main_frame, text="ERROR! Please, run the software as admin.", font=("Arial", 15, "bold"),  text_color="red")

flag_label.pack(pady=10)

# Console di log
log_console = scrolledtext.ScrolledText(main_frame, wrap=ctk.WORD, height=15, state='disabled', bg="#333", fg="white")
log_console.pack(padx=20, pady=20, fill="both", expand=True)

setup_logging_to_text(log_console)
logger.info("Application started.")

root.mainloop()