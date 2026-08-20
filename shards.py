"""
Shard (in-game currency) read/write logic, used by the "Shards" panel in
save_loader.py. Same patch-in-place-or-insert-fresh pattern as
cosmetics.py/unlocks.py -- CoinCounter is a plain IntProperty, so this is
the simplest of the three.
"""
from __future__ import annotations

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
    fresh otherwise. Always backs dest up first and writes atomically.
    Returns the verified post-write value."""
    dest_data = bytearray(dest.read_bytes())
    dest_data = gvas_lite.patch_or_insert_int_properties(dest_data, {PROP_SHARDS: value})

    tool_config.backup_active_save(dest, backup_label)
    tool_config.atomic_write_bytes(dest, bytes(dest_data))
    return read_shards(dest)
