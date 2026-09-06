import os

import pefile


def controlla_patch_4gb_totale(cartella_gioco):
    """
    Verifica lo stato della Patch 4GB (Large Address Aware) sia su lotrbfme2ep1.exe che su game.dat.
    """
    file_da_controllare = {"Launcher": os.path.join(cartella_gioco, "lotrbfme2ep1.exe"), "Core Engine": os.path.join(cartella_gioco, "game.dat")}

    tutto_ok = True

    print("🔍 INIZIO CHECK MEMORIA AVANZATO (RotWK) 🔍\n" + "=" * 45)

    for ruolo, percorso in file_da_controllare.items():
        if not os.path.exists(percorso):
            print(f"❌ Errore: Il file {ruolo} non esiste nel percorso specificato.\n👉 ({percorso})")
            tutto_ok = False
            continue

        try:
            # Carica l'header del file (funziona sia su .exe che su .dat poiché game.dat è strutturalmente un PE)
            pe = pefile.PE(percorso, fast_load=True)

            # Verifica il flag IMAGE_FILE_LARGE_ADDRESS_AWARE (0x0020)
            is_4gb_active = bool(pe.FILE_HEADER.Characteristics & pefile.IMAGE_CHARACTERISTICS["IMAGE_FILE_LARGE_ADDRESS_AWARE"])

            nome_file = os.path.basename(percorso)
            if is_4gb_active:
                print(f"✅ [{ruolo}] {nome_file} -> Patch 4GB ATTIVA!")
            else:
                print(f"🚨 [{ruolo}] {nome_file} -> Patch 4GB ASSENTE (Limitato a 2GB!)")
                tutto_ok = False

        except Exception as e:
            print(f"❌ Errore durante l'analisi di {os.path.basename(percorso)}: {e}")
            tutto_ok = False

    print("=" * 45)
    if tutto_ok:
        print("🎉 DIAGNOSI: Entrambi i file sono patchati. Il gioco sfrutta 4GB di RAM.")
    else:
        print("⚠️ ATTENZIONE: Almeno un file critico è limitato. Rischio crash elevato in multiplayer!")

    return tutto_ok


# --- CONFIGURAZIONE ---
# Inserisci qui il percorso della cartella principale di installazione di RotWK
cartella_installazione = r"C:\Program Files (x86)\Electronic Arts\L'Ascesa del Re Stregone"

# Esegui il doppio controllo
controlla_patch_4gb_totale(cartella_installazione)
