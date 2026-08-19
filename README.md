# Duskfade Save Tools

Save management and practice tools for [Duskfade](https://store.steampowered.com/app/2542020) (UE5.6). Pure Python standard library + Tkinter — no extra packages needed to run from source.

Two tools that work together:

## 1. Auto Save-Copier (`auto_save_copier.py`)

Leave it running in the background while you play. Every time your save file's checkpoint/zone changes, it copies that save into:

```
Library\<zone name>\<timestamp>.sav
```

Play through the game with this running and you end up with a save for every load zone and boss fight, ready to use in the loader. It never writes to your live save — only reads and copies from it.

Run via `run_auto_copier.bat`, or `python auto_save_copier.py`. Stop with Ctrl+C.

## 2. Save Loader (`save_loader.py`)

A browsable list of every save in your library, plus:

- **Load Selected Save** — copies the chosen save over your active save slot. Your current save is always backed up first, automatically, into `Backups\` — nothing is ever lost.
- **Rename** — give any entry a display name (most bosses already ship with their real name baked in).
- **Lock default slot** — pins a specific `DFSlot_*.sav` as the permanent overwrite target. While locked, the slot picker is disabled, so you can't accidentally overwrite a different save file until you deliberately unlock it.
- **Launch Duskfade** — starts the game straight from Steam, no need to alt-tab out.

Run via `run_save_loader.bat`, or `python save_loader.py`.

The checkpoint list order is fixed (not sortable) — it reflects when each save was actually created, so it reads top-to-bottom the way a run plays out.

## First-time setup

Both tools share `config.json` (created automatically on first run, with your save folder location). It defaults to:

```
%LOCALAPPDATA%\Duskfade\Saved\SaveGames
```

If your save folder is somewhere else, use "Browse..." in the Save Loader, or edit `config.json` directly. See `config.example.json` for the full set of options.

## Folder layout this creates

```
Library\...          one folder per zone/boss
Backups\...           automatic safety copies made before any load
config.json           shared settings
capture_state.json    auto-copier's "what zone did I last see" memory
library_names.json    any names set with "Rename" beyond the built-in defaults
```

## Requirements

Python 3.10+. No third-party packages.

## GVAS format notes

`gvas_lite.py` decodes Duskfade's save format directly, without a full GVAS parser. Two confirmed non-standard quirks in this game's UE5.6 build are handled explicitly:

1. One extra null padding byte after the header's save-class name field.
2. Property tags write `ArrayIndex` before `Length` — reversed from every reference GVAS implementation.

## License

GPL-3.0 — see [LICENSE](LICENSE).
