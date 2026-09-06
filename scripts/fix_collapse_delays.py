import glob
import os
import re


def correggi_delay_crollo_strutture_regex(cartella_ini_mod):
    """
    Scansiona tutti i file .ini e sovrascrive Min/MaxCollapseDelay se impostati a 0,
    utilizzando le regex per gestire qualsiasi combinazione di spazi o tabulazioni.
    """
    print("🧹 Avvio correzione automatica tramite Regex dei CollapseDelay...")

    # Cerca ricorsivamente tutti i file .ini
    file_ini = glob.glob(os.path.join(cartella_ini_mod, "**", "*.ini"), recursive=True)
    contatore_correzioni = 0

    # Regex spiegate:
    # ^[ \t]* -> Cerca spazi o tab a inizio riga
    # MinCollapseDelay -> Trova la parola chiave
    # [ \t]*=[ \t]* -> Gestisce qualsiasi spazio prima e dopo il simbolo uguale (=)
    # 0+ -> Trova uno o più zeri (es. 0, 00, 000)
    # (?=[ \t]*(?:;|$)) -> Sostituisce solo un valore numerico uguale a zero,
    # non l'inizio di valori come 0.5 o 01.
    regex_min = re.compile(r"^([ \t]*MinCollapseDelay[ \t]*=[ \t]*)0+(?=[ \t]*(?:;|$))", re.IGNORECASE | re.MULTILINE)
    regex_max = re.compile(r"^([ \t]*MaxCollapseDelay[ \t]*=[ \t]*)0+(?=[ \t]*(?:;|$))", re.IGNORECASE | re.MULTILINE)

    for percorso_file in file_ini:
        try:
            with open(percorso_file, encoding="utf-8", errors="ignore") as f:
                contenuto = f.read()

            # Verifica se ci sono occorrenze nel testo
            match_min = regex_min.search(contenuto)
            match_max = regex_max.search(contenuto)

            if match_min or match_max:
                # \1 mantiene l'indentazione originale e la spaziatura intorno al simbolo '='
                if match_min:
                    contenuto = regex_min.sub(r"\g<1>500", contenuto)
                if match_max:
                    contenuto = regex_max.sub(r"\g<1>2000", contenuto)

                with open(percorso_file, "w", encoding="utf-8") as f:
                    f.write(contenuto)

                contatore_correzioni += 1
                print(f"🔧 Corretto con Regex: {os.path.basename(percorso_file)}")

        except Exception as e:
            print(f"❌ Impossibile elaborare il file {os.path.basename(percorso_file)}: {e}")

    print("-" * 50)
    print(f"✨ Operazione completata! Modificati con successo {contatore_correzioni} file di strutture.")


# --- CONFIGURAZIONE ---
# Sostituisci con il percorso della cartella dove tieni i file .ini estratti della tua mod
cartella_mod_ini = r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini"

# Esegui lo script aggiornato
correggi_delay_crollo_strutture_regex(cartella_mod_ini)
