"""
Shared cosmetic-property read/write logic, used by the "Outfit..." panel in
save_loader.py.

IndexSkin = equipped outfit (0 = default, 1-5 = the five unlockable ones).
IndexRecolor = outfit color variant. IndexRecolorEspada = sword skin color
variant. Confirmed working in-game as of 2026-08-17 -- the Tutorial zone
specifically overrides appearance back to default regardless of these
values (by design, not a bug in this), but everywhere else respects them,
picked up on an in-game retry (no full reload needed).
"""
from __future__ import annotations

from pathlib import Path

import gvas_lite
import tool_config

COSMETIC_PROPS = ["IndexSkin", "IndexRecolor", "IndexRecolorEspada"]


def read_cosmetic_values(path: Path) -> dict:
    data = path.read_bytes()
    strings = gvas_lite.extract_ascii_strings(data, min_len=3)
    return {name: gvas_lite.find_scalar(strings, data, name, "IntProperty", 4) for name in COSMETIC_PROPS}


def apply_cosmetic_values(dest: Path, values: dict, backup_label: str = "cosmetics") -> dict:
    """values: any subset of COSMETIC_PROPS -> int (None entries ignored).
    Patches each property in place if it already exists in dest, inserts it
    fresh otherwise. Always backs dest up first and writes atomically.
    Returns the verified post-write values for all three properties."""
    values = {k: v for k, v in values.items() if k in COSMETIC_PROPS and v is not None}
    if not values:
        return read_cosmetic_values(dest)

    dest_data = bytearray(dest.read_bytes())
    dest_data = gvas_lite.patch_or_insert_int_properties(dest_data, values)

    tool_config.backup_active_save(dest, backup_label)
    tool_config.atomic_write_bytes(dest, bytes(dest_data))
    return read_cosmetic_values(dest)
