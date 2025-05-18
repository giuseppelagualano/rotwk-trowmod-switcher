import os
import re
from pathlib import Path


def get_object_name(content):
    match = re.search(r"^Object\s+([^\s;\n]+)", content, re.MULTILINE)
    return match.group(1).strip() if match else None


def write_to_gamedata(defines, gamedata_path):
    existing_defines = set()

    if os.path.exists(gamedata_path):
        with open(gamedata_path, encoding="ansi") as f:
            for line in f:
                if "#define" in line:
                    define_name = line.split()[1] if len(line.split()) > 1 else ""
                    existing_defines.add(define_name)

    with open(gamedata_path, "a", encoding="ansi") as f:
        for define_name, value in defines.items():
            if define_name not in existing_defines:
                f.write(f"#define {define_name}\t\t\t\t{value}\n")


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


def find_build_patterns(base_path, gamedata_path):
    numeric_builds = []
    numeric_buildtime = []
    build_defines = {}
    mismatched_prefixes = []
    skipped_childobject = []
    factions = ["evilfaction", "goodfaction"]
    gamedata_defines = read_gamedata_defines(gamedata_path)

    for faction in factions:
        faction_path = Path(base_path) / faction / "units"
        if not faction_path.exists():
            continue
        for root, _, files in os.walk(faction_path):
            for file in files:
                if file.endswith(".ini"):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, encoding="ansi") as f:
                            content = f.read()
                            respawnrules_count = len(re.findall(r"^\s*RespawnRules", content, re.MULTILINE))
                            childobject_count = len(re.findall(r"^\s*ChildObject\s+", content, re.MULTILINE))
                            hero_type = re.search(r"KindOf\s*=.*HERO", content, re.IGNORECASE)
                            if respawnrules_count == 0 or not hero_type:
                                continue
                            if childobject_count >= 1 and respawnrules_count > 1:
                                rel_path = os.path.relpath(file_path, base_path)
                                skipped_childobject.append(rel_path)
                                continue
                            rel_path = os.path.relpath(file_path, base_path)
                            object_name = get_object_name(content)
                            if object_name:
                                modified = False
                                # Check BuildCost
                                buildcost_match = re.search(r"BuildCost\s*=\s*(\d+)", content)
                                if buildcost_match:
                                    numeric_value = buildcost_match.group(1)
                                    define_name = f"{object_name.upper()}_BUILDCOST"
                                    build_defines[define_name] = numeric_value
                                    content = re.sub(r"(BuildCost\s*=\s*)\d+", f"\\1{define_name}", content)
                                    modified = True
                                    numeric_builds.append((rel_path, "BuildCost"))
                                # Check BuildTime
                                buildtime_match = re.search(r"BuildTime\s*=\s*(\d+)", content)
                                if buildtime_match:
                                    numeric_value = buildtime_match.group(1)
                                    define_name = f"{object_name.upper()}_BUILDTIME"
                                    build_defines[define_name] = numeric_value
                                    content = re.sub(r"(BuildTime\s*=\s*)\d+", f"\\1{define_name}", content)
                                    modified = True
                                    numeric_builds.append((rel_path, "BuildTime"))
                                    numeric_buildtime.append(rel_path)
                                else:
                                    # Check for string BuildTime (ignored for counting)
                                    pass
                                # Check for mismatched prefixes
                                buildcost_define = re.search(r"BuildCost\s*=\s*([A-Z_]+)", content)
                                buildtime_define = re.search(r"BuildTime\s*=\s*([A-Z_]+)", content)
                                if buildcost_define and buildtime_define:
                                    cost_prefix = buildcost_define.group(1).rsplit("_", 1)[0]
                                    time_prefix = buildtime_define.group(1).rsplit("_", 1)[0]
                                    if cost_prefix != time_prefix:
                                        mismatched_prefixes.append(rel_path)
                                        # Fix mismatch
                                        # Determine which one is wrong (prefer to fix BuildTime)
                                        correct_prefix = buildcost_define.group(1).rsplit("_", 1)[0]
                                        wrong_define = buildtime_define.group(1)
                                        # Get value from gamedata
                                        value = gamedata_defines.get(wrong_define)
                                        if value:
                                            # Create new define with correct prefix
                                            new_define = f"{correct_prefix}_BUILDTIME"
                                            build_defines[new_define] = value
                                            # Replace in content
                                            content = re.sub(r"(BuildTime\s*=\s*)[A-Z_]+", f"\\1{new_define}", content)
                                            modified = True
                                if modified:
                                    with open(file_path, "w", encoding="ansi") as f:
                                        f.write(content)
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
    return numeric_builds, numeric_buildtime, build_defines, mismatched_prefixes, skipped_childobject


def main():
    base_path = r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini\object"
    gamedata_path = r"C:\Users\giuse\Documents\GitHub\TROWMod\data\ini\gamedata.ini"
    numeric_builds, numeric_buildtime, build_defines, mismatched_prefixes, skipped_childobject = find_build_patterns(base_path, gamedata_path)
    write_to_gamedata(build_defines, gamedata_path)
    print(f"\nProcessed {len(numeric_builds)} files with numeric Build values (with RespawnRules):")
    for file, build_type in numeric_builds:
        print(f"- {file} ({build_type})")
    print(f"\nFound {len(numeric_buildtime)} files with numeric BuildTime values (with RespawnRules):")
    for file in numeric_buildtime:
        print(f"- {file}")
    print(f"\nFound {len(mismatched_prefixes)} files with mismatched BuildCost/BuildTime prefixes (with RespawnRules):")
    for file in mismatched_prefixes:
        print(f"- {file}")
    print(f"\nAdded {len(build_defines)} new defines to gamedata.ini")
    print(f"\nSkipped {len(skipped_childobject)} files with at least one ChildObject and more than one RespawnRules:")
    for file in skipped_childobject:
        print(f"- {file}")


if __name__ == "__main__":
    main()
