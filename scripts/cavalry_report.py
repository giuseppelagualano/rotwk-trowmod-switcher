import csv
import os
import re
from pathlib import Path


def read_gamedata_defines(gamedata_path):
    defines = {}
    if os.path.exists(gamedata_path):
        with open(gamedata_path, encoding="ansi") as f:
            for line in f:
                if line.strip().startswith("#define"):
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        defines[parts[1]] = parts[2]
    return defines


def get_cavalry_units(base_path):
    cavalry_units = []

    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".ini"):
                file_path = Path(root) / file
                try:
                    with open(file_path, encoding="ansi") as f:
                        content = f.read()

                        cavalry_positions = [m.start() for m in re.finditer(r"AIKindOf\s*=\s*CAVALRY", content, re.IGNORECASE)]

                        for pos in cavalry_positions:
                            content_before = content[:pos]
                            object_match = re.findall(r"^Object\s+([^\s;\n]+)", content_before, re.MULTILINE)
                            if object_match:
                                unit_name = object_match[-1].strip()

                                # Extract BuildCost and BuildTime
                                cost_match = re.search(r"BuildCost\s*=\s*([A-Z0-9_]+|\d+)", content)
                                time_match = re.search(r"BuildTime\s*=\s*([A-Z0-9_]+|\d+)", content)
                                cp_match = re.search(r"CommandPoints\s*=\s*([A-Z0-9_]+|\d+)", content)

                                buildcost_define = cost_match.group(1) if cost_match else None
                                buildtime_define = time_match.group(1) if time_match else None
                                cp_define = cp_match.group(1) if cp_match else None

                                faction = Path(root).parts[-1]  # Get the parent directory name

                                cavalry_units.append(
                                    {
                                        "faction": faction,
                                        "name": unit_name,
                                        "buildcost_define": buildcost_define,
                                        "buildtime_define": buildtime_define,
                                        "commandpoints_define": cp_define,
                                        "file": str(file_path),
                                    }
                                )

                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

    return cavalry_units


def create_cavalry_report(base_path, gamedata_path, output_csv):
    defines = read_gamedata_defines(gamedata_path)
    cavalry_list = get_cavalry_units(base_path)
    cavalry_list.sort(key=lambda x: (x["faction"], x["name"]))

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Faction", "Unit Name", "BuildCost Value", "BuildTime Value", "CP", "BuildCost Define", "BuildTime Define", "File"])

        for unit in cavalry_list:
            buildcost_value = defines.get(unit["buildcost_define"], "N/A")
            buildtime_value = defines.get(unit["buildtime_define"], "N/A")
            cp_value = defines.get(unit["commandpoints_define"], "N/A")

            if unit["buildcost_define"] and unit["buildcost_define"].isdigit():
                buildcost_value = unit["buildcost_define"]
            if unit["buildtime_define"] and unit["buildtime_define"].isdigit():
                buildtime_value = unit["buildtime_define"]
            if unit["commandpoints_define"] and unit["commandpoints_define"].isdigit():
                cp_value = unit["commandpoints_define"]

            writer.writerow(
                [unit["faction"], unit["name"], buildcost_value, buildtime_value, cp_value, unit["buildcost_define"] or "N/A", unit["buildtime_define"] or "N/A", unit["file"]]
            )


def main():
    base_path = r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini\object"
    gamedata_path = r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini\gamedata.ini"
    output_csv = "cavalry_costs_report.csv"

    create_cavalry_report(base_path, gamedata_path, output_csv)
    print(f"Report generated in: {output_csv}")


if __name__ == "__main__":
    main()
