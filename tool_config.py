"""Shared config for auto_save_copier.py and save_loader.py so both tools
always agree on where the live saves, library, and backups live."""
from __future__ import annotations

import json
import os
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


def set_hidden(path: Path) -> None:
    """Windows-only: mark a file hidden so internal state/settings files
    don't clutter a folder someone's just browsing in Explorer. Best
    effort -- silently does nothing if this isn't Windows or it fails."""
    try:
        import ctypes

        FILE_ATTRIBUTE_HIDDEN = 0x2
        ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        pass


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    set_hidden(CONFIG_PATH)


def captures_dir(cfg: dict) -> Path:
    """Where checkpoint folders live -- Library\\<zone>\\<timestamp>.sav
    directly, no slot- or source-specific subfolders. A capture's origin
    slot doesn't matter for practice purposes, so it's not part of the
    on-disk layout."""
    return Path(cfg["library_dir"])
