"""Check the installed RotWK and 2.02 patch version on Windows.

The 2.02 patch does not expose a single documented API, so the result is
based on Windows file metadata and version strings found in the game files.
An inconclusive result is intentional: it is safer than reporting 9.0.0 from
the presence of the game executable alone.
"""

from __future__ import annotations

import argparse
import ctypes
import re
import sys
import winreg
from ctypes import wintypes
from pathlib import Path

REGISTRY_PATHS = (
    r"SOFTWARE\Wow6432Node\Electronic Arts\Electronic Arts\The Lord of the Rings, The Rise of the Witch-king",
    r"SOFTWARE\Electronic Arts\Electronic Arts\The Lord of the Rings, The Rise of the Witch-king",
)
GAME_FILES = ("lotrbfme2ep1.exe", "game.dat")
PATCH_MARKER_PATTERNS = ("*202*v9.0.0*", "*202*v9.0*")
VERSION_PATTERNS = (
    re.compile(rb"(?i)(?:2\.02|2\.0\.2)"),
    re.compile(rb"(?i)(?:9\.0\.0|v9\.0)"),
)
UNICODE_VERSION_PATTERNS = (
    re.compile(rb"2\x00\.\x000\x002\x00"),
    re.compile(rb"9\x00\.\x000\x00\.\x000\x00"),
)


class FixedFileInfo(ctypes.Structure):
    _fields_ = [
        ("signature", wintypes.DWORD),
        ("struc_version", wintypes.DWORD),
        ("file_version_ms", wintypes.DWORD),
        ("file_version_ls", wintypes.DWORD),
        ("product_version_ms", wintypes.DWORD),
        ("product_version_ls", wintypes.DWORD),
        ("file_flags_mask", wintypes.DWORD),
        ("file_flags", wintypes.DWORD),
        ("file_os", wintypes.DWORD),
        ("file_type", wintypes.DWORD),
        ("file_subtype", wintypes.DWORD),
        ("file_date_ms", wintypes.DWORD),
        ("file_date_ls", wintypes.DWORD),
    ]


def find_install_path() -> Path | None:
    """Find RotWK through both 32-bit and 64-bit registry views."""
    if sys.platform != "win32":
        return None

    access_modes = (winreg.KEY_READ, winreg.KEY_READ | winreg.KEY_WOW64_32KEY, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
    for registry_path in REGISTRY_PATHS:
        for access in access_modes:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path, 0, access) as key:
                    install_path, _ = winreg.QueryValueEx(key, "InstallPath")
                path = Path(install_path)
                if path.is_dir():
                    return path
            except (FileNotFoundError, OSError, TypeError):
                continue
    return None


def get_windows_file_version(path: Path) -> str | None:
    """Read the fixed Windows version resource without third-party packages."""
    version_dll = ctypes.windll.version
    size = version_dll.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None

    buffer = ctypes.create_string_buffer(size)
    if not version_dll.GetFileVersionInfoW(str(path), 0, size, buffer):
        return None

    value = ctypes.c_void_p()
    value_size = wintypes.UINT()
    if not version_dll.VerQueryValueW(buffer, "\\", ctypes.byref(value), ctypes.byref(value_size)):
        return None

    info = ctypes.cast(value, ctypes.POINTER(FixedFileInfo)).contents
    major = info.file_version_ms >> 16
    minor = info.file_version_ms & 0xFFFF
    build = info.file_version_ls >> 16
    revision = info.file_version_ls & 0xFFFF
    return f"{major}.{minor}.{build}.{revision}"


def find_version_strings(path: Path) -> set[str]:
    """Find ASCII/UTF-16LE version markers embedded in a PE-like file."""
    try:
        data = path.read_bytes()
    except OSError:
        return set()

    markers = set()
    for pattern, unicode_pattern, label in zip(
        VERSION_PATTERNS,
        UNICODE_VERSION_PATTERNS,
        ("2.02", "9.0.0"),
    ):
        if pattern.search(data) or unicode_pattern.search(data):
            markers.add(label)
    return markers


def find_patch_markers(install_path: Path) -> list[Path]:
    """Find patch marker files created by the AllInOneLauncher."""
    markers: list[Path] = []
    for pattern in PATCH_MARKER_PATTERNS:
        markers.extend(path for path in install_path.glob(pattern) if path.is_file())
    return sorted(set(markers))


def check_installation(install_path: Path) -> bool:
    files = {name: install_path / name for name in GAME_FILES}
    missing = [name for name, path in files.items() if not path.is_file()]
    if missing:
        print(f"ERRORE: file mancanti: {', '.join(missing)}")
        return False

    print(f"Cartella trovata: {install_path}")
    all_markers: set[str] = set()
    for name, path in files.items():
        file_version = get_windows_file_version(path)
        markers = find_version_strings(path)
        if file_version and file_version.startswith("2.0.2"):
            markers.add("2.02")
        all_markers.update(markers)
        print(f"- {name}: versione Windows={file_version or 'n/d'}; stringhe={', '.join(sorted(markers)) or 'nessuna'}")

    patch_markers = find_patch_markers(install_path)
    if patch_markers:
        for marker in patch_markers:
            print(f"- Marker AllInOneLauncher: {marker.name}")
        all_markers.update(("2.02", "9.0.0"))

    is_202 = "2.02" in all_markers
    is_900 = "9.0.0" in all_markers
    print(f"2.02: {'SI' if is_202 else 'NON CONFERMATA'}")
    print(f"Patch 9.0.0: {'SI' if is_900 else 'NON CONFERMATA'}")
    if not is_202 and not is_900:
        print("Nota: i file sono quelli di RotWK, ma non contengono un identificatore leggibile della patch.")
        print("Controllo inconclusivo: verifica la versione mostrata dal launcher 2.02 o indica il file della patch.")
    return is_900


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlla la versione 2.02/9.0.0 di RotWK.")
    parser.add_argument("path", nargs="?", type=Path, help="Cartella principale di installazione di RotWK")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("Questo controllo richiede Windows.")
        return 2

    install_path = args.path
    if install_path is None:
        entered_path = input("Inserisci il percorso della cartella di RotWK (Invio per cercarlo nel registro): ").strip()
        install_path = Path(entered_path) if entered_path else find_install_path()
    if install_path is None:
        print("Installazione RotWK non trovata nel registro di Windows.")
        return 2
    if not install_path.is_dir():
        print(f"Cartella non trovata: {install_path}")
        return 2
    return 0 if check_installation(install_path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
