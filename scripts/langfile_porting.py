import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def ini_to_str(ini_path1, ini_path2, str_path):
    # Helper function to process an .ini file
    def process_ini_file(ini_path):
        with open(ini_path, encoding="ansi") as ini_file:
            lines = ini_file.readlines()

        # Extract only the [Table] section
        in_table_section = False
        table_lines = []
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith("["):  # Detect section headers
                in_table_section = stripped_line.lower() == "[table]"
            elif in_table_section:
                table_lines.append(line.rstrip("\n"))

        # Merge multi-line values into a single line
        merged_lines = []
        for line in table_lines:
            if line.startswith("|") and merged_lines:
                merged_lines[-1] = merged_lines[-1].rstrip() + " " + line.lstrip()
            else:
                merged_lines.append(line)

        # Filter out invalid lines before parsing
        valid_lines = []
        unwritten_lines = []  # Store unwritten lines
        for line in merged_lines:
            if "=" in line or ":" in line:  # Check for valid key-value pair
                line = line.replace("|", "\\n")  # Replace '|' with '\n' for consistency
                valid_lines.append(line)
            else:
                unwritten_lines.append(line)  # Collect invalid lines

        return valid_lines, unwritten_lines

    # Process the first .ini file
    valid_lines1, unwritten_lines1 = process_ini_file(ini_path1)

    # Process the second .ini file
    valid_lines2, unwritten_lines2 = process_ini_file(ini_path2)

    # Use a set to track already written lines
    written_lines_set = set()

    # Write the entries to the .str file
    written_lines_count = 0
    with open(str_path, "w", encoding="ansi") as str_file:
        # Write lines from the first file
        for line in valid_lines1:
            if ":" in line and "=" in line:
                tag, rest = line.split(":", 1)
                name, body = rest.split("=", 1)
                tag, name, body = tag.strip(), name.strip(), body.strip()
                entry = f'{tag}:{name}\n"{body}"\nEND\r\n'
                if entry not in written_lines_set:
                    str_file.write(entry)
                    written_lines_set.add(entry)
                    written_lines_count += 1

        # Write lines from the second file only if not already written
        for line in valid_lines2:
            if ":" in line and "=" in line:
                tag, rest = line.split(":", 1)
                name, body = rest.split("=", 1)
                tag, name, body = tag.strip(), name.strip(), body.strip()
                entry = f'{tag}:{name}\n"{body}"\nEND\r\n'
                if entry not in written_lines_set:
                    str_file.write(entry)
                    written_lines_set.add(entry)
                    written_lines_count += 1

    # Log the number of lines written to the file
    logging.info(f"Number of lines written to the file: {written_lines_count}")

    # Print the unwritten lines from both files
    if unwritten_lines1 or unwritten_lines2:
        logging.debug("Unwritten lines:")
        for line in unwritten_lines1 + unwritten_lines2:
            logging.debug(line)


# Example usage
# ini_to_str(
#    r'C:\Users\giuse\Documents\GitHub\TROWMod\lang\italian.ini',
#    r'C:\Users\giuse\Downloads\test\original_italian.ini',
#    r'C:\Users\giuse\Documents\GitHub\TROWMod\lang\data\LOTR.STR'
# )
