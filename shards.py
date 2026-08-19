"""
Shard (in-game currency) read/write logic, used by the "Shards" panel in
save_loader.py. Same patch-in-place-or-insert-fresh pattern as
cosmetics.py/unlocks.py -- CoinCounter is a plain IntProperty, so this is
the simplest of the three.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import gvas_lite
import tool_config

PROP_SHARDS = "CoinCounter"


def read_shards(path: Path) -> int:
    data = path.read_bytes()
    strings = gvas_lite.extract_ascii_strings(data, min_len=3)
    return gvas_lite.find_scalar(strings, data, PROP_SHARDS, "IntProperty", 4) or 0


def apply_shards(dest: Path, value: int, backup_label: str = "shards") -> int:
    """Patches CoinCounter in place if it's already on the save, inserts it
    fresh otherwise. Always backs dest up first. Returns the verified
    post-write value."""
    dest_data = bytearray(dest.read_bytes())
    strings = gvas_lite.extract_ascii_strings(bytes(dest_data), min_len=3)

    offset = gvas_lite.find_scalar_value_offset(strings, bytes(dest_data), PROP_SHARDS, "IntProperty", 4)
    if offset is not None:
        dest_data[offset : offset + 4] = int(value).to_bytes(4, "little", signed=True)
    else:
        insert_at = gvas_lite.find_top_level_terminator(bytes(dest_data))
        new_prop = gvas_lite.write_int_property(PROP_SHARDS, value)
        dest_data = dest_data[:insert_at] + bytearray(new_prop) + dest_data[insert_at:]

    cfg = tool_config.load_config()
    backup_dir = Path(cfg["backups_dir"]) / dest.stem
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    shutil.copy2(dest, backup_dir / f"{stamp}_before_{backup_label}.sav")

    dest.write_bytes(bytes(dest_data))
    return read_shards(dest)
