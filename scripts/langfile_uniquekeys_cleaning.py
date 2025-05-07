import logging
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def remove_duplicate_keys_in_str(str_path):
    # Dictionary to store occurrences of each key
    key_occurrences = defaultdict(list)

    try:
        with open(str_path, encoding="ansi") as str_file:
            lines = str_file.readlines()

        current_key = None
        cleaned_lines = []
        skip_lines = 0
        for line_number, line in enumerate(lines, start=1):
            if skip_lines > 0:
                skip_lines -= 1
                continue

            stripped_line = line.strip()
            if ":" in stripped_line and not stripped_line.startswith('"') and not stripped_line.startswith("END"):
                # Extract the key (tag:name)
                current_key = stripped_line
                if current_key in key_occurrences:
                    logging.info(f"Duplicate key removed: {current_key} at line {line_number}")
                    skip_lines = 2  # Skip the next two lines
                    continue  # Skip duplicate key
                key_occurrences[current_key].append(line_number)
            cleaned_lines.append(line)

        # Write the cleaned content back to the file
        with open(str_path, "w", encoding="ansi") as str_file:
            str_file.writelines(cleaned_lines)

        logging.info("Duplicate keys removed successfully.")

    except FileNotFoundError:
        logging.error(f"File not found: {str_path}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")


# Example usage
remove_duplicate_keys_in_str(r"C:\Users\giuse\Documents\GitHub\TROWMod\lang\data\lotr.str")
