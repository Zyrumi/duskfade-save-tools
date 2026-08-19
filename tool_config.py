"""Shared config for auto_save_copier.py and save_loader.py so both tools
always agree on where the live saves, library, and backups live."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Running as a PyInstaller --onefile exe: __file__ would resolve to a
    # temporary extraction folder that's wiped after every run. The exe's
    # own path is the only stable location to keep config/library/backups
    # next to.
    HERE = Path(sys.executable).resolve().parent
else:
    HERE = Path(__file__).resolve().parent

CONFIG_PATH = HERE / "config.json"

_LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))

DEFAULT_CONFIG = {
    "save_dir": str(_LOCAL_APPDATA / "Duskfade" / "Saved" / "SaveGames"),
    "slot_pattern": "DFSlot_*.sav",
    "library_dir": str(HERE / "Library"),
    "backups_dir": str(HERE / "Backups"),
    "poll_seconds": 2,
    "last_target_slot": None,
    "pinned_target_slot": None,
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            on_disk = json.loads(CONFIG_PATH.read_text())
        except Exception:
            on_disk = {}
    else:
        on_disk = {}
    merged = {**DEFAULT_CONFIG, **on_disk}
    if merged != on_disk:
        save_config(merged)
    return merged


_FILE_ATTRIBUTE_HIDDEN = 0x2
_FILE_ATTRIBUTE_NORMAL = 0x80


def set_hidden(path: Path) -> None:
    """Windows-only: mark a file hidden so internal state/settings files
    don't clutter a folder someone's just browsing in Explorer. Best
    effort -- silently does nothing if this isn't Windows or it fails."""
    try:
        import ctypes

        ctypes.windll.kernel32.SetFileAttributesW(str(path), _FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        pass


def write_hidden_text(path: Path, text: str) -> None:
    """write_text, but safe to call repeatedly on a file that's already
    hidden. A plain write_text() on an existing hidden file raises
    PermissionError on Windows -- CreateFile's default flags can't
    overwrite a file that already carries FILE_ATTRIBUTE_HIDDEN. Clearing
    the attribute first (then re-hiding after) avoids that; confirmed this
    is genuinely required, not just theoretical -- the old write-then-hide
    version of this pattern (still what set_hidden's callers did before)
    left config.json/library_names.json only writable exactly once per
    file, silently raising on every save after the first."""
    try:
        import ctypes

        ctypes.windll.kernel32.SetFileAttributesW(str(path), _FILE_ATTRIBUTE_NORMAL)
    except Exception:
        pass
    path.write_text(text)
    set_hidden(path)


def save_config(cfg: dict) -> None:
    write_hidden_text(CONFIG_PATH, json.dumps(cfg, indent=2))


def captures_dir(cfg: dict) -> Path:
    """Where checkpoint folders live -- Library\\<zone>\\<timestamp>.sav
    directly, no slot- or source-specific subfolders. A capture's origin
    slot doesn't matter for practice purposes, so it's not part of the
    on-disk layout."""
    return Path(cfg["library_dir"])


def resource_path(name: str) -> Path:
    """A bundled asset (icon, seed library) -- prefers a real file sitting
    next to the exe/script (so it can be swapped without rebuilding), and
    falls back to whatever PyInstaller embedded inside the exe itself
    (sys._MEIPASS) so a bare exe downloaded on its own still has everything
    it needs, not just the zip release."""
    local = HERE / name
    if local.exists():
        return local
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / name
    return local


def ensure_seed_library(cfg: dict) -> None:
    """First run of a bare exe download: if there's no library on disk yet,
    copy out whatever PyInstaller embedded as a starter set. A no-op once a
    real library exists (never overwrites), and a no-op entirely for a dev
    checkout / an exe built without a bundled seed."""
    lib_dir = Path(cfg["library_dir"])
    if lib_dir.exists() and any(lib_dir.iterdir()):
        return
    seed = resource_path("Library")
    if seed == lib_dir or not seed.exists():
        return
    shutil.copytree(seed, lib_dir, dirs_exist_ok=True)
