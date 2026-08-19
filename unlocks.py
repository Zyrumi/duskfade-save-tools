"""
Shared ability/gadget/upgrade unlock-flag read/write logic, used by the
"Unlocks" panel in save_loader.py.

Duskfade tracks which abilities/gadgets are owned, and which upgrade tier
each has reached, as six fixed-size (4-slot) true/false arrays. A property
is simply absent from the save file until its first slot is unlocked (UE
only serializes values that differ from class default), so a fresh/early
save has none of these -- see gvas_lite.find_bool_array /
write_bool_array_property for the confirmed on-disk shape.

Slot names for Habilidades/Gadgets confirmed directly by the user
(2026-08-19). UpHabilidades/UpGadgets are NOT sequential tiers of one
thing -- each slot is the upgrade for one specific ability/gadget, at the
same index as (and in the same unlock order as) Habilidades/Gadgets
respectively (confirmed by the user 2026-08-19, after "Tier 1-4" labels
shipped incorrectly in v1.1.0 -- e.g. UpHabilidades slot 0 is Hook's
upgrade, not "ability upgrade tier 1"). UpMinutero/UpCuco really are
sequential tiers of a single weapon/gadget each, so those two keep
"Tier 1..4".
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import gvas_lite
import tool_config

_ABILITY_NAMES = ["Hook", "Pendulum", "Sundial", "Crunia's Wings"]
_GADGET_NAMES = ["Chronoblast", "Stopwatch", "Time Bomb", "Starfall"]

UNLOCK_GROUPS: list[tuple[str, str, list[str]]] = [
    ("Habilidades", "Abilities", _ABILITY_NAMES),
    ("Gadgets", "Gadgets", _GADGET_NAMES),
    ("UpHabilidades", "Ability Upgrades", [f"{n} Upgrade" for n in _ABILITY_NAMES]),
    ("UpGadgets", "Gadget Upgrades", [f"{n} Upgrade" for n in _GADGET_NAMES]),
    ("UpMinutero", "Minutero (Sword) Upgrades", ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]),
    ("UpCuco", "Cuco (Cuckoo) Upgrades", ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]),
]
UNLOCK_ARRAY_NAMES = [name for name, _, _ in UNLOCK_GROUPS]


def read_unlock_values(path: Path) -> dict[str, list[bool]]:
    """Missing arrays read as all-False -- that's the real default state
    (nothing unlocked yet), matching what the game itself would show."""
    data = path.read_bytes()
    strings = gvas_lite.extract_ascii_strings(data, min_len=3)
    result = {}
    for name, _, slots in UNLOCK_GROUPS:
        found = gvas_lite.find_bool_array(strings, data, name)
        result[name] = found[2] if found is not None else [False] * len(slots)
    return result


def apply_unlock_values(dest: Path, values: dict[str, list[bool]], backup_label: str = "unlocks") -> dict[str, list[bool]]:
    """values: any subset of UNLOCK_ARRAY_NAMES -> list[bool] (must match
    that array's slot count). Patches each array in place if it already
    exists in dest, inserts it fresh otherwise. Always backs dest up first.
    Returns the verified post-write values for every known array."""
    values = {k: v for k, v in values.items() if k in UNLOCK_ARRAY_NAMES}
    if not values:
        return read_unlock_values(dest)

    dest_data = bytearray(dest.read_bytes())
    strings = gvas_lite.extract_ascii_strings(bytes(dest_data), min_len=3)

    to_insert: dict[str, list[bool]] = {}
    for name, new_values in values.items():
        found = gvas_lite.find_bool_array(strings, bytes(dest_data), name)
        if found is not None:
            count, offset, _ = found
            if count == len(new_values):
                dest_data[offset : offset + count] = bytes(1 if v else 0 for v in new_values)
            # else: mismatched slot count vs. what's already on disk --
            # shouldn't happen for the known 4-slot arrays. Left untouched
            # rather than inserting a duplicate property of the same name.
        elif any(new_values):
            # Not on disk yet and still all-False is a no-op (that's already
            # the default/absent state) -- only worth inserting fresh when
            # something's actually being turned on.
            to_insert[name] = new_values

    if to_insert:
        insert_at = gvas_lite.find_top_level_terminator(bytes(dest_data))
        new_props = b"".join(gvas_lite.write_bool_array_property(n, v) for n, v in to_insert.items())
        dest_data = dest_data[:insert_at] + bytearray(new_props) + dest_data[insert_at:]

    cfg = tool_config.load_config()
    backup_dir = Path(cfg["backups_dir"]) / dest.stem
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    shutil.copy2(dest, backup_dir / f"{stamp}_before_{backup_label}.sav")

    dest.write_bytes(bytes(dest_data))
    return read_unlock_values(dest)
