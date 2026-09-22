// Duskfade any% autosplitter
// Splits along the fixed any% route from save-file zone changes,
// starts on New Game and ends on the credits (live memory).
// Set SlotFileName below if you have more than one save slot.
// Don't run alongside Duskfade-LoadSplitter.asl.

state("Duskfade-Win64-Shipping")
{
	byte loadscreen : "Duskfade-Win64-Shipping.exe", 0x9642340;
}

startup
{
    // Exact slot file (e.g. "DFSlot_1.sav"), or "" to auto-detect
    vars.SlotFileName = "";

    vars.SaveDir = System.IO.Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Duskfade", "Saved", "SaveGames"
    );

    // { level_key, label, setting id, chapter }
    // First entry is the starting TickTown: consumed, never split
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
        if (entry[2] == "__start__") continue; // no checkbox
        settings.Add(entry[2], true, entry[1], entry[3]);
        settings.SetToolTip(entry[2], "Internal zone key: " + entry[0]);
    }

    vars.Pointer = 0;
    vars.LastLevel = (string)null;
    vars.CurrentLevel = (string)null;
    vars.SaveJustChanged = false;
    vars.ConsumedKeys = new HashSet<string>();
    vars.FileMtimes = new Dictionary<string, long>();

    // Printable ASCII runs (4+ chars) with their offsets
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

    // First non-type string after a property name
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

    settings.Add("autostart", true, "Auto-start on New Game (difficulty confirm)");
    settings.Add("autoend", true, "Auto-split on Credits (true ending)");
    settings.Add("autoreset", true, "Auto-reset if you return to the menu mid-run");
    settings.Add("worldfallback", true, "Also split on level load when no checkpoint save happens (wrong warps)");

    vars.MenuWorldName = "MenuInicio";
    vars.CreditsWorldName = "Creditos";
    vars.GWorldAddr = IntPtr.Zero;
    vars.NamePoolBase = IntPtr.Zero;
    vars.CurrentWorldName = (string)null;
    vars.PreviousWorldName = (string)null;
    vars.CreditsSplitSent = false;

    // FNamePool layout for this game build (confirmed live)
    const int chunksStart = 0x10;
    const int nameStride = 2;
    const int nameStringOffset = 2;
    const int nameHeaderOffset = 0;
    const int nameHeaderShift = 6;
    const int nameBlockOffsetBits = 16;

    // FName index -> string (ported from Dumper-7)
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
                int entryIdOff = nameStringOffset;
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

    // Route back to the top; current save zone becomes the baseline
    vars.ResyncRoute = (Action)(() =>
    {
        vars.Pointer = 0;
        vars.LastLevel = (string)vars.CurrentLevel;
        vars.ConsumedKeys = new HashSet<string>();
        vars.CreditsSplitSent = false;
    });
}

init
{
    vars.Pointer = 0;
    vars.LastLevel = (string)null;
    vars.CreditsSplitSent = false;
    vars.SaveJustChanged = false;
    vars.ConsumedKeys = new HashSet<string>();
    vars.CurrentWorldName = (string)null;
    vars.PreviousWorldName = (string)null;

    vars.GWorldAddr = IntPtr.Zero;
    vars.NamePoolBase = IntPtr.Zero;

    var scanner = new SignatureScanner(game, modules.First().BaseAddress, modules.First().ModuleMemorySize);

    // GWorld (pattern from GSpots; disp32 at offset 12)
    var gWorldTarget = new SigScanTarget(12, "E8 ?? ?? ?? FF ?? 8B ?? 78 48 89 05 ?? ?? ?? ?? ?? 8B ?? 78")
    {
        OnFound = (p, s, addr) => addr + 0x4 + p.ReadValue<int>(addr)
    };
    try { vars.GWorldAddr = scanner.Scan(gWorldTarget); } catch { vars.GWorldAddr = IntPtr.Zero; }

    // GNames (FNamePool)
    var gNamesTarget = new SigScanTarget(3, "48 8D 0D ?? ?? ?? ?? E8 ?? ?? FE FF 4C 8B C0 C6 05 ?? ?? ?? ?? 01")
    {
        OnFound = (p, s, addr) => addr + 0x4 + p.ReadValue<int>(addr)
    };
    try { vars.NamePoolBase = scanner.Scan(gNamesTarget); } catch { vars.NamePoolBase = IntPtr.Zero; }
}

update
{
    vars.SaveJustChanged = false;

    // Live world (level) name
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
        catch { /* mid-load: keep last name */ }
    }

    // Save file changes
    try
    {
        string saveDir = (string)vars.SaveDir;
        if (!System.IO.Directory.Exists(saveDir)) return;

        var mtimes = (Dictionary<string, long>)vars.FileMtimes;
        string changedPath = null;
        string slotFileName = (string)vars.SlotFileName;

        if (!string.IsNullOrEmpty(slotFileName))
        {
            // Pinned slot
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
            // Auto-detect: most recently changed slot
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
        if (level != null)
        {
            vars.CurrentLevel = level;
            vars.SaveJustChanged = true;
        }
    }
    catch
    {
    }
}

split
{
    // Credits
    if (settings["autoend"] && (string)vars.CurrentWorldName == (string)vars.CreditsWorldName && !(bool)vars.CreditsSplitSent)
    {
        vars.CreditsSplitSent = true;
        return true;
    }

    var route = (string[][])vars.Route;
    int pointer = (int)vars.Pointer;
    var consumed = (HashSet<string>)vars.ConsumedKeys;

    // Level load onto the next route zone with no save (wrong warps)
    string world = (string)vars.CurrentWorldName;
    if (settings["worldfallback"] && world != null && world != (string)vars.PreviousWorldName
        && pointer < route.Length
        && string.Equals(world, route[pointer][0], StringComparison.OrdinalIgnoreCase))
    {
        vars.Pointer = pointer + 1;
        vars.LastLevel = route[pointer][0];
        consumed.Add(route[pointer][0]);
        if (route[pointer][2] == "__start__") return false;
        return settings[route[pointer][2]] && settings[route[pointer][3]];
    }

    // Only react to a real save write
    if (!(bool)vars.SaveJustChanged) return false;

    string level = (string)vars.CurrentLevel;
    if (level == null || level == (string)vars.LastLevel) return false;
    vars.LastLevel = level;

    // Scan forward (skipped zones are passed over);
    // a later repeat of an already-reached zone is a revisit, not progress
    for (int i = pointer; i < route.Length; i++)
    {
        if (level != route[i][0]) continue;
        if (i != pointer && consumed.Contains(level)) return false;
        vars.Pointer = i + 1;
        consumed.Add(level);
        string settingId = route[i][2];
        if (settingId == "__start__") return false; // consumed, not a real split
        string parentId = route[i][3];
        return settings[settingId] && settings[parentId];
    }
    return false;
}

start
{
    // Leaving the main menu
    if (!settings["autostart"]) return false;
    return (string)vars.PreviousWorldName == (string)vars.MenuWorldName
        && vars.CurrentWorldName != null
        && (string)vars.CurrentWorldName != (string)vars.MenuWorldName;
}

onStart
{
    ((Action)vars.ResyncRoute)();
}

reset
{
    // Back to the main menu mid-run
    if (!settings["autoreset"]) return false;
    return (string)vars.CurrentWorldName == (string)vars.MenuWorldName
        && (string)vars.PreviousWorldName != (string)vars.MenuWorldName;
}

onReset
{
    ((Action)vars.ResyncRoute)();
}

isLoading
{
    return current.loadscreen == 6;
}
