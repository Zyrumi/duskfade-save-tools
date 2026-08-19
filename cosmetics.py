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

import shutil
from datetime import datetime
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
    fresh otherwise. Always backs dest up first. Returns the verified
    post-write values for all three properties."""
    values = {k: v for k, v in values.items() if k in COSMETIC_PROPS and v is not None}
    if not values:
        return read_cosmetic_values(dest)

    dest_data = bytearray(dest.read_bytes())
    strings = gvas_lite.extract_ascii_strings(bytes(dest_data), min_len=3)

    to_insert = {}
    for name, value in values.items():
        offset = gvas_lite.find_scalar_value_offset(strings, bytes(dest_data), name, "IntProperty", 4)
        if offset is not None:
            dest_data[offset : offset + 4] = int(value).to_bytes(4, "little", signed=True)
        else:
            to_insert[name] = value

    if to_insert:
        insert_at = gvas_lite.find_top_level_terminator(bytes(dest_data))
        new_props = b"".join(gvas_lite.write_int_property(n, v) for n, v in to_insert.items())
        dest_data = dest_data[:insert_at] + bytearray(new_props) + dest_data[insert_at:]

    cfg = tool_config.load_config()
    backup_dir = Path(cfg["backups_dir"]) / dest.stem
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    shutil.copy2(dest, backup_dir / f"{stamp}_before_{backup_label}.sav")

    dest.write_bytes(bytes(dest_data))
    return read_cosmetic_values(dest)
