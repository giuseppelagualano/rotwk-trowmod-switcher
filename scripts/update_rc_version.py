# scripts/update_rc_version.py
import re
import sys
import tomllib


def load_toml(file_path):
    with open(file_path, "rb") as f:
        return tomllib.load(f)


# --- Configuration ---
pyproject_path = "pyproject.toml"
rc_file_path = "version.rc"


def get_version_from_toml(file_path):
    try:
        data = load_toml(file_path)
        version = data.get("project", {}).get("version")
        if version:
            return version
        raise ValueError("Version not found in [project] table.")
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: '{file_path}' not found.")
    except Exception as e:
        raise RuntimeError(f"Error parsing '{file_path}': {e}")


def format_version_for_rc_tuple(version_str):
    cleaned_version = re.sub(r"[^\d.]", "", version_str.split("-")[0].split("+")[0])
    parts = cleaned_version.split(".") + ["0"] * 4
    major, minor, patch, build = map(int, parts[:4])
    return major, minor, patch, build


def format_version_for_rc_string(version_str):
    parts = version_str.split(".")
    major = parts[0] if len(parts) > 0 else "0"
    minor = parts[1] if len(parts) > 1 else "0"
    patch = parts[2] if len(parts) > 2 else "0"
    return f"{major}.{minor}.{patch}"


print(f"Attempting to update versions in '{rc_file_path}' from '{pyproject_path}'...")

try:
    # 1. Get version from pyproject.toml
    version_str = get_version_from_toml(pyproject_path)
    print(f"Found version: {version_str}")

    # 2. Format versions for RC file
    filevers_tuple = format_version_for_rc_tuple(version_str)
    prodvers_tuple = filevers_tuple
    file_version_str_rc = format_version_for_rc_string(version_str)
    prod_version_str_rc = file_version_str_rc

    # Create the exact strings needed for replacement MANUALLY
    filevers_replacement_nums = f"{filevers_tuple[0]}, {filevers_tuple[1]}, {filevers_tuple[2]}, {filevers_tuple[3]}"
    prodvers_replacement_nums = f"{prodvers_tuple[0]}, {prodvers_tuple[1]}, {prodvers_tuple[2]}, {prodvers_tuple[3]}"

    print(f"  - Replacing filevers tuple with: {filevers_replacement_nums}")
    print(f"  - Replacing prodvers tuple with: {prodvers_replacement_nums}")
    print(f"  - Replacing FileVersion string with: '{file_version_str_rc}'")
    print(f"  - Replacing ProductVersion string with: '{prod_version_str_rc}'")

    # 3. Read the existing version.rc content
    with open(rc_file_path, encoding="utf-8") as f:
        rc_content = f.read()

    # 4. Use Regex to replace version parts, passing pre-formatted strings
    rc_content_new = rc_content  # Start with original content

    # Define replacement function for tuples to avoid repeating logic
    def replace_tuple(pattern, replacement_nums, text):
        match = re.search(pattern, text)
        if match:
            # Group 1 captures the part before the numbers (e.g., "filevers = (")
            # Group 2 captures the closing parenthesis ")"
            return text[: match.start(1)] + match.group(1) + replacement_nums + match.group(2) + text[match.end(2) :]
        else:
            print(f"Warning: Pattern not found for tuple replacement: {pattern}")
            return text  # Return original text if no match

    # Define replacement function for strings
    def replace_string(pattern, replacement_str, text):
        """
        Finds a pattern and replaces the content of the second capture group
        with replacement_str, keeping the first and third capture groups.
        """
        match = re.search(pattern, text)
        if match:
            # Pattern structure assumption:
            # Group 1: The part *before* the value to replace (e.g., "StringStruct(u'FileVersion', u'")
            # Group 2: The *old value* itself (e.g., "OLD_VERSION") - We will DISCARD this.
            # Group 3: The part *after* the value (e.g., "')")
            prefix = match.group(1)
            suffix = match.group(3)
            # Reconstruct: Text before match starts + group 1 + new string + group 3 + text after match ends
            start_index = match.start()  # Start of the whole match
            end_index = match.end()  # End of the whole match
            return text[:start_index] + prefix + replacement_str + suffix + text[end_index:]
        else:
            print(f"Warning: Pattern not found for string replacement: {pattern}")
            return text  # Return original text if no match

    # Replace filevers tuple - **Using pre-built string and manual replacement logic**
    rc_content_new = replace_tuple(
        r"(filevers\s*=\s*\()\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(\))",  # Capture prefix and suffix
        filevers_replacement_nums,
        rc_content_new,
    )

    # Replace prodvers tuple - **Using pre-built string and manual replacement logic**
    rc_content_new = replace_tuple(
        r"(prodvers\s*=\s*\()\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(\))",  # Capture prefix and suffix
        prodvers_replacement_nums,
        rc_content_new,
    )

    # Replace FileVersion string - **Using pre-built string and manual replacement logic**
    rc_content_new = replace_string(
        r"(StringStruct\s*\(\s*u?'FileVersion'\s*,\s*u?')([^']*)('\))",  # Capture prefix and suffix
        file_version_str_rc,
        rc_content_new,
    )

    # Replace ProductVersion string - **Using pre-built string and manual replacement logic**
    rc_content_new = replace_string(
        r"(StringStruct\s*\(\s*u?'ProductVersion'\s*,\s*u?')([^']*)('\))",  # Capture prefix and suffix
        prod_version_str_rc,
        rc_content_new,
    )

    # 5. Write the modified content back to version.rc
    # Add a check to see if content actually changed before writing
    if rc_content_new != rc_content:
        with open(rc_file_path, "w", encoding="utf-8") as f:
            f.write(rc_content_new)
        print(f"Successfully updated '{rc_file_path}'")
    else:
        print(f"No changes made to '{rc_file_path}' (versions might already be up-to-date or patterns didn't match).")


except (FileNotFoundError, RuntimeError, ValueError, ImportError) as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"An unexpected error occurred: {e}", file=sys.stderr)
    sys.exit(1)
