"""Shared config for auto_save_copier.py and save_loader.py so both tools
always agree on where the live saves, library, and backups live."""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
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
    # How many backups each slot keeps (newest kept, oldest pruned) so
    # Backups\ doesn't grow forever over a long session. 0 or less disables
    # pruning entirely (unlimited retention) -- an explicit opt-in escape
    # hatch, not the default.
    "backup_retention_count": 30,
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


def parse_timestamp(stem: str) -> datetime | None:
    """Parses this project's one timestamp format (used for both Library
    capture filenames and Backups filenames), or None if stem isn't that
    shape -- shared so every caller falls back the same way instead of each
    re-implementing its own strptime/except."""
    try:
        return datetime.strptime(stem, "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        return None


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Writes data to path without ever leaving it half-written: writes to a
    temp file in the same directory first, then atomically replaces the
    target (os.replace is atomic on both Windows and POSIX for a same-
    volume rename). A crash or interrupted write mid-operation leaves
    either the untouched old file or the fully-written new one -- never a
    truncated mix of both. Every writer of a live save file (loading a
    library save, restoring a backup, or patching unlocks/outfit/shards)
    goes through this."""
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def atomic_copy(src: Path, dest: Path) -> None:
    atomic_write_bytes(dest, src.read_bytes())


def _backup_sort_key(path: Path) -> datetime:
    # The filename's own timestamp reflects when the backup was actually
    # made (datetime.now() at copy time) -- NOT the file's mtime, which
    # shutil.copy2 carries over from the source save's own last-write time
    # (e.g. an old checkpoint backed up just now still has an old mtime).
    # Sorting by mtime would prune the wrong ones.
    ts_part = path.stem.split("_before_", 1)[0]
    return parse_timestamp(ts_part) or datetime.fromtimestamp(path.stat().st_mtime)


def prune_backups(backup_dir: Path, keep: int) -> None:
    """Deletes the oldest backups in backup_dir beyond the newest `keep`.
    keep <= 0 means unlimited retention -- a no-op."""
    if keep <= 0:
        return
    saves = sorted(backup_dir.glob("*.sav"), key=_backup_sort_key, reverse=True)
    for stale in saves[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass


def prune_all_backups(cfg: dict) -> None:
    """Prunes every slot's backup folder to the configured retention count
    -- run at startup so a folder that grew large under an older build (or
    after lowering backup_retention_count by hand) gets trimmed immediately,
    not just on the next edit."""
    backups_root = Path(cfg["backups_dir"])
    if not backups_root.exists():
        return
    keep = cfg.get("backup_retention_count", DEFAULT_CONFIG["backup_retention_count"])
    for slot_dir in backups_root.iterdir():
        if slot_dir.is_dir():
            prune_backups(slot_dir, keep)


def backup_active_save(dest: Path, label: str, cfg: dict | None = None) -> Path:
    """Copies dest into Backups\\<slot_stem>\\<timestamp>_before_<label>.sav
    before any in-place edit, then prunes that slot's backups down to
    backup_retention_count."""
    if cfg is None:
        cfg = load_config()
    backup_dir = Path(cfg["backups_dir"]) / dest.stem
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = backup_dir / f"{stamp}_before_{label}.sav"
    if dest.exists():
        shutil.copy2(dest, backup_path)
    prune_backups(backup_dir, cfg.get("backup_retention_count", DEFAULT_CONFIG["backup_retention_count"]))
    return backup_path


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
