import logging
from collections import defaultdict


def check_duplicate_keys_in_str_file(str_path: str) -> bool:
    """
    Checks for duplicate keys in a .str file.
    Logs an error if duplicates are found and returns False.
    """

    # Dictionary to store occurrences of each key
    key_occurrences = defaultdict(list)

    try:
        with open(str_path, encoding="ansi") as str_file:
            lines = str_file.readlines()

        current_key = None
        duplicates_found = False
        for line_number, line in enumerate(lines, start=1):
            stripped_line = line.strip()
            if ":" in stripped_line and not stripped_line.startswith('"') and not stripped_line.startswith("END"):
                # Extract the key (tag:name)
                current_key = stripped_line
                if current_key in key_occurrences:
                    logging.error(f"Duplicate key found: {current_key} at line {line_number}")
                    duplicates_found = True
                key_occurrences[current_key].append(line_number)

        return not duplicates_found

    except FileNotFoundError:
        logging.error(f"File not found: {str_path}")
        return False
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return False
