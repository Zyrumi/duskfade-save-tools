// Duskfade load splitter -- any category (100%, all achievements, ...)
// Starts on New Game, splits on every level arrival (revisits too),
// ends on the credits.
// Don't run alongside Duskfade.asl.

state("Duskfade-Win64-Shipping")
{
	byte loadscreen : "Duskfade-Win64-Shipping.exe", 0x9642340;
}

startup
{
    // { map name, label }
    vars.Levels = new[] {
        new[] { "IntroCinematica", "Intro cutscene" },
        new[] { "Tutorial", "Tutorial" },
        new[] { "TickTown", "TickTown" },
        new[] { "TristanHouse", "TristanHouse" },
        new[] { "Forest1", "Forest 1" },
        new[] { "AncientTemple1_GB", "Temple 1" },
        new[] { "BurntForest_GB", "Burnt Forest" },
        new[] { "Caves_GB", "Caves" },
        new[] { "Wrath_GB", "Wrath (Boss)" },
        new[] { "Volcano_GB", "Volcano" },
        new[] { "Guayota_GB", "Guayota (Boss)" },
        new[] { "Forest2", "Forest 2" },
        new[] { "Archipelagos", "Archipelagos" },
        new[] { "AncientTemple2", "Temple 2" },
        new[] { "School", "School" },
        new[] { "School1", "School 1" },
        new[] { "School_Rework", "School (transition area)" },
        new[] { "MiniBoss2", "Miniboss 2" },
        new[] { "School3", "School 3" },
        new[] { "Library_GB", "Library" },
        new[] { "Boss2", "Boss 2" },
        new[] { "Forest3", "Forest 3" },
        new[] { "AncientTemple3", "Temple 3" },
        new[] { "Observatory", "Observatory" },
        new[] { "Sky1", "Sky 1" },
        new[] { "Sky2", "Sky 2" },
        new[] { "SkyPalace", "Sky Palace" },
        new[] { "Boss3", "Boss 3" },
        new[] { "Forest4", "Forest 4" },
        new[] { "AncientTemple4", "Temple 4" },
        new[] { "Canyon", "Canyon" },
        new[] { "Catacombs", "Catacombs" },
        new[] { "MiniBoss4", "Miniboss 4" },
        new[] { "Desert", "Desert" },
        new[] { "DesertTR", "DesertTR" },
        new[] { "Boss4", "Boss 4" },
        new[] { "AnclaBoss4", "Post-Boss 4 (transition area)" },
        new[] { "TowerCorridor", "Tower Corridor" },
        new[] { "FinalBoss", "Final Boss" },
        new[] { "TowerEscape", "Tower Escape" },
        new[] { "TickTown_Cinematic_Final_SECRETO", "Secret ending cutscene" },
    };

    settings.Add("autostart", true, "Start on New Game");
    settings.Add("autoend", true, "Final split on the credits");
    settings.Add("autoreset", false, "Reset when returning to the main menu");
    settings.Add("levels", true, "Split every time you enter:");
    settings.SetToolTip("levels", "Each checked level splits on every visit, not just the first. Unchecked levels never split.");

    vars.KnownLevels = new HashSet<string>();
    foreach (var level in (string[][])vars.Levels)
    {
        vars.KnownLevels.Add(level[0]);
        settings.Add("lvl_" + level[0], true, level[1], "levels");
        settings.SetToolTip("lvl_" + level[0], "Splits on every arrival here. Map name: " + level[0]);
    }

    vars.MenuWorldName = "MenuInicio";
    vars.CreditsWorldName = "Creditos";
    vars.GWorldAddr = IntPtr.Zero;
    vars.NamePoolBase = IntPtr.Zero;
    vars.CurrentWorldName = (string)null;
    vars.PreviousWorldName = (string)null;
    vars.LastLevel = (string)null;
    vars.FromMenu = false;
    vars.CreditsSplitSent = false;

    // FNamePool layout (same as Duskfade.asl)
    const int chunksStart = 0x10;
    const int nameStride = 2;
    const int nameStringOffset = 2;
    const int nameHeaderOffset = 0;
    const int nameHeaderShift = 6;
    const int nameBlockOffsetBits = 16;

    // FName index -> string
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
                int nextIdx = p.ReadValue<int>((IntPtr)((long)entryAddr + nameStringOffset));
                int number = p.ReadValue<int>((IntPtr)((long)entryAddr + nameStringOffset + 4));
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

    // Current level becomes the baseline on start/reset;
    // mid-load (auto-start), the next level is the baseline
    vars.ResyncRun = (Action)(() =>
    {
        string world = (string)vars.CurrentWorldName;
        bool known = world != null && ((HashSet<string>)vars.KnownLevels).Contains(world);
        vars.LastLevel = known ? world : null;
        vars.FromMenu = !known;
        vars.CreditsSplitSent = false;
    });
}

init
{
    vars.CurrentWorldName = (string)null;
    vars.PreviousWorldName = (string)null;
    vars.LastLevel = (string)null;
    vars.FromMenu = false;
    vars.CreditsSplitSent = false;
    vars.GWorldAddr = IntPtr.Zero;
    vars.NamePoolBase = IntPtr.Zero;

    var scanner = new SignatureScanner(game, modules.First().BaseAddress, modules.First().ModuleMemorySize);

    // GWorld
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
    // Read the live world (level) name
    vars.PreviousWorldName = vars.CurrentWorldName;
    if ((IntPtr)vars.GWorldAddr == IntPtr.Zero || (IntPtr)vars.NamePoolBase == IntPtr.Zero) return;
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
    catch { } // mid-load: keep last name
}

start
{
    // Leaving the main menu (same moment as Duskfade.asl)
    if (!settings["autostart"]) return false;
    return (string)vars.PreviousWorldName == (string)vars.MenuWorldName
        && vars.CurrentWorldName != null
        && (string)vars.CurrentWorldName != (string)vars.MenuWorldName;
}

onStart
{
    ((Action)vars.ResyncRun)();
}

split
{
    string world = (string)vars.CurrentWorldName;
    if (world == null) return false;

    // Credits
    if (world == (string)vars.CreditsWorldName)
    {
        if (!settings["autoend"] || (bool)vars.CreditsSplitSent) return false;
        vars.CreditsSplitSent = true;
        return true;
    }

    // Main menu
    if (world == (string)vars.MenuWorldName)
    {
        vars.FromMenu = true;
        return false;
    }

    // Unknown name (loading map, mid-load read)
    if (!((HashSet<string>)vars.KnownLevels).Contains(world)) return false;

    // First level after the menu or run start: new baseline, no split
    if ((bool)vars.FromMenu)
    {
        vars.FromMenu = false;
        vars.LastLevel = world;
        return false;
    }

    // Same level (death, retry)
    if (world == (string)vars.LastLevel) return false;

    // New level
    vars.LastLevel = world;
    return settings["lvl_" + world];
}

reset
{
    if (!settings["autoreset"]) return false;
    return (string)vars.CurrentWorldName == (string)vars.MenuWorldName
        && (string)vars.PreviousWorldName != (string)vars.MenuWorldName;
}

onReset
{
    ((Action)vars.ResyncRun)();
}

isLoading
{
    return current.loadscreen == 6;
}
