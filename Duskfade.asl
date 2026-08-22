/*
Duskfade autosplitter (ASL)

Watches Duskfade's save files for zone progression and splits
automatically as the route advances. Every split point is an individual
checkbox in this component's settings (grouped by chapter) -- uncheck
whatever doesn't belong in your route and only the checked ones will
actually fire. All default to on, matching the full any% route.

Zones you skip entirely (never visit) are handled too: matching searches
forward from wherever the route currently is, so if the real next zone you
reach is a few positions further down the list, everything in between is
quietly passed over -- no split, no getting stuck.

By default it watches every DFSlot_*.sav file and reacts to whichever one
changed most recently -- convenient with no setup, but if more than one
save slot exists on disk, anything that touches an unrelated slot (Steam
Cloud sync, for example) can be picked up by mistake and cause wrong or
early splits. To avoid that, set SlotFileName below to the exact slot
you play on, e.g. "DFSlot_1.sav" -- then only that file is ever watched.

Auto-start and auto-end (both toggleable in settings, on by default) read
Duskfade's live engine memory instead of the save file, since neither point
has a save event to detect: New Game is watched via the game's live UWorld
changing from the main menu's own level ("MenuInicio") to anything else
while the timer isn't running -- confirmed by hand the very next world
after MenuInicio is "IntroCinematica" (the intro cutscene, its own separate
level), well before the player gets control in "Tutorial", so this fires
at the real speedrun-legal start point (difficulty confirmed), not once
cutscenes finish. The true ending is watched via the world "Creditos" (the
credits sequence) -- a real distinct world that only appears once the
post-final-boss escape sequence and cutscenes are genuinely finished.
Returning to MenuInicio mid-run (dying and exiting, quitting out, etc.)
auto-resets the timer for the next attempt -- this can never fire after a
legitimate finish, since the Creditos split already ends the run (moves the
timer out of Running phase) before any such transition could occur.

GWorld/GNames are located via an external AOB signature scan (patterns
from GSpots, github.com/Do0ks/GSpots) -- read-only, only ever
ReadProcessMemory, never writes to the game. They resolve to a fixed
offset from the module's own base address, so they're stable across
relaunches and across machines running the same game build, even though
ASLR moves the module's base address itself every launch. The FNamePool
decoder is ported from Dumper-7 (github.com/Encryqed/Dumper-7)'s
NameArray.cpp/.h; its usual pool-layout auto-discovery was replaced here
with constants already confirmed live against this exact game build (see
chunksStart/nameStride/nameHeaderShift below) -- if a future game update
ever moves these, re-derive them the same way (see the project's
mem_scan.py / name_scan.py research scripts) rather than guessing new
values.
*/

state("Duskfade-Win64-Shipping")
{
}

startup
{
    // Set this to your save slot's exact filename (e.g. "DFSlot_1.sav")
    // for reliable single-slot tracking. Leave "" to auto-detect instead.
    vars.SlotFileName = "";

    vars.SaveDir = System.IO.Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Duskfade", "Saved", "SaveGames"
    );

    // { level_key, label, setting id, parent chapter id }
    // level_key must exactly match the game's LastLevelPlayer value.
    //
    // The very first entry is special: "TickTown" is the starting town every
    // single run passes through before Forest1, and "TickTown" also recurs
    // later in the route (post-Volcano, post-Library, post-Boss3, post-
    // Boss4). Because split() forward-scans from the current pointer rather
    // than requiring adjacency, leaving this starting visit out of the route
    // entirely let it get matched against the wrong (later) TickTown
    // occurrence whenever the pointer was freshly reset to 0 -- silently
    // skipping every real split between Forest1 and that later TickTown.
    // Giving it its own settingId ("__start__", checked for explicitly in
    // split() below) lets the pointer consume it like a normal route entry
    // -- advancing past index 0 -- without actually firing a split.
    vars.Route = new[] {
        new[] { "TickTown", "Ticktown (start)", "__start__", "ch1" },
        new[] { "Forest1", "Forest 1", "forest_1", "ch1" },
        new[] { "AncientTemple1_GB", "Temple 1", "temple_1", "ch1" },
        new[] { "BurntForest_GB", "Burnt Forest", "burnt_forest", "ch1" },
        new[] { "Caves_GB", "Caves", "caves", "ch1" },
        new[] { "Wrath_GB", "Wrath (Boss)", "wrath_boss", "ch1" },
        new[] { "Volcano_GB", "Volcano", "volcano", "ch1" },
        new[] { "Guayota_GB", "Guayota (Boss)", "guayota_boss", "ch1" },
        new[] { "TickTown", "Ticktown (post-Volcano)", "ticktown_post_volcano", "ch1" },

        new[] { "Forest2", "Forest 2", "forest_2", "ch2" },
        new[] { "Archipelagos", "Archipelagos", "archipelagos", "ch2" },
        new[] { "AncientTemple2", "Temple 2", "temple_2", "ch2" },
        new[] { "School1", "School 1", "school_1", "ch2" },
        new[] { "School_Rework", "School (transition area)", "school_transition", "ch2" },
        new[] { "MiniBoss2", "Miniboss 2", "miniboss_2", "ch2" },
        new[] { "School3", "School 3", "school_3", "ch2" },
        new[] { "Library_GB", "Library", "library", "ch2" },
        new[] { "Boss2", "Boss 2", "boss_2", "ch2" },
        new[] { "TickTown", "Ticktown (post-Library)", "ticktown_post_library", "ch2" },

        new[] { "Forest3", "Forest 3", "forest_3", "ch3" },
        new[] { "AncientTemple3", "Temple 3", "temple_3", "ch3" },
        new[] { "Observatory", "Observatory", "observatory", "ch3" },
        new[] { "Sky1", "Sky 1", "sky_1", "ch3" },
        new[] { "Sky2", "Sky 2", "sky_2", "ch3" },
        new[] { "SkyPalace", "Sky Palace", "sky_palace", "ch3" },
        new[] { "Boss3", "Boss 3", "boss_3", "ch3" },
        new[] { "TickTown", "Ticktown (post-Boss3)", "ticktown_post_boss3", "ch3" },

        new[] { "Forest4", "Forest 4", "forest_4", "ch4" },
        new[] { "AncientTemple4", "Temple 4", "temple_4", "ch4" },
        new[] { "Canyon", "Canyon", "canyon", "ch4" },
        new[] { "Catacombs", "Catacombs", "catacombs", "ch4" },
        new[] { "Miniboss4", "Miniboss 4", "miniboss_4", "ch4" },
        new[] { "Desert", "Desert", "desert", "ch4" },
        new[] { "Boss4", "Boss 4", "boss_4", "ch4" },
        new[] { "AnclaBoss4", "Post-Boss 4 (transition area)", "post_boss4_transition", "ch4" },
        new[] { "TickTown", "Ticktown (post-Boss4)", "ticktown_post_boss4", "ch4" },

        new[] { "TowerCorridor", "Tower Corridor", "tower_corridor", "ch5" },
        new[] { "FinalBoss", "Final Boss", "final_boss", "ch5" },
        new[] { "TowerEscape", "Tower Escape", "tower_escape", "ch5" },
    };

    settings.Add("ch1", true, "Chapter 1 — Volcano");
    settings.Add("ch2", true, "Chapter 2 — Library");
    settings.Add("ch3", true, "Chapter 3 — Sky");
    settings.Add("ch4", true, "Chapter 4 — Desert");
    settings.Add("ch5", true, "Chapter 5 — Tower");

    foreach (var entry in (string[][])vars.Route)
    {
        if (entry[2] == "__start__") continue; // internal marker, not a real split -- no checkbox
        settings.Add(entry[2], true, entry[1], entry[3]);
        settings.SetToolTip(entry[2], "Internal zone key: " + entry[0]);
    }

    vars.Pointer = 0;
    vars.LastLevel = "";
    vars.CurrentLevel = (string)null;
    vars.FileMtimes = new Dictionary<string, long>();

    vars.ExtractStrings = (Func<byte[], List<KeyValuePair<int, string>>>)((data) =>
    {
        var results = new List<KeyValuePair<int, string>>();
        int start = -1;
        for (int i = 0; i < data.Length; i++)
        {
            byte b = data[i];
            bool printable = b >= 0x20 && b <= 0x7e;
            if (printable)
            {
                if (start == -1) start = i;
            }
            else
            {
                if (start != -1 && i - start >= 4)
                    results.Add(new KeyValuePair<int, string>(start, System.Text.Encoding.ASCII.GetString(data, start, i - start)));
                start = -1;
            }
        }
        if (start != -1 && data.Length - start >= 4)
            results.Add(new KeyValuePair<int, string>(start, System.Text.Encoding.ASCII.GetString(data, start, data.Length - start)));
        return results;
    });

    vars.TypeTokens = new HashSet<string> {
        "StrProperty", "IntProperty", "BoolProperty", "StructProperty",
        "ArrayProperty", "ObjectProperty", "None"
    };

    vars.FindValueAfter = (Func<List<KeyValuePair<int, string>>, string, string>)((strings, key) =>
    {
        int idx = strings.FindIndex(s => s.Value == key);
        if (idx == -1) return null;
        int maxAhead = 6;
        for (int i = idx + 1; i < Math.Min(idx + 1 + maxAhead, strings.Count); i++)
        {
            if (((HashSet<string>)vars.TypeTokens).Contains(strings[i].Value)) continue;
            return strings[i].Value;
        }
        return null;
    });

    // --- Auto-start / auto-end / auto-reset (live memory, see header comment) ---
    settings.Add("autostart", true, "Auto-start on New Game (difficulty confirm)");
    settings.Add("autoend", true, "Auto-split on Credits (true ending)");
    settings.Add("autoreset", true, "Auto-reset if you return to the menu mid-run");

    vars.MenuWorldName = "MenuInicio";
    vars.CreditsWorldName = "Creditos";
    vars.GWorldAddr = IntPtr.Zero;
    vars.NamePoolBase = IntPtr.Zero;
    vars.CurrentWorldName = (string)null;
    vars.PreviousWorldName = (string)null;
    vars.CreditsSplitSent = false;

    // FNamePool layout constants for this game build -- confirmed live
    // 2026-08-21 (see name_scan.py). chunksStart is always 0x10 for every
    // FNamePool build Dumper-7 has seen; the rest (stride/headerOffset/
    // shift/blockOffsetBits) are specific to this compiled exe.
    const int chunksStart = 0x10;
    const int nameStride = 2;
    const int nameStringOffset = 2;
    const int nameHeaderOffset = 0;
    const int nameHeaderShift = 6;
    const int nameBlockOffsetBits = 16;

    Func<Process, IntPtr, int, int, string> decodeFName = null;
    decodeFName = (p, poolBase, compIdx, depth) =>
    {
        if (compIdx < 0 || depth > 3) return null;
        int chunkIdx = compIdx >> nameBlockOffsetBits;
        int inChunkOff = (compIdx & ((1 << nameBlockOffsetBits) - 1)) * nameStride;
        IntPtr chunkPtr;
        try { chunkPtr = (IntPtr)p.ReadValue<long>((IntPtr)((long)poolBase + chunksStart + chunkIdx * 8)); }
        catch { return null; }
        if (chunkPtr == IntPtr.Zero) return null;
        IntPtr entryAddr = (IntPtr)((long)chunkPtr + inChunkOff);
        ushort header;
        try { header = p.ReadValue<ushort>((IntPtr)((long)entryAddr + nameHeaderOffset)); }
        catch { return null; }
        int nameLen = header >> nameHeaderShift;
        bool isWide = (header & 0x1) != 0;
        try
        {
            if (nameLen == 0)
            {
                int entryIdOff = nameStringOffset + (nameStringOffset == 6 ? 2 : 0);
                int nextIdx = p.ReadValue<int>((IntPtr)((long)entryAddr + entryIdOff));
                int number = p.ReadValue<int>((IntPtr)((long)entryAddr + entryIdOff + 4));
                string baseName = decodeFName(p, poolBase, nextIdx, depth + 1);
                if (baseName == null) return null;
                return number > 0 ? baseName + "_" + (number - 1) : baseName;
            }
            byte[] bytes;
            if (isWide)
            {
                if (!p.ReadBytes((IntPtr)((long)entryAddr + nameStringOffset), nameLen * 2, out bytes)) return null;
                return Encoding.Unicode.GetString(bytes);
            }
            else
            {
                if (!p.ReadBytes((IntPtr)((long)entryAddr + nameStringOffset), nameLen, out bytes)) return null;
                return Encoding.ASCII.GetString(bytes);
            }
        }
        catch { return null; }
    };
    vars.DecodeFName = decodeFName;
}

init
{
    vars.Pointer = 0;
    vars.LastLevel = "";
    vars.CreditsSplitSent = false;
    vars.CurrentWorldName = (string)null;
    vars.PreviousWorldName = (string)null;

    vars.GWorldAddr = IntPtr.Zero;
    vars.NamePoolBase = IntPtr.Zero;

    var scanner = new SignatureScanner(game, modules.First().BaseAddress, modules.First().ModuleMemorySize);

    // GWorld: confirmed live this session that only this variant (of
    // several tried) matches Duskfade's compiled code -- resolves to the
    // address of the GWorld global itself (a pointer-to-UWorld*, still
    // needs one dereference every read since the *value* changes whenever
    // a new level loads). This pattern carries leading context bytes
    // ("E8 ?? ?? ?? FF ?? 8B ?? 78") before the actual "48 89 05" mov
    // instruction, which sits at pattern position 9 -- so the SigScanTarget
    // offset (12) points at the disp32 right after it, not at the pattern
    // start.
    var gWorldTarget = new SigScanTarget(12, "E8 ?? ?? ?? FF ?? 8B ?? 78 48 89 05 ?? ?? ?? ?? ?? 8B ?? 78")
    {
        OnFound = (p, s, addr) => addr + 0x4 + p.ReadValue<int>(addr)
    };
    try { vars.GWorldAddr = scanner.Scan(gWorldTarget); } catch { vars.GWorldAddr = IntPtr.Zero; }

    // GNames (FNamePool): resolves directly to the pool object's own
    // address -- no extra dereference (confirmed live: decoding UWorld's
    // own name through this address correctly produced "MenuInicio").
    var gNamesTarget = new SigScanTarget(3, "48 8D 0D ?? ?? ?? ?? E8 ?? ?? FE FF 4C 8B C0 C6 05 ?? ?? ?? ?? 01")
    {
        OnFound = (p, s, addr) => addr + 0x4 + p.ReadValue<int>(addr)
    };
    try { vars.NamePoolBase = scanner.Scan(gNamesTarget); } catch { vars.NamePoolBase = IntPtr.Zero; }
}

update
{
    // A reset (or a fresh attempt started without closing the game) should
    // always resync back to the top of the route -- otherwise a leftover
    // Pointer position from the previous attempt could silently swallow
    // every split on the next one.
    //
    // LastLevel is baselined to whatever CurrentLevel already is (not
    // blanked to "") -- otherwise the level you're already standing on
    // when you hit Start (e.g. a checkpoint save loaded to begin the run)
    // reads as a "new" zone the instant Running begins, firing a split
    // immediately even though no real transition happened.
    if (timer.CurrentPhase != LiveSplit.Model.TimerPhase.Running)
    {
        vars.Pointer = 0;
        vars.LastLevel = vars.CurrentLevel;
        vars.CreditsSplitSent = false;
    }

    // --- World name (menu/cutscene/level/credits detection) ---
    vars.PreviousWorldName = vars.CurrentWorldName;
    if ((IntPtr)vars.GWorldAddr != IntPtr.Zero && (IntPtr)vars.NamePoolBase != IntPtr.Zero)
    {
        try
        {
            IntPtr uworldPtr = (IntPtr)game.ReadValue<long>((IntPtr)vars.GWorldAddr);
            if (uworldPtr != IntPtr.Zero)
            {
                int compIdx = game.ReadValue<int>((IntPtr)((long)uworldPtr + 0x18));
                string name = ((Func<Process, IntPtr, int, int, string>)vars.DecodeFName)(game, (IntPtr)vars.NamePoolBase, compIdx, 0);
                if (name != null) vars.CurrentWorldName = name;
            }
        }
        catch { /* transient read failure (e.g. level loading) -- keep last known name */ }
    }

    try
    {
        string saveDir = (string)vars.SaveDir;
        if (!System.IO.Directory.Exists(saveDir)) return;

        var mtimes = (Dictionary<string, long>)vars.FileMtimes;
        string changedPath = null;
        string slotFileName = (string)vars.SlotFileName;

        if (!string.IsNullOrEmpty(slotFileName))
        {
            // Pinned mode: only this exact file is ever watched.
            string pinnedPath = System.IO.Path.Combine(saveDir, slotFileName);
            if (!System.IO.File.Exists(pinnedPath)) return;
            long ticks = System.IO.File.GetLastWriteTimeUtc(pinnedPath).Ticks;
            long previous;
            bool known = mtimes.TryGetValue(pinnedPath, out previous);
            mtimes[pinnedPath] = ticks;
            if (known && ticks == previous) return;
            changedPath = pinnedPath;
        }
        else
        {
            // Auto-detect mode: react to whichever slot changed most recently.
            long changedTicks = -1;
            foreach (var path in System.IO.Directory.GetFiles(saveDir, "DFSlot_*.sav"))
            {
                long ticks = System.IO.File.GetLastWriteTimeUtc(path).Ticks;
                long previous;
                bool known = mtimes.TryGetValue(path, out previous);
                mtimes[path] = ticks;
                if (known && ticks == previous) continue;
                if (ticks > changedTicks)
                {
                    changedTicks = ticks;
                    changedPath = path;
                }
            }
            if (changedPath == null) return;
        }

        byte[] data;
        try
        {
            data = System.IO.File.ReadAllBytes(changedPath);
        }
        catch
        {
            return;
        }

        var strings = ((Func<byte[], List<KeyValuePair<int, string>>>)vars.ExtractStrings)(data);
        string level = ((Func<List<KeyValuePair<int, string>>, string, string>)vars.FindValueAfter)(strings, "LastLevelPlayer");
        if (level != null) vars.CurrentLevel = level;
    }
    catch
    {
    }
}

split
{
    if (settings["autoend"] && (string)vars.CurrentWorldName == (string)vars.CreditsWorldName && !(bool)vars.CreditsSplitSent)
    {
        vars.CreditsSplitSent = true;
        return true;
    }

    string level = (string)vars.CurrentLevel;
    if (level == null || level == (string)vars.LastLevel) return false;
    vars.LastLevel = level;

    var route = (string[][])vars.Route;
    int pointer = (int)vars.Pointer;

    // Scan forward from the current pointer rather than requiring an exact
    // adjacent match -- if the real next zone reached is further down the
    // list (a zone in between was skipped entirely, or its checkbox is
    // simply off), jump the pointer there instead of getting stuck.
    for (int i = pointer; i < route.Length; i++)
    {
        if (level == route[i][0])
        {
            vars.Pointer = i + 1;
            string settingId = route[i][2];
            if (settingId == "__start__") return false; // consumed, not a real split
            string parentId = route[i][3];
            return settings[settingId] && settings[parentId];
        }
    }
    return false;
}

start
{
    if (!settings["autostart"]) return false;
    return (string)vars.PreviousWorldName == (string)vars.MenuWorldName
        && vars.CurrentWorldName != null
        && (string)vars.CurrentWorldName != (string)vars.MenuWorldName;
}

reset
{
    // reset only ever runs while the timer is actively Running, so a
    // legitimate finish is never mistaken for this: the Creditos split
    // already moves the timer to Ended phase before any later transition
    // back to MenuInicio (post-credits, if the game does that) could occur.
    // This only catches genuinely abandoning a run early -- dying and
    // exiting to the main menu, quitting out mid-attempt, etc.
    if (!settings["autoreset"]) return false;
    return (string)vars.CurrentWorldName == (string)vars.MenuWorldName
        && (string)vars.PreviousWorldName != (string)vars.MenuWorldName;
}
