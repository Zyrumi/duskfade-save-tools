# Duskfade Save Tools

Save management and practice tools for [Duskfade](https://store.steampowered.com/app/2542020) (UE5.6). Pure Python standard library + Tkinter — no extra packages needed to run from source.

**Just want the app?** Grab the packaged Windows build from [Releases](https://github.com/Zyrumi/duskfade-save-tools/releases/latest) — it's self-contained (starter checkpoint library and icon built in, no Python or the Auto Save-Copier required to get started). That library currently covers the **any% route only** (not every checkpoint in the game) — it grows with future releases. Run the Auto Save-Copier below yourself if you want your own saves added.

> **Windows will warn you before running it.** This is an unsigned exe from a small community project, so Windows SmartScreen shows a "Windows protected your PC" prompt on first run. That's normal, and not a sign that anything is wrong. 
Click **More info** → **Run anyway**.

Two tools that work together:

## 1. Auto Save-Copier (`auto_save_copier.py`)

Leave it running in the background while you play. Every time your save file's checkpoint/zone changes, it copies that save into:

```
Library\<zone name>\<timestamp>.sav
```

Play through the game with this running and you end up with a save for every load zone and boss fight, ready to use in the editor. It never writes to your live save — only reads and copies from it.

Run via `run_auto_copier.bat`, or `python auto_save_copier.py`. Stop with Ctrl+C.

## 2. Save Editor (`save_loader.py`)

A browsable list of every save in your library, plus:

- **Load Selected Save** — copies the chosen save over your active save slot. Your current save is always backed up first, automatically, into `Backups\` — nothing is ever lost.
- **Rename checkpoint** — give any entry a display name (most bosses already ship with their real name baked in).
- **Lock default slot** — pins a specific `DFSlot_*.sav` as the permanent overwrite target. While locked, the slot picker is disabled, so you can't accidentally overwrite a different save file until you deliberately unlock it.
- **Launch Duskfade** — starts the game straight from Steam, no need to alt-tab out.
- **Unlocks** — toggle any ability, gadget, or upgrade tier on your active save directly, no need to earn it in-game first.
- **Outfit** — force any outfit, outfit color, or sword skin color on your active save, owned or not.
- **Shards** — set the exact shard (currency) count on your active save.
- **Restore Backup** — browse every automatic backup made for your active slot and put one back in place, with a preview of each backup's zone/shard count. No more digging through `Backups\` in Explorer and copy-pasting a file over your live save by hand.

**Unlocks**, **Outfit**, and **Shards** each show a themed confirmation — spelling out exactly what's about to change — before writing anything, the same as **Load Selected Save** and **Restore Backup** already did. Every one of these writes is atomic (via a temp-file-then-replace swap, so an interrupted write can never leave your save half-written) and backs up your current save first automatically. They all apply the same way once confirmed: back up, write, then pick up in-game on your next **Retry** or **Continue from menu** (walking between zones in a continuous session won't refresh them).

Run via `run_save_loader.bat`, or `python save_loader.py`.

The checkpoint list order is fixed (not sortable) — it reflects when each save was actually created, so it reads top-to-bottom the way a run plays out.

## First-time setup

Both tools share `config.json` (created automatically on first run, with your save folder location). It defaults to:

```
%LOCALAPPDATA%\Duskfade\Saved\SaveGames
```

If your save folder is somewhere else, use "Browse..." in the Save Editor, or edit `config.json` directly. See `config.example.json` for the full set of options.

## Folder layout this creates

```
Library\...          one folder per zone/boss
Backups\...           automatic safety copies made before any load/edit/restore --
                      kept for the newest backup_retention_count per slot (30 by
                      default), oldest pruned automatically; browse and restore
                      any of them from the "Restore Backup" button
config.json           shared settings
capture_state.json    auto-copier's "what zone did I last see" memory
library_names.json    any names set with "Rename" beyond the built-in defaults
```

## Requirements

Running from source: Python 3.10+, no third-party packages. Running the packaged build: Windows only, no Python needed.

## GVAS format notes

`gvas_lite.py` decodes Duskfade's save format directly, without a full GVAS parser. Two confirmed non-standard quirks in this game's UE5.6 build are handled explicitly:

1. One extra null padding byte after the header's save-class name field.
2. Property tags write `ArrayIndex` before `Length` — reversed from every reference GVAS implementation.

## License

GPL-3.0 — see [LICENSE](LICENSE).
