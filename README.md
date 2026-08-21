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
- **Skip confirmations** — turns off the "are you sure" dialog before Load/Unlocks/Outfit/Shards actions, for anyone doing a lot of repeat loads who finds the extra click tedious. Off by default. Safe either way — the automatic backup is what actually protects your save, not the dialog.
- **Launch Duskfade** — starts the game straight from Steam, no need to alt-tab out.
- **Unlocks** — toggle any ability, gadget, or upgrade tier on your active save directly, no need to earn it in-game first.
- **Outfit** — force any outfit, outfit color, or sword skin color on your active save, owned or not.
- **Shards** — set the exact shard (currency) count on your active save.

**Unlocks**, **Outfit**, and **Shards** each show a themed confirmation — spelling out exactly what's about to change — before writing anything, the same as **Load Selected Save** already did (unless **Skip confirmations** is checked). Every one of these writes is atomic (via a temp-file-then-replace swap, so an interrupted write can never leave your save half-written) and backs up your current save first automatically. They all apply the same way once confirmed: back up, write, then pick up in-game on your next **Retry** or **Continue from menu** (walking between zones in a continuous session won't refresh them). To manually put an old backup back in place, see [`Backup-README.md`](Backup-README.md).

**Hotkeys** — Enter or double-click a row loads it straight away; `Ctrl+L` loads the selected row from anywhere in the window; `Ctrl+U` opens Unlocks; `Ctrl+O` opens Outfit; `Ctrl+G` opens Shards.

Run via `run_save_loader.bat`, or `python save_loader.py`.

The checkpoint list order is fixed (not sortable) — it reflects when each save was actually created, so it reads top-to-bottom the way a run plays out.

## 3. LiveSplit Autosplitter (`Duskfade.asl`)

Splits automatically as you progress through the any% route — every split is an individual checkbox in the component's settings (grouped by chapter), all on by default, so unchecking anything not in your route just skips it. Also starts the timer automatically the instant a real New Game begins (at difficulty-confirm, before any cutscenes), and ends the run automatically at the true credits — neither of those has a save-file event to hook, so this reads a couple of the game's own read-only memory values (never writes to the game) to catch them.

**Setup:**
1. Download [`Duskfade.asl`](Duskfade.asl) from this repo.
2. In LiveSplit: right-click → Edit Layout → **+** → Control → **Scriptable Auto Splitter**.
3. In that component's settings, browse to your downloaded `Duskfade.asl`.
4. If you have more than one save slot on disk, set `SlotFileName` in the component settings to your exact slot (e.g. `DFSlot_1.sav`) so an unrelated slot (e.g. a Steam Cloud sync) can't trigger a wrong split.

Don't run this alongside any other Duskfade autosplitter at the same time — each would independently fire the same start/split/reset and double-advance your segments.

## First-time setup

Both tools share `config.json` (created automatically on first run, with your save folder location). It defaults to:

```
%LOCALAPPDATA%\Duskfade\Saved\SaveGames
```

If your save folder is somewhere else, use "Browse..." in the Save Editor, or edit `config.json` directly. See `config.example.json` for the full set of options.

## Folder layout this creates

```
Library\...          one folder per zone/boss
Backups\...           automatic safety copies made before any load/edit --
                      kept for the newest backup_retention_count per slot (30 by
                      default), oldest pruned automatically; see Backup-README.md
                      to restore one by hand
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
