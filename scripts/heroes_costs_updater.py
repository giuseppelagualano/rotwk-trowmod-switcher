import os
import re
from pathlib import Path

import pandas as pd


def read_csv_data(csv_path):
    """Read hero tiers and costs from Excel file."""

    # Read the "Simone" sheet
    df = pd.read_csv(csv_path)
    tier_df = df[["Tier", "Cost", "Time", "Points"]].dropna(how="all")
    heroes_df = df[["Hero Code Name", "HeroTier", "fell_beast_name"]].dropna(how="all")

    return tier_df, heroes_df


def update_gamedata_defines(gamedata_path, tier_df):
    """Update or add cost defines in gamedata.ini."""
    if not os.path.exists(gamedata_path):
        print(f"Warning: {gamedata_path} not found")
        return

    with open(gamedata_path, encoding="ansi") as f:
        content = f.read()

    # Create defines dictionary
    defines = {}
    for _, row in tier_df.iterrows():
        tier_num = int(row["Tier"])
        defines.update({f"TIER_{tier_num}_HERO_BUILDCOST": int(row["Cost"]), f"TIER_{tier_num}_HERO_BUILDTIME": int(row["Time"]), f"TIER_{tier_num}_HERO_CP": int(row["Points"])})

    # Update existing defines or prepare new ones
    defines_str = ""
    for define_name, value in defines.items():
        if f"#define {define_name}" in content:
            content = re.sub(r"#define {define_name}\s+\d+", f"#define {define_name} {value}", content)
        else:
            defines_str += f"#define {define_name} {value}\n"

    # Add new defines if any
    if defines_str:
        break_header = ";------------------------BALANCE DATA---------------------------- "
        new_header = ";------------------------HERO COST DEFINES---------------------------- "
        parts = content.split(break_header)

        if len(parts) == 2:
            content = parts[0] + new_header + "\n" + defines_str + "\n" + break_header + parts[1]
        else:
            print("Warning: Could not find expected header in gamedata.ini")
            exit(1)

    with open(gamedata_path, "w", encoding="ansi") as f:
        f.write(content)


def update_hero_files(base_path, fell_beast_path, heroes_df, tier_df):
    """Update hero files with tier-based define references."""
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".ini"):
                file_path = Path(root) / file
                try:
                    with open(file_path, encoding="ansi") as f:
                        content = f.read()

                    # Check if this is a hero file
                    if not re.search(r"KindOf\s*=.*HERO", content, re.IGNORECASE):
                        continue

                    # Get object name
                    object_name = re.search(r"^Object\s+([^\s;\n]+)", content, re.MULTILINE)
                    if not object_name:
                        continue

                    object_name = object_name.group(1).strip()

                    # Find hero in dataframe
                    hero_row = heroes_df[heroes_df["Hero Code Name"] == object_name]
                    if not hero_row.empty:
                        tier = int(hero_row["HeroTier"].iloc[0])
                        tier_row = tier_df[tier_df["Tier"] == tier].iloc[0]

                        # Get tier values
                        cost = int(tier_row["Cost"])
                        time = int(tier_row["Time"])

                        # Calculate respawn values (75% rounded down to nearest 100)
                        respawn_cost = str((cost * 75 // 100) // 100 * 100)
                        respawn_time = str(((time * 1000) * 75 // 100) // 100 * 100)

                        # Use tier-based defines
                        cost_define = f"TIER_{tier}_HERO_BUILDCOST"
                        time_define = f"TIER_{tier}_HERO_BUILDTIME"
                        cp_define = f"TIER_{tier}_HERO_CP"

                        # Update the values
                        content = re.sub(r"(BuildCost\s*=\s*)[^\s\n]+", f"\\1{cost_define}", content)
                        content = re.sub(r"(BuildTime\s*=\s*)[^\s\n]+", f"\\1{time_define}", content)
                        content = re.sub(r"(CommandPoints\s*=\s*)[^\s\n]+", f"\\1{cp_define}", content)

                        # Update RespawnRules if present
                        respawn_pattern = r"(RespawnRules\s*=\s*AutoSpawn:No\s*Cost:)\d+(\s*Time:)\d+"
                        if re.search(respawn_pattern, content):
                            content = re.sub(respawn_pattern, f"\\g<1>{respawn_cost}\\g<2>{respawn_time}", content)

                        # Write updated content
                        with open(file_path, "w", encoding="ansi") as f:
                            f.write(content)
                        print(f"Updated {file_path}")

                        # Handle fell beast updates if applicable
                        try:
                            fell_beast_name = hero_row["fell_beast_name"].iloc[0]
                            if pd.notna(fell_beast_name):
                                with open(fell_beast_path, encoding="ansi") as f:
                                    fell_beast_content = f.read()

                                # Find the section for this fell beast
                                fell_beast_section = re.search(f"ChildObject\\s+{fell_beast_name}[\\s\\S]*?(?=\\s*(?:ChildObject|$))", fell_beast_content)
                                if fell_beast_section:
                                    updated_section = fell_beast_section.group(0)
                                    updated_section = re.sub(r"(BuildCost\s*=\s*)[^\s\n]+", f"\\1{cost_define}", updated_section)
                                    updated_section = re.sub(r"(BuildTime\s*=\s*)[^\s\n]+", f"\\1{time_define}", updated_section)
                                    updated_section = re.sub(r"(CommandPoints\s*=\s*)[^\s\n]+", f"\\1{cp_define}", updated_section)

                                    # Update RespawnRules if present
                                    respawn_pattern = r"(RespawnRules\s*=\s*AutoSpawn:No\s*Cost:)\d+(\s*Time:)\d+"
                                    if re.search(respawn_pattern, updated_section):
                                        updated_section = re.sub(respawn_pattern, f"\\g<1>{respawn_cost}\\g<2>{respawn_time}", updated_section)

                                    # Update the fell beast file
                                    fell_beast_content = fell_beast_content.replace(fell_beast_section.group(0), updated_section)
                                    with open(fell_beast_path, "w", encoding="ansi") as f:
                                        f.write(fell_beast_content)
                                    print(f"Updated fell beast {fell_beast_name} in {fell_beast_path}")
                        except KeyError:
                            print(f"No fell beast name found for {object_name}, skipping fell beast update.")
                            exit(1)
                        except FileNotFoundError:
                            print(f"Fell beast file not found: {fell_beast_path}, skipping fell beast update.")
                            exit(1)
                        except Exception as e:
                            print(f"Error updating fell beast {fell_beast_name}: {e}")
                            exit(1)

                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    exit(1)


def main():
    # Configuration paths
    csv_path = r"C:\Users\giuse\Downloads\BFMEhero.csv"
    base_path = r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini\object"
    gamedata_path = r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini\gamedata.ini"
    fell_beast_path = r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini\object\evilfaction\units\mordor\fellbeast.ini"

    # Read hero data from CSV
    tier_df, heroes_df = read_csv_data(csv_path)

    update_gamedata_defines(gamedata_path, tier_df)
    update_hero_files(base_path, fell_beast_path, heroes_df, tier_df)

    print("Hero costs update completed!")


if __name__ == "__main__":
    main()
