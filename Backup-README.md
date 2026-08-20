# Restoring a backup by hand

The Save Editor doesn't have a Restore button — do it manually:

- **Close Duskfade first**, so nothing writes to the save while you're replacing it.
- Backups live in `Backups\<slot name>\`, e.g. `Backups\DFSlot_1\2026-08-20_18-22-16_before_shards.sav` — the filename is the timestamp it was made, and what triggered it (`load`/`cosmetics`/`unlocks`/`shards`).
- Copy your current live save somewhere safe first if you might want to undo this — restoring by hand doesn't back anything up for you.
- Copy the backup `.sav` you want into your live save folder (shown at the top of the Save Editor, defaults to `%LOCALAPPDATA%\Duskfade\Saved\SaveGames\`), renaming it to match the exact slot filename (e.g. `DFSlot_1.sav`), overwriting the existing one.
- Launch the game and Retry/Continue from the main menu to pick it up.
