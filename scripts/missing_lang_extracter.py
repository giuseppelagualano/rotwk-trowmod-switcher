import os


def extract_lang_strings(str_file_path):
    missing_strings = set()

    try:
        with open(str_file_path, encoding="ansi") as file:
            for line in file:
                line = line.strip()
                if line.startswith("CONTROLBAR:") or line.startswith("Controlbar:") or line.startswith("OBJECT:") or line.startswith("Object:"):
                    if line.lower().startswith("controlbar:"):
                        prefix = "CONTROLBAR:"
                        text = line[len("controlbar:") :]
                    elif line.lower().startswith("object:"):
                        prefix = "OBJECT:"
                        text = line[len("object:") :]

                    # Take only the first word after the tag
                    first_word = text.split()[0] if text.split() else ""
                    missing_strings.add(prefix + first_word)

    except FileNotFoundError:
        print(f"Error: File {str_file_path} not found")
    except Exception as e:
        print(f"Error reading file: {e}")

    return missing_strings


def search_files_for_strings(directory):
    missing_strings = set()
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                with open(file_path, encoding="ansi") as f:
                    for line in f:
                        line = line.strip()
                        for pattern in ["CONTROLBAR:", "controlbar:", "OBJECT:", "object:"]:
                            if pattern in line:
                                start = line.find(pattern)
                                text = line[start:]
                                prefix = "CONTROLBAR:" if pattern.lower() == "controlbar:" else "OBJECT:"
                                # Take only the first word after the tag
                                tag_text = text[len(pattern) :].split()[0] if text[len(pattern) :].split() else ""
                                if tag_text:
                                    missing_strings.add(prefix + tag_text)
            except (FileNotFoundError, UnicodeDecodeError):
                continue
    return missing_strings


# Example usage
if __name__ == "__main__":
    file_path = r"C:\Users\giuse\Documents\GitHub\TROWMod\lang\data\lotr.str"
    lang_strings = extract_lang_strings(file_path)
    mod_strings = search_files_for_strings(r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini")

    print("Mod strings from files:", len(mod_strings))
    print("Language strings from file:", len(lang_strings))

    missing_in_mod = lang_strings - mod_strings
    missing_in_lang = mod_strings - lang_strings
    print("Missing in mod (compared to lang):", len(missing_in_mod))
    print("Missing in language file (compared to mod):", len(missing_in_lang))

    # print("\n\nExamples of missing strings:")
    # print("\nExample missing strings in lang: ", list(missing_in_lang)[:60])
    # print("\nExample missing strings in mod: ", list(missing_in_mod)[:10])

    # select only the OBJECT strings
    missing_in_lang_objects = [s for s in missing_in_lang if s.startswith("OBJECT:")]
    print("Missing OBJECT strings in lang:", len(missing_in_lang_objects))
    print("\nExample missing OBJECT strings in lang: ", missing_in_lang_objects[:80])
