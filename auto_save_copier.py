"""
Duskfade Auto Save-Copier
--------------------------
Watches your live Duskfade save slot(s). Every time the decoded checkpoint/
zone changes (i.e. you hit a new checkpoint, enter a new level, or start a
boss encounter), it copies that save file into a local library folder named
after the zone. Run through the game once and you end up with a folder per
load zone / boss fight, ready to feed into save_loader.py.

Usage: just run it (double-click run_auto_copier.bat, or `python
auto_save_copier.py`) while you play. Leave it running in the background.
Stop with Ctrl+C.

Nothing here ever writes to your live save — it only reads and copies FROM it.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import gvas_lite
import tool_config

HERE = Path(__file__).resolve().parent
STATE_PATH = HERE / "capture_state.json"


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def zone_label(summary: gvas_lite.SaveSummary) -> str | None:
    if not summary.zone:
        return None
    parts = [p for p in (summary.last_level_player, summary.last_checkpoint) if p]
    raw = "__".join(dict.fromkeys(parts)) if parts else summary.zone
    return gvas_lite.sanitize_folder_name(raw)


def try_capture(slot_path: Path, captures_dir: Path, state: dict) -> None:
    slot_key = slot_path.name
    slot_state = state.setdefault(slot_key, {"mtime": None, "zone": None})

    mtime = slot_path.stat().st_mtime
    if mtime == slot_state["mtime"]:
        return  # no change since last check

    try:
        summary = gvas_lite.read_summary(slot_path)
    except Exception as e:
        # Likely mid-write by the game; try again next poll.
        print(f"  [{slot_key}] couldn't read yet ({e}), will retry")
        return

    label = zone_label(summary)
    slot_state["mtime"] = mtime

    if label is None:
        return
    if label == slot_state["zone"]:
        return  # no change since the last poll — skip

    dest_dir = captures_dir / label
    if any(dest_dir.glob("*.sav")):
        # Already have a capture of this exact checkpoint from earlier in
        # this run (or a previous one) — remember it as "current" so we
        # don't check again every poll, but don't file a duplicate. This is
        # what actually stops death/respawn loops near the same checkpoint
        # from spamming captures: comparing only to the immediately-previous
        # poll misses the case where something else briefly interrupts and
        # you land back on a checkpoint already on disk.
        slot_state["zone"] = label
        return
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dest_path = dest_dir / f"{stamp}.sav"
    shutil.copy2(slot_path, dest_path)

    extras = []
    if summary.shards is not None:
        extras.append(f"shards={summary.shards}")
    if summary.momento is not None:
        extras.append(f"momento={summary.momento}")
    extra_str = f" ({', '.join(extras)})" if extras else ""
    print(f"  [{slot_key}] new zone '{label}'{extra_str} -> captured")

    slot_state["zone"] = label


def main() -> None:
    cfg = tool_config.load_config()
    save_dir = Path(cfg["save_dir"])
    captures_dir = tool_config.captures_dir(cfg)
    captures_dir.mkdir(parents=True, exist_ok=True)
    poll_seconds = cfg.get("poll_seconds", 2)

    if not save_dir.exists():
        print(f"Save directory not found: {save_dir}")
        print(f"Fix the 'save_dir' value in {tool_config.CONFIG_PATH} and re-run.")
        sys.exit(1)

    state = load_state()

    print("Duskfade Auto Save-Copier")
    print(f"  Watching: {save_dir}\\{cfg['slot_pattern']}")
    print(f"  Library:  {captures_dir}")
    print("  Play the game normally. Ctrl+C to stop.\n")

    try:
        while True:
            for slot_path in sorted(save_dir.glob(cfg["slot_pattern"])):
                try_capture(slot_path, captures_dir, state)
            save_state(state)
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        save_state(state)
        print("\nStopped.")


if __name__ == "__main__":
    main()
