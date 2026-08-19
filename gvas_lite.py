"""
gvas_lite — minimal, dependency-free reader for Duskfade's GVAS .sav files.

This is a direct Python port of the byte-scanning approach validated in the
Ticktown Ledger tool (save-reader.html / gvas-reader.ts on the speedrun hub).
It does NOT do a full property-by-property GVAS parse (that still chokes on
the nested LevelsState map). Instead it linearly scans the raw bytes for
printable-ASCII runs and pattern-matches known field names, which is what
Ticktown Ledger already proved reliable for: checkpoint/zone strings and a
handful of integer scalars (shards, gadget index, story progress).

Two confirmed Duskfade / UE5.6 quirks baked into the scalar decoder:
  1. Property tags write ArrayIndex BEFORE Length (reversed from every
     reference GVAS implementation).
  2. (Not needed here — header quirk only matters for a full header parse,
     which this module skips entirely since it scans raw bytes.)
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path

_PRINTABLE_MIN, _PRINTABLE_MAX = 0x20, 0x7E


@dataclass
class Str:
    offset: int
    text: str


def extract_ascii_strings(data: bytes, min_len: int = 4) -> list[Str]:
    results: list[Str] = []
    start = -1
    for i, b in enumerate(data):
        if _PRINTABLE_MIN <= b <= _PRINTABLE_MAX:
            if start == -1:
                start = i
        else:
            if start != -1 and i - start >= min_len:
                results.append(Str(start, data[start:i].decode("ascii")))
            start = -1
    if start != -1 and len(data) - start >= min_len:
        results.append(Str(start, data[start:].decode("ascii")))
    return results


_TYPE_TOKEN_RE = re.compile(
    r"^(StrProperty|IntProperty|BoolProperty|StructProperty|ArrayProperty|ObjectProperty|None)$"
)


def find_value_after(strings: list[Str], key: str, max_ahead: int = 6) -> str | None:
    idx = next((i for i, s in enumerate(strings) if s.text == key), None)
    if idx is None:
        return None
    for i in range(idx + 1, min(idx + 1 + max_ahead, len(strings))):
        t = strings[i].text
        if _TYPE_TOKEN_RE.match(t):
            continue
        return t
    return None


def _locate_scalar_value(
    data: bytes, name_offset: int, name_text_len: int, expected_type: str, byte_size: int
) -> int | None:
    """Validates the property tag right after a name string and, if it
    matches, returns the file offset where the raw value bytes begin."""
    try:
        pos = name_offset + name_text_len + 1  # past name's null terminator
        type_len = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        if type_len <= 0 or type_len > 200:
            return None
        type_text = data[pos : pos + type_len - 1].decode("ascii")
        pos += type_len
        if type_text != expected_type:
            return None
        array_index = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        length = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        terminator = data[pos]
        pos += 1
        if array_index != 0 or terminator != 0 or length != byte_size:
            return None
        return pos
    except Exception:
        return None


def _decode_value_at(data: bytes, pos: int, expected_type: str):
    if expected_type == "IntProperty":
        return struct.unpack_from("<i", data, pos)[0]
    if expected_type == "FloatProperty":
        return struct.unpack_from("<f", data, pos)[0]
    if expected_type == "DoubleProperty":
        return struct.unpack_from("<d", data, pos)[0]
    if expected_type == "BoolProperty":
        return data[pos] != 0
    return None


def find_scalar(strings: list[Str], data: bytes, name: str, expected_type: str, byte_size: int):
    hit = next((s for s in strings if s.text == name), None)
    if hit is None:
        return None
    pos = _locate_scalar_value(data, hit.offset, len(hit.text), expected_type, byte_size)
    if pos is None:
        return None
    return _decode_value_at(data, pos, expected_type)


def find_scalar_value_offset(strings: list[Str], data: bytes, name: str, expected_type: str, byte_size: int) -> int | None:
    """Like find_scalar, but returns the file offset of the raw value bytes
    instead of the decoded value -- for in-place patching."""
    hit = next((s for s in strings if s.text == name), None)
    if hit is None:
        return None
    return _locate_scalar_value(data, hit.offset, len(hit.text), expected_type, byte_size)


def _locate_bool_array_values(data: bytes, name_offset: int, name_text_len: int) -> tuple[int, int] | None:
    """Validates an ArrayProperty-of-BoolProperty tag right after a name
    string. Confirmed byte layout (reverse-engineered from real Duskfade
    saves, e.g. Habilidades/Gadgets/UpHabilidades/UpGadgets/UpMinutero/
    UpCuco -- fixed-size toggle lists like unlocked abilities/gadgets):

        Type="ArrayProperty"  (FString)
        <4 bytes, always 1 in every sample seen -- unidentified, treated
         as an opaque constant, not validated>
        InnerType="BoolProperty"  (FString)
        ArrayIndex (int32, always 0)
        Length (int32 -- byte size of Count+data, i.e. Count+4)
        terminator (1 byte, 0x00)
        Count (int32 -- number of bool elements)
        <Count raw bytes, one per element, 0x00/0x01>

    Returns (count, offset_of_first_bool_byte), or None if the tag doesn't
    match this exact shape."""
    try:
        pos = name_offset + name_text_len + 1
        type_len = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        if type_len <= 0 or type_len > 60:
            return None
        type_text = data[pos : pos + type_len - 1].decode("ascii")
        pos += type_len
        if type_text != "ArrayProperty":
            return None
        pos += 4  # unidentified constant field, always 1 so far
        inner_len = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        if inner_len <= 0 or inner_len > 60:
            return None
        inner_text = data[pos : pos + inner_len - 1].decode("ascii")
        pos += inner_len
        if inner_text != "BoolProperty":
            return None
        array_index = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        length = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        terminator = data[pos]
        pos += 1
        count = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        if array_index != 0 or terminator != 0 or count < 0 or count > 200 or length != count + 4:
            return None
        return count, pos
    except Exception:
        return None


def find_bool_array(strings: list[Str], data: bytes, name: str) -> tuple[int, int, list[bool]] | None:
    """Returns (count, offset_of_first_bool_byte, values) for an existing
    ArrayProperty-of-BoolProperty, or None if the property isn't present in
    this save at all (UE only serializes properties that differ from class
    default, so a fully-locked save is simply missing it)."""
    hit = next((s for s in strings if s.text == name), None)
    if hit is None:
        return None
    located = _locate_bool_array_values(data, hit.offset, len(hit.text))
    if located is None:
        return None
    count, offset = located
    return count, offset, [b != 0 for b in data[offset : offset + count]]


def write_fstring(s: str) -> bytes:
    text = s.encode("ascii") + b"\x00"
    return struct.pack("<i", len(text)) + text


def write_int_property(name: str, value: int) -> bytes:
    """A fresh top-level IntProperty entry, in Duskfade's confirmed tag
    order (ArrayIndex before Length)."""
    out = write_fstring(name)
    out += write_fstring("IntProperty")
    out += struct.pack("<I", 0)  # ArrayIndex
    out += struct.pack("<I", 4)  # Length -- 4 bytes for an int32
    out += b"\x00"  # terminator
    out += struct.pack("<i", value)
    return out


def write_bool_array_property(name: str, values: list[bool]) -> bytes:
    """A fresh top-level ArrayProperty-of-BoolProperty entry, matching the
    exact shape _locate_bool_array_values expects to read back."""
    count = len(values)
    out = write_fstring(name)
    out += write_fstring("ArrayProperty")
    out += struct.pack("<I", 1)  # unidentified constant, matches every real sample
    out += write_fstring("BoolProperty")
    out += struct.pack("<I", 0)  # ArrayIndex
    out += struct.pack("<I", count + 4)  # Length
    out += b"\x00"  # terminator
    out += struct.pack("<i", count)
    out += bytes(1 if v else 0 for v in values)
    return out


def find_top_level_terminator(data: bytes) -> int:
    """Returns the offset where the file's outermost property-list "None"
    terminator's length-prefix begins -- i.e. where new top-level
    properties can be safely inserted right before it.

    Confirmed (not assumed) against real Duskfade saves: the top-level
    terminator is the LAST "None" string in the file, and it's always
    immediately followed by a fixed 4-byte zero trailer that runs to EOF.
    Refuses rather than guessing if that exact shape isn't present.
    """
    strings = extract_ascii_strings(data, min_len=3)
    none_hits = [s for s in strings if s.text == "None"]
    if not none_hits:
        raise ValueError("no 'None' terminator found -- not a property list layout I recognize")
    last = none_hits[-1]
    prefix_offset = last.offset - 4
    expected_tail = struct.pack("<i", 5) + b"None\x00" + b"\x00\x00\x00\x00"
    actual_tail = data[prefix_offset:]
    if actual_tail != expected_tail:
        raise ValueError(
            "file doesn't end with the expected None-terminator + 4-byte trailer shape -- "
            "refusing to guess where the top-level property list actually ends"
        )
    return prefix_offset


def sanitize_folder_name(name: str) -> str:
    """Make a decoded checkpoint/zone string safe to use as a Windows folder name."""
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", "_", name)
    return name[:120] or "Unknown"


@dataclass
class SaveSummary:
    zone: str | None          # best short label for "what load zone is this"
    last_level_player: str | None
    last_checkpoint: str | None
    last_door: str | None
    shards: int | None
    gadget_index: int | None
    momento: int | None


def read_summary(path: str | Path) -> SaveSummary:
    data = Path(path).read_bytes()
    strings = extract_ascii_strings(data, min_len=4)

    last_level_player = find_value_after(strings, "LastLevelPlayer")
    last_checkpoint = find_value_after(strings, "LastCheckPointName")
    last_door = find_value_after(strings, "NombrePuerta")

    shards = find_scalar(strings, data, "CoinCounter", "IntProperty", 4)
    gadget_index = find_scalar(strings, data, "IndexGadgets", "IntProperty", 4)
    momento = find_scalar(strings, data, "Momento", "IntProperty", 4)

    # Prefer the short checkpoint name for folder/zone naming; fall back to
    # the full level path, then the door name.
    zone = last_checkpoint or last_level_player or last_door

    return SaveSummary(
        zone=zone,
        last_level_player=last_level_player,
        last_checkpoint=last_checkpoint,
        last_door=last_door,
        shards=shards,
        gadget_index=gadget_index,
        momento=momento,
    )
