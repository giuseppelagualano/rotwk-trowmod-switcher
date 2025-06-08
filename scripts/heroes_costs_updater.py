import os
import re
from pathlib import Path

import pandas as pd


def read_xlsx_data(xlsx_path):
    """Read hero tiers and costs from Excel file."""

    # Read the "Simone" sheet
    df = pd.read_excel(xlsx_path, sheet_name="Simone")
    tier_df = df[["Tier", "Cost", "Time", "Points"]].dropna()
    heroes_df = df[["Hero Code Name", "HeroTier"]].dropna()

    return tier_df, heroes_df


def update_gamedata_defines(gamedata_path, tier_df):
    """Update or add cost defines in gamedata.ini."""
    if not os.path.exists(gamedata_path):
        print(f"Warning: {gamedata_path} not found")
        return

    with open(gamedata_path, encoding="ansi") as f:
        content = f.read()

    # Create tier defines and update/add them
    for _, row in tier_df.iterrows():
        tier_num = int(row["Tier"])
        defines = {f"TIER_{tier_num}_HERO_BUILDCOST": int(row["Cost"]), f"TIER_{tier_num}_HERO_BUILDTIME": int(row["Time"]), f"TIER_{tier_num}_HERO_CP": int(row["Points"])}

        for define_name, value in defines.items():
            pattern = rf"#define\s+{define_name}\s+\d+"
            replacement = f"#define {define_name} {value}"

            if re.search(pattern, content):
                # Replace existing define
                content = re.sub(pattern, replacement, content)
            else:
                # Add new define at the end
                content += f"\n{replacement}"

    # Write updated content back to file

    with open(gamedata_path, "w", encoding="ansi") as f:
        f.write(content)


def update_hero_files(base_path, heroes_df, tier_df):
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

                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    exit(1)


def main():
    # Configuration paths
    xlsx_path = r"C:\Users\giuse\Downloads\BFMEhero.xlsx"
    base_path = r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini\object"
    gamedata_path = r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini\gamedata.ini"

    # Read hero data from CSV
    tier_df, heroes_df = read_xlsx_data(xlsx_path)

    update_gamedata_defines(gamedata_path, tier_df)
    update_hero_files(base_path, heroes_df, tier_df)

    print("Hero costs update completed!")


if __name__ == "__main__":
    main()
