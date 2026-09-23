# Duskfade Save Tools

Save management and practice tools for [Duskfade](https://store.steampowered.com/app/2542020) (UE5.6). Pure Python standard library + Tkinter — no extra packages needed to run from source.

**Just want the app?** Grab the packaged Windows build from [Releases](https://github.com/Zyrumi/duskfade-save-tools/releases/latest) — it's self-contained (starter checkpoint library and icon built in, no Python or the Auto Save-Copier required to get started). That library currently covers the **any% route only** (not every checkpoint in the game) — it grows with future releases. Run the Auto Save-Copier below yourself if you want your own saves added.

> **Windows will warn you before running it.** This is an unsigned exe from a small community project, so Windows SmartScreen shows a "Windows protected your PC" prompt on first run. That's normal, and not a sign that anything is wrong. 
Click **More info** → **Run anyway**.

What's here: two save tools that work together, plus two LiveSplit autosplitters.

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
- **Hotkeys** — assign F1-F12 to instantly load a specific save (right-click any row → **Assign Quick-Load Key...**) or toggle a specific ability/gadget/upgrade on your active save (**Hotkeys** button). Handy for swapping between a couple of practice spots, or granting yourself something like Crunia's Wings mid-exploration, with a single keypress. Manage every assignment (and remove them) from the **Hotkeys** button in the bottom bar.

**Unlocks**, **Outfit**, and **Shards** each show a themed confirmation — spelling out exactly what's about to change — before writing anything, the same as **Load Selected Save** already did (unless **Skip confirmations** is checked, which also covers hotkey-triggered loads/toggles). Every one of these writes is atomic (via a temp-file-then-replace swap, so an interrupted write can never leave your save half-written) and backs up your current save first automatically. They all apply the same way once confirmed: back up, write, then pick up in-game on your next **Retry** or **Continue from menu** (walking between zones in a continuous session won't refresh them). To manually put an old backup back in place, see [`Backup-README.md`](Backup-README.md).

Run via `run_save_loader.bat`, or `python save_loader.py`.

The checkpoint list order is fixed (not sortable) — it reflects when each save was actually created, so it reads top-to-bottom the way a run plays out.

## 3. LiveSplit Autosplitters

Two scripts, pick the one for your category. Both only read the game's memory and save files (they never write to the game). **Use only one at a time**: running both would fire every start/split twice.

| | Any% (`Duskfade.asl`) | Any category (`Duskfade-LoadSplitter.asl`) |
|---|---|---|
| For | The any% route | 100%, all achievements, anything else |
| Starts | Leaving the main menu (New Game) | Leaving the main menu (New Game), same moment as any% |
| Splits | Each zone on the fixed any% route | Every arrival in a different level, revisits included |
| Ends | Credits | Credits |
| Resets | Returning to the main menu (on by default) | Off by default, so quitting to the menu doesn't end a long run |

Both pause LiveSplit's **Game Time** during loading screens. To see load-removed time, right-click LiveSplit → Compare Against → **Game Time**. This reads a fixed memory address, so a game patch may break it until the script is updated.

**Setup:**
1. Download [`Duskfade.asl`](Duskfade.asl) or [`Duskfade-LoadSplitter.asl`](Duskfade-LoadSplitter.asl) from this repo.
2. In LiveSplit: right-click → Edit Layout → **+** → Control → **Scriptable Auto Splitter**.
3. In that component's settings, browse to the downloaded `.asl` file.

### Any% (`Duskfade.asl`)

Every split is its own checkbox in the component's settings, grouped by chapter and all on by default. Uncheck anything not in your route and it's skipped. Zones reached without a checkpoint save, like the wrong warp out of Guayota, still split when the level loads.

If you have more than one save slot on disk, set `SlotFileName` at the top of the script to your exact slot (e.g. `DFSlot_1.sav`), so an unrelated slot (e.g. a Steam Cloud sync) can't trigger a wrong split.

### Any category (`Duskfade-LoadSplitter.asl`)

No route to set up. It splits **every time** you arrive in a different level, including revisits. Coming back to TickTown for the third time in a run splits just like the first.

- Dying or retrying in the same level doesn't split.
- Quitting to the main menu and continuing doesn't split or reset. The timer keeps running.
- Each level has one checkbox under **Split every time you enter:**, all on by default. Checked means that level splits on every visit, and unchecked means it never splits. It's all visits or none, not per visit.

Your splits file needs one segment per arrival at a checked level (count every revisit), plus the credits.

## First-time setup

Both tools share `config.json` (created automatically on first run, with your save folder location). It defaults to:

```
%LOCALAPPDATA%\Duskfade\Saved\SaveGames
```

If your save folder is somewhere else, use "Save Folder..." → "Browse..." in the Save Editor, or edit `config.json` directly. See `config.example.json` for the full set of options.

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
