"""Update InvisibilityUpdate behavior periods in a mod's INI files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

BEHAVIOR_PATTERN = re.compile(
    r"^[ \x09]*Behavior[ \x09]*=[ \x09]*InvisibilityUpdate" r"(?:[ \x09]+[^;]*)?[ \x09]*(?:;.*)?$",
    re.IGNORECASE,
)
UPDATE_PERIOD_PATTERN = re.compile(
    r"^(?P<prefix>[ \x09]*UpdatePeriod[ \x09]*=[ \x09]*)" r"(?P<value>\d+)" r"(?P<suffix>[ \x09]*(?:;.*)?)$",
    re.IGNORECASE,
)


def update_invisibility_period(content: str, new_period: int = 5000) -> tuple[str, int]:
    """Replace UpdatePeriod only inside InvisibilityUpdate behavior blocks."""
    lines = content.splitlines(keepends=True)
    in_invisibility_behavior = False
    replacements = 0
    updated_lines: list[str] = []

    for line in lines:
        line_without_newline = line.rstrip("\r\n")

        if BEHAVIOR_PATTERN.fullmatch(line_without_newline):
            in_invisibility_behavior = True
        elif re.match(r"^[ \x09]*Behavior[ \x09]*=", line_without_newline, re.IGNORECASE):
            in_invisibility_behavior = False

        if in_invisibility_behavior:
            match = UPDATE_PERIOD_PATTERN.fullmatch(line_without_newline)
            if match and match.group("value") != str(new_period):
                newline = line[len(line_without_newline) :]
                line = f"{match.group('prefix')}{new_period}{match.group('suffix')}{newline}"
                replacements += 1

        updated_lines.append(line)

    return "".join(updated_lines), replacements


def update_mod_files(mod_directory: Path, write_changes: bool) -> int:
    """Scan all INI files below mod_directory and optionally write changes."""
    changed_files = 0

    for file_path in sorted(mod_directory.rglob("*.ini")):
        if not file_path.is_file():
            continue

        try:
            original = file_path.read_text(encoding="utf-8", errors="surrogateescape")
            updated, replacements = update_invisibility_period(original)
        except OSError as error:
            print(f"Errore durante la lettura di {file_path}: {error}")
            continue

        if not replacements:
            continue

        changed_files += 1
        action = "Modificato" if write_changes else "Da modificare"
        print(f"{action}: {file_path} ({replacements} occorrenze)")

        if write_changes:
            try:
                file_path.write_text(updated, encoding="utf-8", errors="surrogateescape")
            except OSError as error:
                print(f"Errore durante la scrittura di {file_path}: {error}")

    return changed_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Imposta UpdatePeriod a 5000 nei blocchi InvisibilityUpdate.")
    parser.add_argument("mod_directory", type=Path, help="Cartella principale della mod da analizzare")
    parser.add_argument("--write", action="store_true", help="Applica le sostituzioni; senza questa opzione esegue solo una simulazione")
    args = parser.parse_args()

    if not args.mod_directory.is_dir():
        parser.error(f"La cartella non esiste: {args.mod_directory}")

    changed_files = update_mod_files(args.mod_directory, write_changes=args.write)
    mode = "modificati" if args.write else "da modificare"
    print(f"Completato: {changed_files} file {mode}.")


if __name__ == "__main__":
    main()
