"""Friendly label lookup/edit for the Outfit panel.

Outfit color variant names are nested per-outfit (outfit_colors[outfit][color])
since the same color index means a different name depending on which outfit
is equipped. Weapon skin colors are a flat list, independent of outfit.

Real names given directly by the user (2026-08-17), baked in as constants
here (same pattern as save_loader.py's DEFAULT_NAMES for checkpoints) rather
than shipped as a loose JSON file -- a fresh download needs zero data files
to already show correct labels, and it sidesteps the frozen-exe path trap a
plain `Path(__file__).resolve().parent` would hit (PyInstaller --onefile
extracts to a temp folder that's wiped after every run). User renames still
persist, just as a small overrides file next to the real exe/script."""
from __future__ import annotations

import json

import tool_config

DEFAULT_OUTFITS: dict[int, str] = {
    0: "Hourglass Jacket",
    1: "Cloud Walker",
    2: "Fairytale Knight",
    3: "Temporal Anomaly",
    4: "Desperate",
    5: "Precursor of the Sands",
}

DEFAULT_OUTFIT_COLORS: dict[int, dict[int, str]] = {
    0: {0: "Default", 1: "World Hopper", 2: "Ruby Ghost", 3: "Chess", 4: "Sakura", 5: "Urban"},
    1: {0: "Default", 1: "Lightning Bolt", 2: "Red Moon", 3: "Night", 4: "Spark", 5: "Violet Storm"},
    2: {0: "Default", 1: "Chosen", 2: "Legend", 3: "Fallen", 4: "Champion", 5: "Hero of Time"},
    3: {0: "Default", 1: "Crimson", 2: "Sky Blue", 3: "Sunrise", 4: "Troupe", 5: "Sand"},
    4: {0: "Default", 1: "Corrupted", 2: "Golden", 3: "Negative", 4: "Fog", 5: "Darkness"},
    5: {0: "Default", 1: "Nomad", 2: "Scavenger", 3: "Echo", 4: "Omen", 5: "Specter"},
}

DEFAULT_WEAPON_COLORS: dict[int, str] = {
    0: "Minutero (default)",
    1: "Shared Memories",
    2: "Scarlet Minute",
    3: "Corrupted Flux",
    4: "Star of Damascus",
    5: "Molten Time",
    6: "Jade",
    7: "Cosmos",
    8: "Profound Wisdom",
    9: "Starstone",
    10: "Chrome",
}

OVERRIDES_PATH = tool_config.HERE / "cosmetic_name_overrides.json"


def _load_overrides() -> dict:
    try:
        return json.loads(OVERRIDES_PATH.read_text())
    except Exception:
        return {}


def _save_overrides(overrides: dict) -> None:
    tool_config.write_hidden_text(OVERRIDES_PATH, json.dumps(overrides, indent=2))


def outfit_label(index: int) -> str:
    overrides = _load_overrides().get("outfits", {})
    return overrides.get(str(index)) or DEFAULT_OUTFITS.get(index, f"Outfit {index}")


def outfit_color_label(outfit_index: int, color_index: int) -> str:
    overrides = _load_overrides().get("outfit_colors", {}).get(str(outfit_index), {})
    if str(color_index) in overrides:
        return overrides[str(color_index)]
    return DEFAULT_OUTFIT_COLORS.get(outfit_index, {}).get(color_index, f"Color {color_index}")


def weapon_color_label(index: int) -> str:
    overrides = _load_overrides().get("weapon_colors", {})
    return overrides.get(str(index)) or DEFAULT_WEAPON_COLORS.get(index, f"Weapon Color {index}")


def rename_outfit(index: int, new_label: str) -> None:
    overrides = _load_overrides()
    overrides.setdefault("outfits", {})[str(index)] = new_label
    _save_overrides(overrides)


def rename_outfit_color(outfit_index: int, color_index: int, new_label: str) -> None:
    overrides = _load_overrides()
    overrides.setdefault("outfit_colors", {}).setdefault(str(outfit_index), {})[str(color_index)] = new_label
    _save_overrides(overrides)


def rename_weapon_color(index: int, new_label: str) -> None:
    overrides = _load_overrides()
    overrides.setdefault("weapon_colors", {})[str(index)] = new_label
    _save_overrides(overrides)


def outfit_count() -> int:
    return len(DEFAULT_OUTFITS)


def outfit_color_count(outfit_index: int) -> int:
    return len(DEFAULT_OUTFIT_COLORS.get(outfit_index, DEFAULT_OUTFIT_COLORS[0]))


def weapon_color_count() -> int:
    return len(DEFAULT_WEAPON_COLORS)
