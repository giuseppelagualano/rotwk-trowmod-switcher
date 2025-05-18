import csv
import os
import re
from pathlib import Path


def get_object_name(content):
    match = re.search(r"^Object\s+([^\s;\n]+)", content, re.MULTILINE)
    return match.group(1).strip() if match else None


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


def collect_hero_data(base_path):
    heroes_data = []

    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".ini"):
                file_path = Path(root) / file
                try:
                    with open(file_path, encoding="ansi") as f:
                        content = f.read()

                        respawnrules_count = len(re.findall(r"^\s*RespawnRules", content, re.MULTILINE))
                        hero_type = re.search(r"KindOf\s*=.*HERO", content, re.IGNORECASE)
                        if respawnrules_count == 0 or not hero_type:
                            continue

                        object_name = get_object_name(content)
                        if not object_name:
                            continue

                        # Extract faction from path
                        faction = Path(root).parts[-1]  # Get the parent directory name

                        # Extract BuildCost, BuildTime and CommandPoints
                        buildcost_define = None
                        buildtime_define = None
                        command_points = None

                        cost_match = re.search(r"BuildCost\s*=\s*([A-Z0-9_]+)", content)
                        time_match = re.search(r"BuildTime\s*=\s*([A-Z0-9_]+)", content)
                        points_match = re.search(r"CommandPoints\s*=\s*([A-Z0-9_]+|\d+)", content)

                        if cost_match:
                            buildcost_define = cost_match.group(1)
                        if time_match:
                            buildtime_define = time_match.group(1)
                        if points_match:
                            command_points = points_match.group(1)
                            # If command_points looks like a define (all caps with underscores)
                            if re.match(r"^[A-Z0-9_]+$", command_points) and not command_points.isdigit():
                                # The actual value will be looked up in gamedata.ini later
                                pass

                        heroes_data.append(
                            {
                                "faction": faction,
                                "name": object_name,
                                "buildcost_define": buildcost_define,
                                "buildtime_define": buildtime_define,
                                "command_points": command_points,
                                "file": str(file_path),
                            }
                        )

                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

    return heroes_data


def create_hero_report(base_path, gamedata_path, output_csv):
    # Leggi le definizioni da gamedata.ini
    defines = read_gamedata_defines(gamedata_path)

    # Raccogli i dati degli eroi
    heroes_data = collect_hero_data(base_path)

    # Ordina per fazione e nome
    heroes_data.sort(key=lambda x: (x["faction"], x["name"]))

    # Scrivi il CSV
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Faction", "Hero Name", "BuildCost Value", "BuildTime Value", "Command Points", "BuildCost Define", "BuildTime Define"])

        for hero in heroes_data:
            buildcost_value = defines.get(hero["buildcost_define"], "N/A")
            buildtime_value = defines.get(hero["buildtime_define"], "N/A")

            # Se command_points è una define, cerchiamo il valore in gamedata.ini
            if re.match(r"^[A-Z0-9_]+$", hero["command_points"] or "") and not (hero["command_points"] or "").isdigit():
                command_points = defines.get(hero["command_points"], "N/A")
            else:
                command_points = hero["command_points"] if hero["command_points"] else "N/A"

            writer.writerow(
                [
                    hero["faction"],
                    hero["name"],
                    buildcost_value,
                    buildtime_value,
                    command_points,
                    hero["buildcost_define"] or "N/A",
                    hero["buildtime_define"] or "N/A",
                ]
            )


def main():
    base_path = r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini\object"
    gamedata_path = r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini\gamedata.ini"
    output_csv = "hero_costs_report.csv"

    create_hero_report(base_path, gamedata_path, output_csv)
    print(f"Report generato in: {output_csv}")


if __name__ == "__main__":
    main()
