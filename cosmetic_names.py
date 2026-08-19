"""Friendly label lookup for the Outfit panel.

Outfit color variant names are nested per-outfit (outfit_colors[outfit][color])
since the same color index means a different name depending on which outfit
is equipped. Weapon skin colors are a flat list, independent of outfit.

Real names given directly by the user (2026-08-17), baked in as constants --
these are the game's own names, not placeholders, so there's nothing to
rename."""
from __future__ import annotations

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


def outfit_label(index: int) -> str:
    return DEFAULT_OUTFITS.get(index, f"Outfit {index}")


def outfit_color_label(outfit_index: int, color_index: int) -> str:
    return DEFAULT_OUTFIT_COLORS.get(outfit_index, {}).get(color_index, f"Color {color_index}")


def weapon_color_label(index: int) -> str:
    return DEFAULT_WEAPON_COLORS.get(index, f"Weapon Color {index}")


def outfit_count() -> int:
    return len(DEFAULT_OUTFITS)


def outfit_color_count(outfit_index: int) -> int:
    return len(DEFAULT_OUTFIT_COLORS.get(outfit_index, DEFAULT_OUTFIT_COLORS[0]))


def weapon_color_count() -> int:
    return len(DEFAULT_WEAPON_COLORS)
