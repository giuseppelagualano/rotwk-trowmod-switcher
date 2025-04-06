import customtkinter as ctk
import logging
from tkinter import scrolledtext
from PIL import Image

from core.archiver import create_trowmod_ini_big_archive
from core.config import *
from core.mod_retriever import update_rotwk_with_latest_mod
from core.registry import find_rotwk_install_path
from core.utils import is_admin, resource_path
from tkinter import filedialog

import threading

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

    if not rotwk_path_entry.get():
        logger.critical("Could not find RoTWK installation path. Script cannot continue.")
        update_flag(False)

    if update_rotwk_with_latest_mod(repo_full_name=REPO_FULL_NAME, game_path=rotwk_path_entry.get()):
        update_flag(True)
        logger.info("Update completed.")
    else:
        update_flag(False)

def on_local_update_click():
    logger.info("Update started!")
    flag_label.configure(text="Waiting for update...", text_color="white")

    if not rotwk_path_entry.get():
        logger.critical("Could not find RoTWK installation path. Script cannot continue.")
        update_flag(False)

    source_content_path = local_path_entry.get()

    if not source_content_path.strip():  # .strip() rimuove spazi bianchi iniziali e finali
        logger.warning("Local content path is empty. Update cannot proceed.")
        flag_label.configure(text="Error: Local path cannot be empty.", text_color="yellow")
        return  # Esci dalla funzione se il campo è vuoto

    logger.info(f"Using local content path: {source_content_path}")

    if create_trowmod_ini_big_archive(
                    source_dir_path=source_content_path,
                    output_dir_path=rotwk_path_entry.get(),
                    archive_name=DEFAULT_ARCHIVE_NAME
                ):
        update_flag(True)
        logger.info("Update completed.")
    else:
        update_flag(False)

# --- Funzione per il bottone Sfoglia ---
def browse_rotwk_path():
    # Chiede all'utente di selezionare una directory
    directory = filedialog.askdirectory(title="Select RoTWK Installation Folder")
    if directory: # Se l'utente seleziona una cartella e non annulla
        rotwk_path_entry.delete(0, ctk.END) # Cancella il contenuto attuale dell'entry
        rotwk_path_entry.insert(0, directory) # Inserisce il nuovo percorso
        logger.info(f"RoTWK path set to: {directory}")

def browse_local_dev_path(): # <-- NUOVA FUNZIONE PER IL PATH LOCALE
    directory = filedialog.askdirectory(title="Select Local DEV Mod Folder")
    if directory:
        local_path_entry.delete(0, ctk.END) # Cancella il contenuto attuale
        local_path_entry.insert(0, directory) # Inserisce il nuovo percorso
        logger.info(f"Local DEV Mod path set to: {directory}")

###### MAIN ####

rotwk_default_path = find_rotwk_install_path(REGISTRY_PATHS_ROTWK)
if not rotwk_default_path:
    rotwk_default_path = "NOT FOUND!"
    
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

# Configura le colonne e le righe del grid dentro main_frame
main_frame.grid_columnconfigure(0, weight=1)
main_frame.grid_rowconfigure(0, weight=0) # Remote Section Heading
main_frame.grid_rowconfigure(1, weight=0) # Remote Path Label
main_frame.grid_rowconfigure(2, weight=0) # Remote Frame (Entry/Buttons)
main_frame.grid_rowconfigure(3, weight=0) # Local Section Heading
# main_frame.grid_rowconfigure(4, weight=0) # Rimuoviamo label separata per local path (opzionale)
main_frame.grid_rowconfigure(4, weight=0) # Local Frame (Entry/Buttons) <-- AGGIORNATO INDICE
main_frame.grid_rowconfigure(5, weight=0) # Admin Flag Frame          <-- AGGIORNATO INDICE
main_frame.grid_rowconfigure(6, weight=1) # Log Frame                 <-- AGGIORNATO INDICE

# --- REMOTE UPDATE SECTION ---
remote_heading_label = ctk.CTkLabel(main_frame, text="Remote Update", font=("Arial", 16, "bold"))
remote_heading_label.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")

rotwk_path_label = ctk.CTkLabel(main_frame, text="RoTWK Installation Path (detected, editable):", font=TEXT_FONT)
rotwk_path_label.grid(row=1, column=0, padx=20, pady=(5, 0), sticky="w")

remote_frame = ctk.CTkFrame(main_frame)
remote_frame.grid(row=2, column=0, padx=20, pady=(5, 10), sticky="ew")
remote_frame.grid_columnconfigure(0, weight=1) # Entry
remote_frame.grid_columnconfigure(1, weight=0) # Browse Btn
remote_frame.grid_columnconfigure(2, weight=0) # Update Btn

rotwk_path_entry = ctk.CTkEntry(remote_frame, font=TEXT_FONT)
rotwk_path_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
rotwk_path_entry.insert(0, rotwk_default_path)

browse_button_remote = ctk.CTkButton(remote_frame, text="Browse...", font=SECONDARY_BUTTON_FONT, command=browse_rotwk_path, width=80)
browse_button_remote.grid(row=0, column=1, padx=5, pady=10)

remote_update_button = ctk.CTkButton(
    remote_frame, text="Update Mod", font=PRIMARY_BUTTON_FONT, text_color=TEXT_PRIMARY, command=on_remote_update_click,
    fg_color=BUTTON_PRIMARY_BG, hover_color=BUTTON_PRIMARY_HOVER, border_color=BUTTON_PRIMARY_BORDER, border_width=1,
)
remote_update_button.grid(row=0, column=2, padx=(5, 10), pady=10)

# --- LOCAL UPDATE SECTION ---
local_heading_label = ctk.CTkLabel(main_frame, text="Local Update", font=("Arial", 16, "bold"))
# Riga 3
local_heading_label.grid(row=3, column=0, padx=20, pady=(15, 5), sticky="w")

# Frame locale - ora userà 3 colonne come quello remoto
local_frame = ctk.CTkFrame(main_frame)
# Riga 4
local_frame.grid(row=4, column=0, padx=20, pady=(5, 10), sticky="ew") # Modificato pady per coerenza
# Configura 3 colonne: Entry (espandibile), Sfoglia (fisso), Update (fisso)
local_frame.grid_columnconfigure(0, weight=1)
local_frame.grid_columnconfigure(1, weight=0)
local_frame.grid_columnconfigure(2, weight=0)

# Entry locale - Manteniamo il placeholder qui perché è un input richiesto
local_path_entry = ctk.CTkEntry(local_frame, font=TEXT_FONT, placeholder_text="Insert DEV Mod folder path here")
local_path_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew") # Colonna 0

# NUOVO Bottone Sfoglia locale
browse_button_local = ctk.CTkButton(
    local_frame,
    text="Browse...",
    font=SECONDARY_BUTTON_FONT,
    command=browse_local_dev_path, # Usa la nuova funzione browse locale
    width=80
)
browse_button_local.grid(row=0, column=1, padx=5, pady=10) # Colonna 1

# Bottone Update locale esistente
local_update_button = ctk.CTkButton(
    local_frame,
    text="Update Local", # Testo leggermente accorciato
    font=SECONDARY_BUTTON_FONT, # Mantenuto stile secondario
    text_color=BUTTON_TEXT_SECONDARY,
    command=on_local_update_click, # Questo comando ora leggerà l'entry
    fg_color=BUTTON_SECONDARY_BG,
    hover_color=BUTTON_SECONDARY_HOVER,
    border_color=BUTTON_SECONDARY_HOVER,
    border_width=2,
)
local_update_button.grid(row=0, column=2, padx=(5, 10), pady=10) # Colonna 2

# --- ADMIN FLAG SECTION ---
flag_frame = ctk.CTkFrame(main_frame)
# Riga 5
flag_frame.grid(row=5, column=0, padx=20, pady=(10, 10), sticky="ew")
flag_frame.grid_columnconfigure(0, weight=1)
if is_admin():
    flag_text = "Administrator privileges verified."
    flag_color = "green"
else:
    flag_text = "ERROR! Please, run the software as admin."
    flag_color = "red"
flag_label = ctk.CTkLabel(flag_frame, text=flag_text, font=LABEL_FONT, text_color=flag_color)
flag_label.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

# --- LOG CONSOLE SECTION ---
log_frame = ctk.CTkFrame(main_frame)
# Riga 6
log_frame.grid(row=6, column=0, padx=10, pady=(10, 10), sticky="nsew")

log_label = ctk.CTkLabel(log_frame, text="Log Console:", font=TEXT_FONT)
log_label.pack(anchor="w", pady=(5, 5), padx=10)

log_console = scrolledtext.ScrolledText(log_frame, wrap=ctk.WORD, height=10, state='disabled', relief="flat", borderwidth=1)
log_console.configure(bg="#2B2B2B", fg="#DCE4EE", insertbackground="#DCE4EE")
log_console.pack(padx=10, pady=(0, 5), fill="both", expand=True)

# Setup del logger per scrivere nel widget log_console (assicurati sia chiamato dopo la creazione di log_console)
setup_logging_to_text(log_console)

clear_log_button = ctk.CTkButton(log_frame, text="Clear Log", command=clear_log, fg_color="#555", hover_color="#777")
clear_log_button.pack(pady=(5, 10), padx=10, anchor="e")

# --- Log Iniziali ---
logger.info("Application started.")
if is_admin():
    logger.info("Running with administrator privileges.")
else:
    logger.error("Running without administrator privileges.")

# --- Avvio UI ---
root.mainloop()