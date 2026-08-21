"""
Duskfade Save Editor
---------------------
Successor to "Zyrumi's Sheepy Loader" — browse a library of saved game
states (auto-captured load zones/bosses from auto_save_copier.py) and
inject any of them into a live save slot, or edit unlocks/outfit directly
on your active save.

Your current save is always backed up automatically before anything is
overwritten, so any change here is non-destructive.

Run via run_save_loader.bat, or `python save_loader.py`.
"""
from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from angled_button import AngledButton
import cosmetic_names
import cosmetics
import gvas_lite
import shards
import tool_config
import unlocks
import updater

STEAM_APP_ID = "2542020"

# Same palette as the Duskfade speedrun hub website, so the whole tooling
# suite reads as one thing rather than a bare-Tkinter afterthought.
DUSK = "#1b1626"
PANEL = "#251f33"
PANEL_RAISED = "#2c2438"
EDGE = "#3c3350"
AMBER = "#e8935a"
AMBER_DIM = "#b97245"
TEAL = "#5fc9c0"
TEAL_DIM = "#3d8f88"
INK = "#f0e6d8"
INK_MID = "#c7bcd4"
INK_DIM = "#9184a3"

def _extract_raw_level(raw: str) -> str:
    """Auto-captured folder names are built from the game's internal
    LastLevelPlayer/LastCheckPointName strings (e.g.
    'School_Rework__School_Rework___BP_CheckPoint_C_UAID_74563CBA697E9D6602_1979343867')
    -- readable to the tool, not to a human. This pulls out just the zone's
    internal name, unmodified (matches splits.json's level_key exactly)."""
    level_part, _, _ = raw.partition("__")
    return level_part.strip() or raw


def _extract_level(raw: str) -> str:
    """Same as _extract_raw_level, but with underscores turned into spaces
    for display."""
    return _extract_raw_level(raw).replace("_", " ")


@dataclass
class Entry:
    path: Path
    group: str          # raw zone label, e.g. "Desert__Desert___BP_CheckPoint_C_1"
    display_group: str  # human-readable version shown in the UI
    captured_at: datetime | None
    shards: int | None
    momento: int | None


# Two zones (the literal start of the game, before any real checkpoint
# exists) whose real capture timestamps can't be trusted to land first --
# e.g. if a fresh run gets captured while an older library is still open,
# these can end up with a "later" timestamp than content from well into
# the game. Pinned to the front, in this order, regardless of when they
# were actually captured.
PINNED_FIRST = [
    "Tutorial__Tutorial___BP_CheckPoint_C_1",
    "TickTown",
]

# Real in-game names for zones that otherwise show a generic internal
# label -- known so far, mostly bosses. Ship these baked in so a fresh
# download already reads correctly with no setup; "Rename" only needs to
# write a file for names beyond this set.
DEFAULT_NAMES: dict[str, str] = {
    "Wrath_GB__Caves_GB___BP_CheckPoint_C_6": "Wrath",
    "Guayota_GB__Volcano_GB___BP_CheckPoint_C_UAID_74563CBA697E855202_1632524626": "Guayota",
    "Boss2__Library_GB___BP_CheckPoint_C_UAID_74563CBA697E2A6E02_2125569279": "Watcher",
    "MiniBoss2__School_Rework___BP_CheckPoint_C_UAID_74563CBA697E9D6602_1979343867": "Sadness",
    "Observatory__AncientTemple3___BP_CheckPoint_C_UAID_74563CBA697EB58B02_1966067342": "Guilt",
    "Boss3__SkyPalace___BP_CheckPoint_C_UAID_74563CBA697EBF8B02_1183227690": "Father Gaoth",
    "Miniboss4__Catacombs___BP_CheckPoint_C_UAID_74563CBA697E9ACA02_1790318563": "Solitude",
    "Boss4__Desert___BP_CheckPoint_C_UAID_74563CBA697EF6C402_1644486013": "Anchored Wilhelm",
    "AnclaBoss4__Desert___BP_CheckPoint_C_UAID_74563CBA697EF6C402_1644486013": "Post Wilhelm",
    "FinalBoss__Desert___BP_CheckPoint_C_UAID_74563CBA697EF6C402_1644486013": "Despair",
}

NAMES_PATH = tool_config.HERE / "library_names.json"


def _load_file_overrides() -> dict[str, str]:
    """Just what's actually in library_names.json -- i.e. renames beyond
    the baked-in DEFAULT_NAMES. Kept separate from load_name_overrides()
    so the file only ever grows by what someone actually typed, not a full
    copy of the defaults re-saved every time one thing is renamed."""
    try:
        return json.loads(NAMES_PATH.read_text())
    except Exception:
        return {}


def load_name_overrides() -> dict[str, str]:
    """Baked-in DEFAULT_NAMES, with anything in library_names.json (written
    by "Rename") layered on top -- so a rename always wins over the
    built-in default, and new zones can be named without needing a code
    change."""
    return {**DEFAULT_NAMES, **_load_file_overrides()}


def save_name_overrides(overrides: dict[str, str]) -> None:
    tool_config.write_hidden_text(NAMES_PATH, json.dumps(overrides, indent=2))


def scan_library(cfg: dict) -> list[Entry]:
    entries: list[Entry] = []

    captures_root = tool_config.captures_dir(cfg)
    if captures_root.exists():
        for zone_dir in sorted(p for p in captures_root.iterdir() if p.is_dir()):
            for sav in sorted(zone_dir.glob("*.sav")):
                entries.append(_build_entry(sav, zone_dir.name))

    # Group by zone and number entries only where a zone genuinely has more
    # than one distinct save (e.g. Ticktown, visited at several different
    # points in the story) -- a zone with just one save shows its plain
    # name, no "1 of 1" clutter. Numbered in the order they were actually
    # reached, not alphabetically.
    by_level: dict[str, list[Entry]] = {}
    for e in entries:
        by_level.setdefault(_extract_level(e.group), []).append(e)
    for level, group_entries in by_level.items():
        group_entries.sort(key=lambda e: e.captured_at or datetime.min)
        if len(group_entries) == 1:
            group_entries[0].display_group = level
        else:
            for i, e in enumerate(group_entries, start=1):
                e.display_group = f"{level} {i}"

    # Name overrides on top of the auto-generated names -- e.g. renaming a
    # generic "Boss2" to whatever that boss is actually called in-game.
    # Applied per-entry, so renaming one doesn't touch the numbering of
    # other entries sharing the same zone.
    overrides = load_name_overrides()
    for e in entries:
        if e.group in overrides:
            e.display_group = overrides[e.group]

    # Baseline order: when each save was actually created. Real capture
    # time, not route position -- a zone like Ticktown that's revisited
    # several times at genuinely different points in the story lands each
    # of those saves in its own correct place, rather than all of them
    # clustering together at Ticktown's first-ever appearance.
    entries.sort(key=lambda e: e.captured_at or datetime.min)

    # PINNED_FIRST on top of that baseline (see its definition).
    position = {group: i for i, group in enumerate(PINNED_FIRST)}
    pinned = [e for e in entries if e.group in position]
    rest = [e for e in entries if e.group not in position]
    pinned.sort(key=lambda e: position[e.group])
    entries = pinned + rest

    return entries


def _build_entry(sav: Path, group: str) -> Entry:
    shards = momento = None
    try:
        summary = gvas_lite.read_summary(sav)
        shards, momento = summary.shards, summary.momento
    except Exception:
        pass
    captured = tool_config.parse_timestamp(sav.stem)
    if captured is None:
        captured = datetime.fromtimestamp(sav.stat().st_mtime)
    return Entry(sav, group, group, captured, shards, momento)


class CenteredDialog(tk.Toplevel):
    """Shared scaffolding for every dialog in this app: dusk background,
    fixed size, centered over its parent (which may itself be another
    CenteredDialog -- Tk nests transient Toplevels fine), Escape and the
    window's own close button both route through the same handler. Cuts
    what used to be ~15 duplicated lines per dialog (UnlocksDialog,
    CosmeticsDialog, ShardsDialog, and the old one-off confirm dialog all
    hand-rolled this identically)."""

    def __init__(self, parent: tk.Misc, title: str, on_close=None):
        super().__init__(parent, bg=DUSK)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self._parent_window = parent
        close = on_close if on_close is not None else self.destroy
        self.protocol("WM_DELETE_WINDOW", close)
        self.bind("<Escape>", lambda _e: close())

    def show_modal(self):
        """Call once the dialog's body is fully built -- centers it over
        its parent (needs real widget sizes, hence the update_idletasks)
        and makes it modal."""
        self.update_idletasks()
        parent = self._parent_window
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        dw, dh = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")
        self.grab_set()


def confirm(
    parent: tk.Misc, headline: str, detail: str, note: str, confirm_text: str = "Confirm", skip: bool = False
) -> bool:
    """A themed yes/no confirm -- the native messagebox.askyesno renders as
    a plain unthemed system box that, at a glance, reads as an error rather
    than a normal confirm. Used before every action in this app that
    overwrites an active save (Load, Restore, and applying Unlocks/Outfit/
    Shards), so nothing writes to a live save without the user seeing
    exactly what's about to happen first.

    skip=True (from the "Skip confirmations" checkbox) bypasses the dialog
    entirely and just returns True -- the automatic backup taken before
    every write is what actually keeps this safe, the dialog itself is just
    a speed bump some users find tedious on repeat loads."""
    if skip:
        return True
    result = {"ok": False}

    def cancel():
        result["ok"] = False
        dialog.destroy()

    def accept():
        result["ok"] = True
        dialog.destroy()

    dialog = CenteredDialog(parent, f"{confirm_text}?", on_close=cancel)
    # Enter defaults to Cancel, not the destructive action -- there's no
    # native "focused button" affordance on a Canvas-based button, so this
    # is bound on the dialog itself instead.
    dialog.bind("<Return>", lambda _e: cancel())

    body = tk.Frame(dialog, bg=DUSK, padx=20, pady=16)
    body.pack(fill="both", expand=True)

    tk.Label(
        body, text=f"⚠  {headline}", bg=DUSK, fg=AMBER, font=("Segoe UI", 12, "bold"), justify="left"
    ).pack(anchor="w")
    tk.Label(body, text=detail, bg=DUSK, fg=INK, font=("Segoe UI", 10), justify="left").pack(
        anchor="w", pady=(10, 0)
    )
    tk.Label(
        body, text=note, bg=DUSK, fg=TEAL, font=("Segoe UI", 9), justify="left", wraplength=340
    ).pack(anchor="w", pady=(10, 0))

    btn_row = tk.Frame(body, bg=DUSK)
    btn_row.pack(fill="x", pady=(18, 0))
    AngledButton(btn_row, "Cancel", command=cancel, width=90, height=30, bg=DUSK).pack(side="right", padx=(8, 0))
    AngledButton(btn_row, confirm_text, style="primary", command=accept, width=110, height=30, bg=DUSK).pack(
        side="right"
    )

    dialog.show_modal()
    dialog.wait_window()
    return result["ok"]


class LoaderApp(tk.Tk):
    COLUMNS = ("group", "shards", "momento")
    HEADINGS = {
        "group": "Zone / Name",
        "shards": "Shards",
        "momento": "Story Progress",
    }

    def __init__(self):
        super().__init__()
        self.title("Duskfade Save Editor")
        self.geometry("900x560")
        self.minsize(720, 420)
        try:
            self.iconbitmap(str(tool_config.resource_path("duskfade.ico")))
        except Exception:
            pass  # missing/unsupported icon shouldn't block the app from starting

        self.cfg = tool_config.load_config()
        tool_config.ensure_seed_library(self.cfg)
        # Trims every slot's Backups\ folder down to backup_retention_count
        # right away -- covers a folder that grew large under an older
        # build (before pruning existed) or after lowering the retention
        # count by hand, not just backups made from this point forward.
        tool_config.prune_all_backups(self.cfg)
        self.entries: list[Entry] = []

        self._apply_theme()
        self._build_banner()
        self._build_top_bar()
        self._build_table()
        self._build_bottom_bar()
        self._build_hotkeys()
        self.refresh()

        self.update_info: updater.UpdateInfo | None = None
        updater.check_for_update_async(lambda info: self.after(0, self._show_update_banner, info))

    # ---------- UI construction ----------

    def _apply_theme(self):
        self.configure(bg=DUSK)
        body_font = ("Segoe UI", 10)
        bold_font = ("Segoe UI", 10, "bold")

        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=DUSK, foreground=INK, font=body_font)
        style.configure("TFrame", background=DUSK)
        style.configure("TLabel", background=DUSK, foreground=INK)
        style.configure("Dim.TLabel", background=DUSK, foreground=INK_DIM)

        style.configure(
            "TButton",
            background=PANEL_RAISED,
            foreground=INK,
            bordercolor=EDGE,
            lightcolor=PANEL_RAISED,
            darkcolor=PANEL_RAISED,
            padding=(10, 5),
            relief="flat",
            focuscolor=TEAL,
        )
        style.map(
            "TButton",
            background=[("active", EDGE), ("pressed", EDGE)],
            bordercolor=[("focus", TEAL)],
        )

        style.configure(
            "Accent.TButton",
            background=AMBER,
            foreground=DUSK,
            bordercolor=AMBER,
            lightcolor=AMBER,
            darkcolor=AMBER,
            padding=(10, 5),
            relief="flat",
            font=bold_font,
        )
        style.map(
            "Accent.TButton",
            background=[("active", AMBER_DIM), ("pressed", AMBER_DIM)],
            bordercolor=[("focus", AMBER_DIM)],
        )

        style.configure(
            "TEntry",
            fieldbackground=PANEL_RAISED,
            foreground=INK,
            bordercolor=EDGE,
            insertcolor=INK,
            lightcolor=PANEL_RAISED,
            darkcolor=PANEL_RAISED,
        )
        style.map("TEntry", bordercolor=[("focus", TEAL)])

        style.configure(
            "TCombobox",
            fieldbackground=PANEL_RAISED,
            background=PANEL_RAISED,
            foreground=INK,
            arrowcolor=TEAL,
            bordercolor=EDGE,
            lightcolor=PANEL_RAISED,
            darkcolor=PANEL_RAISED,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", PANEL_RAISED)],
            foreground=[("readonly", INK)],
            bordercolor=[("focus", TEAL)],
        )
        self.option_add("*TCombobox*Listbox.background", PANEL_RAISED)
        self.option_add("*TCombobox*Listbox.foreground", INK)
        self.option_add("*TCombobox*Listbox.selectBackground", TEAL_DIM)

        style.configure(
            "Treeview",
            background=PANEL,
            fieldbackground=PANEL,
            foreground=INK,
            bordercolor=EDGE,
            borderwidth=0,
            rowheight=26,
        )
        style.map(
            "Treeview",
            background=[("selected", TEAL_DIM)],
            foreground=[("selected", DUSK)],
        )
        style.configure(
            "Treeview.Heading",
            background=PANEL_RAISED,
            foreground=TEAL,
            bordercolor=EDGE,
            relief="flat",
            font=bold_font,
        )
        style.map("Treeview.Heading", background=[("active", EDGE)])

        style.configure(
            "Vertical.TScrollbar",
            background=PANEL_RAISED,
            troughcolor=DUSK,
            bordercolor=DUSK,
            arrowcolor=INK_MID,
            relief="flat",
        )

    def _build_banner(self):
        # A canvas rather than a Frame of Labels -- the key-art background
        # needs text drawn directly on top of it (create_text has no opaque
        # box behind it the way a Label would), not stacked in front of it.
        banner = tk.Canvas(self, height=100, bg=DUSK, highlightthickness=0)
        banner.pack(fill="x")
        self.banner_canvas = banner

        try:
            self.banner_img = tk.PhotoImage(file=str(tool_config.resource_path("banner_art.png")))
        except tk.TclError:
            self.banner_img = None
        self._banner_img_id = None
        if self.banner_img is not None:
            self._banner_img_id = banner.create_image(0, 0, image=self.banner_img, anchor="n")

        banner.create_text(
            12, 24, text="Duskfade Save Editor", fill=AMBER, font=("Segoe UI", 15, "bold"), anchor="w"
        )
        banner.create_text(
            12,
            48,
            text="Browse captured checkpoints, load one into a live slot, or edit unlocks and outfit directly.",
            fill=INK_DIM,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self._banner_credit_id = banner.create_text(
            0, 0, text="built by Zyrumi", fill=INK_DIM, font=("Segoe UI", 8), anchor="se"
        )
        banner.create_rectangle(0, 99, 0, 100, fill=EDGE, outline="", tags="hairline")
        banner.bind("<Configure>", self._on_banner_resize)

        self.update_btn = AngledButton(
            banner, "", style="primary", command=self._on_update_clicked, width=150, height=26, bg=DUSK,
            font=("Segoe UI", 9, "bold"),
        )
        # Hidden until an update is actually found (see _show_update_banner).

    def _on_banner_resize(self, event):
        banner = self.banner_canvas
        if self._banner_img_id is not None:
            # Shifted right of true center -- keeps the clock-tower glyph
            # out from behind the title/subtitle text on the left.
            banner.coords(self._banner_img_id, event.width / 2 + 90, 0)
        banner.coords(self._banner_credit_id, event.width - 8, event.height - 6)
        banner.coords("hairline", 0, event.height - 1, event.width, event.height)

    def _show_update_banner(self, info: updater.UpdateInfo):
        self.update_info = info
        self.update_btn.set_text(f"Update to {info.version}")
        self.update_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)

    def _on_update_clicked(self):
        if self.update_info is None:
            return
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Update available",
                f"{self.update_info.version} is available. You're running from source — "
                "update with `git pull` instead of the in-app updater.",
            )
            return
        self.update_btn.set_enabled(False)
        self.update_btn.set_text("Downloading...")
        updater.download_and_apply(
            self.update_info,
            on_progress=lambda frac: self.after(0, self._on_update_progress, frac),
            on_error=lambda msg: self.after(0, self._on_update_error, msg),
        )

    def _on_update_progress(self, frac: float):
        self.update_btn.set_text(f"Downloading... {int(frac * 100)}%")

    def _on_update_error(self, message: str):
        self.update_btn.set_enabled(True)
        self.update_btn.set_text(f"Update to {self.update_info.version}")
        messagebox.showerror("Update failed", f"Couldn't install the update:\n{message}")

    def _build_top_bar(self):
        bar = ttk.Frame(self, padding=(12, 10))
        bar.pack(fill="x")

        ttk.Label(bar, text="Live save folder:").pack(side="left")
        self.save_dir_var = tk.StringVar(value=self.cfg["save_dir"])
        entry = ttk.Entry(bar, textvariable=self.save_dir_var, width=52)
        entry.pack(side="left", padx=(6, 6))
        AngledButton(bar, "Browse...", command=self._browse_save_dir, width=90, height=28).pack(side="left")

        ttk.Label(bar, text="   Active slot:").pack(side="left", padx=(14, 6))
        self.slot_var = tk.StringVar()
        self.slot_combo = ttk.Combobox(bar, textvariable=self.slot_var, width=16, state="readonly")
        self.slot_combo.pack(side="left")
        self.slot_combo.bind("<<ComboboxSelected>>", lambda e: self._persist_slot())

        self.pin_var = tk.BooleanVar()
        ttk.Checkbutton(
            bar, text="Lock default slot", variable=self.pin_var, command=self._toggle_pin
        ).pack(side="left", padx=(10, 0))

        self.skip_confirm_var = tk.BooleanVar(value=self.cfg.get("skip_confirm", False))
        ttk.Checkbutton(
            bar, text="Skip confirmations", variable=self.skip_confirm_var, command=self._toggle_skip_confirm
        ).pack(side="left", padx=(10, 0))

    def _build_table(self):
        frame = ttk.Frame(self, padding=(12, 4))
        frame.pack(fill="both", expand=True)

        # Fixed story order (see scan_library) -- not user-sortable, so
        # headings are static labels, not click targets.
        self.tree = ttk.Treeview(frame, columns=self.COLUMNS, show="headings", selectmode="browse")
        for col in self.COLUMNS:
            self.tree.heading(col, text=self.HEADINGS[col])
            width = 220 if col == "group" else 110
            self.tree.column(col, width=width, anchor="w")
        self.tree.tag_configure("odd", background=PANEL)
        self.tree.tag_configure("even", background=PANEL_RAISED)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_bottom_bar(self):
        bar = ttk.Frame(self, padding=12)
        bar.pack(fill="x")
        AngledButton(bar, "Rename checkpoint", command=self._rename_selected, width=170, height=32).pack(
            side="left"
        )
        AngledButton(bar, "Unlocks", command=self._open_unlocks, width=100, height=32).pack(
            side="left", padx=(8, 0)
        )
        AngledButton(bar, "Outfit", command=self._open_cosmetics, width=90, height=32).pack(
            side="left", padx=(8, 0)
        )
        AngledButton(bar, "Shards", command=self._open_shards, width=90, height=32).pack(
            side="left", padx=(8, 0)
        )
        AngledButton(
            bar, "Load Selected Save", style="primary", command=self._load_selected, width=170, height=32
        ).pack(side="right")
        AngledButton(bar, "Launch Duskfade", command=self._launch_game, width=140, height=32).pack(
            side="right", padx=(0, 8)
        )

        hint = ttk.Frame(self, padding=(12, 0, 12, 8))
        hint.pack(fill="x")
        ttk.Label(
            hint,
            text="Hotkeys: Enter / double-click a row = Load  •  Ctrl+L = Load  •  "
            "Ctrl+U = Unlocks  •  Ctrl+O = Outfit  •  Ctrl+G = Shards",
            style="Dim.TLabel",
            font=("Segoe UI", 8),
        ).pack(side="left")

    def _build_hotkeys(self):
        # Quick-load a row directly from the table without reaching for the
        # button -- the friction the "Skip confirmations" checkbox above
        # doesn't address on its own.
        self.tree.bind("<Return>", lambda _e: self._load_selected())
        self.tree.bind("<Double-1>", lambda _e: self._load_selected())

        # Global shortcuts so Load/Unlocks/Outfit/Shards don't need mouse
        # travel to the bottom bar at all, once you know them.
        self.bind_all("<Control-l>", lambda _e: self._load_selected())
        self.bind_all("<Control-u>", lambda _e: self._open_unlocks())
        self.bind_all("<Control-o>", lambda _e: self._open_cosmetics())
        self.bind_all("<Control-g>", lambda _e: self._open_shards())

    # ---------- data ----------

    def refresh(self):
        self.cfg = tool_config.load_config()
        self.entries = scan_library(self.cfg)

        save_dir = Path(self.save_dir_var.get())
        slots = sorted(p.name for p in save_dir.glob(self.cfg["slot_pattern"])) if save_dir.exists() else []
        self.slot_combo["values"] = slots

        # A pinned slot always wins -- that's the whole point of locking one
        # in, so it can't drift back to whatever's alphabetically first.
        pinned = self.cfg.get("pinned_target_slot")
        if pinned in slots:
            self.slot_var.set(pinned)
            self.pin_var.set(True)
        else:
            self.pin_var.set(False)
            wanted = self.cfg.get("last_target_slot")
            if wanted in slots:
                self.slot_var.set(wanted)
            elif slots:
                self.slot_var.set(slots[0])
            else:
                self.slot_var.set("")
        self.slot_combo.configure(state="disabled" if self.pin_var.get() else "readonly")

        self._render_rows()

    def _render_rows(self, select_path: Path | None = None):
        self.tree.delete(*self.tree.get_children())
        # self.entries is already in fixed story order from scan_library --
        # no re-sorting here.
        for i, e in enumerate(self.entries):
            self.tree.insert(
                "",
                "end",
                iid=str(e.path),
                tags=("even" if i % 2 == 0 else "odd",),
                values=(
                    e.display_group,
                    e.shards if e.shards is not None else "",
                    e.momento if e.momento is not None else "",
                ),
            )
        if select_path is not None:
            iid = str(select_path)
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.see(iid)

    def _rename_selected(self):
        e = self._selected_entry()
        if not e:
            messagebox.showinfo("Nothing selected", "Select a save in the list first.")
            return
        new_name = simpledialog.askstring("Rename", "Display name for this save:", initialvalue=e.display_group)
        if not new_name or new_name == e.display_group:
            return
        overrides = _load_file_overrides()
        overrides[e.group] = new_name
        save_name_overrides(overrides)
        e.display_group = new_name
        self._render_rows(select_path=e.path)

    # ---------- actions ----------

    def _selected_entry(self) -> Entry | None:
        sel = self.tree.selection()
        if not sel:
            return None
        path = Path(sel[0])
        return next((e for e in self.entries if e.path == path), None)

    def _browse_save_dir(self):
        chosen = filedialog.askdirectory(initialdir=self.save_dir_var.get())
        if chosen:
            self.save_dir_var.set(chosen)
            self.cfg["save_dir"] = chosen
            tool_config.save_config(self.cfg)
            self.refresh()

    def _persist_slot(self):
        self.cfg["last_target_slot"] = self.slot_var.get()
        tool_config.save_config(self.cfg)

    def _toggle_pin(self):
        if self.pin_var.get():
            self.cfg["pinned_target_slot"] = self.slot_var.get()
        else:
            self.cfg["pinned_target_slot"] = None
        tool_config.save_config(self.cfg)
        self.slot_combo.configure(state="disabled" if self.pin_var.get() else "readonly")

    def _toggle_skip_confirm(self):
        self.cfg["skip_confirm"] = self.skip_confirm_var.get()
        tool_config.save_config(self.cfg)

    def _launch_game(self):
        os.startfile(f"steam://rungameid/{STEAM_APP_ID}")

    def _require_active_save(self) -> Path | None:
        """The active-slot guard shared by every dialog opener below: no
        slot selected, or the slot file doesn't exist yet (no in-game
        checkpoint reached), both bail out with an explanatory message
        instead of opening a dialog that has nothing to operate on."""
        active = self._active_slot_path()
        if active is None:
            return None
        if not active.exists():
            messagebox.showinfo(
                "No save yet", f"{active.name} doesn't exist yet -- reach the first in-game checkpoint first."
            )
            return None
        return active

    def _open_unlocks(self):
        active = self._require_active_save()
        if active is not None:
            UnlocksDialog(self, active)

    def _open_cosmetics(self):
        active = self._require_active_save()
        if active is not None:
            CosmeticsDialog(self, active)

    def _open_shards(self):
        active = self._require_active_save()
        if active is not None:
            ShardsDialog(self, active)

    def _active_slot_path(self) -> Path | None:
        slot = self.slot_var.get()
        if not slot:
            messagebox.showerror("No active slot", "No DFSlot_*.sav files found in the live save folder.")
            return None
        return Path(self.save_dir_var.get()) / slot

    def _load_selected(self):
        e = self._selected_entry()
        if not e:
            messagebox.showinfo("Nothing selected", "Select a save in the list first.")
            return
        active = self._active_slot_path()
        if active is None:
            return

        if not confirm(
            self,
            headline=f"This will overwrite {active.name}",
            detail=f"Replacing it with:  {e.display_group}\n{e.path.name}",
            note="Your current save is backed up first, automatically — nothing is lost.",
            confirm_text="Overwrite",
            skip=self.skip_confirm_var.get(),
        ):
            return

        active.parent.mkdir(parents=True, exist_ok=True)
        if active.exists():
            tool_config.backup_active_save(active, "load", self.cfg)
        tool_config.atomic_copy(e.path, active)

        messagebox.showinfo(
            "Loaded", f"'{e.display_group}' is now active in {active.name}.\n\nRestart/reload in-game to pick it up."
        )


class UnlocksDialog(CenteredDialog):
    """Toggle any ability/gadget/upgrade-tier flag directly on the active
    save, bypassing whatever it normally takes to earn it in-game. Operates
    on the live active slot (same file "Load Selected Save" writes to), not
    whatever's selected in the library table -- so it always affects the
    save you're about to actually play."""

    def __init__(self, parent: LoaderApp, active_path: Path):
        super().__init__(parent, "Abilities & Upgrades")
        self.parent_app = parent
        self.active_path = active_path

        current = unlocks.read_unlock_values(active_path)
        self.vars: dict[str, list[tk.BooleanVar]] = {}

        body = tk.Frame(self, bg=DUSK, padx=20, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="Abilities & Upgrades",
            bg=DUSK,
            fg=AMBER,
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        tk.Label(
            body,
            text=f"Toggle anything on or off directly -- no need to purchase/unlock it first.\nApplies to {active_path.name}.",
            bg=DUSK,
            fg=INK_DIM,
            font=("Segoe UI", 9),
            justify="left",
        ).pack(anchor="w", pady=(4, 12))

        for name, group_label, slot_labels in unlocks.UNLOCK_GROUPS:
            section = tk.Frame(body, bg=DUSK)
            section.pack(fill="x", pady=(0, 10))
            tk.Label(section, text=group_label, bg=DUSK, fg=TEAL, font=("Segoe UI", 10, "bold")).pack(
                anchor="w"
            )
            row = tk.Frame(section, bg=DUSK)
            row.pack(fill="x", pady=(2, 0))
            existing = current.get(name, [False] * len(slot_labels))
            slot_vars = []
            for slot_label, is_set in zip(slot_labels, existing):
                var = tk.BooleanVar(value=is_set)
                slot_vars.append(var)
                ttk.Checkbutton(row, text=slot_label, variable=var).pack(side="left", padx=(0, 16))
            self.vars[name] = slot_vars

        tk.Frame(body, bg=EDGE, height=1).pack(fill="x", pady=(2, 12))

        btn_row = tk.Frame(body, bg=DUSK)
        btn_row.pack(fill="x")
        AngledButton(btn_row, "Select All", command=self._select_all, width=100, height=28, bg=DUSK).pack(
            side="left"
        )
        AngledButton(btn_row, "Select None", command=self._select_none, width=100, height=28, bg=DUSK).pack(
            side="left", padx=(8, 0)
        )
        AngledButton(btn_row, "Cancel", command=self.destroy, width=90, height=28, bg=DUSK).pack(
            side="right"
        )
        AngledButton(btn_row, "Apply", style="primary", command=self._apply, width=100, height=28, bg=DUSK).pack(
            side="right", padx=(0, 8)
        )

        self.show_modal()

    def _select_all(self):
        for slot_vars in self.vars.values():
            for var in slot_vars:
                var.set(True)

    def _select_none(self):
        for slot_vars in self.vars.values():
            for var in slot_vars:
                var.set(False)

    def _apply(self):
        values = {name: [var.get() for var in slot_vars] for name, slot_vars in self.vars.items()}
        if not confirm(
            self,
            headline=f"Apply changes to {self.active_path.name}?",
            detail="This overwrites your active save's ability/gadget/upgrade unlock state.",
            note="Your current save is backed up first, automatically — nothing is lost.",
            confirm_text="Apply",
            skip=self.parent_app.skip_confirm_var.get(),
        ):
            return
        try:
            unlocks.apply_unlock_values(self.active_path, values)
        except Exception as exc:
            messagebox.showerror("Couldn't apply", f"Failed to write changes:\n{exc}")
            return
        self.destroy()
        messagebox.showinfo(
            "Applied",
            f"Updated {self.active_path.name}. Your previous save was backed up automatically.\n\n"
            "Retry/reload in-game to pick up the changes.",
        )


class CosmeticsDialog(CenteredDialog):
    """Force the equipped outfit / outfit color / sword skin color on the
    active save, bypassing whatever it normally takes to own them. Outfit
    and outfit color are linked -- switching outfit repopulates the color
    dropdown with that outfit's own variant names and resets the choice to
    Default, since color index 5 means a different thing per outfit.
    Weapon (sword) color is a separate, independent equipment slot."""

    def __init__(self, parent: LoaderApp, active_path: Path):
        super().__init__(parent, "Outfit")
        self.parent_app = parent
        self.active_path = active_path

        current = cosmetics.read_cosmetic_values(active_path)
        self.outfit_index = current.get("IndexSkin") or 0
        self.outfit_color_index = current.get("IndexRecolor") or 0
        self.weapon_color_index = current.get("IndexRecolorEspada") or 0

        body = tk.Frame(self, bg=DUSK, padx=20, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Outfit", bg=DUSK, fg=AMBER, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(
            body,
            text=f"Force any outfit or color, owned or not.\nApplies to {active_path.name}.",
            bg=DUSK,
            fg=INK_DIM,
            font=("Segoe UI", 9),
            justify="left",
        ).pack(anchor="w", pady=(4, 14))

        self.outfit_combo = self._build_row(body, "Outfit")
        self.outfit_color_combo = self._build_row(body, "Outfit Color")
        self.weapon_color_combo = self._build_row(body, "Sword Skin Color")

        self.outfit_combo["values"] = [cosmetic_names.outfit_label(i) for i in range(cosmetic_names.outfit_count())]
        self.outfit_combo.current(self.outfit_index)
        self.weapon_color_combo["values"] = [
            cosmetic_names.weapon_color_label(i) for i in range(cosmetic_names.weapon_color_count())
        ]
        self.weapon_color_combo.current(self.weapon_color_index)
        self._refresh_outfit_color_combo(select=self.outfit_color_index)

        self.outfit_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_outfit_color_combo(select=0))

        tk.Frame(body, bg=EDGE, height=1).pack(fill="x", pady=(6, 12))

        btn_row = tk.Frame(body, bg=DUSK)
        btn_row.pack(fill="x")
        AngledButton(btn_row, "Cancel", command=self.destroy, width=90, height=28, bg=DUSK).pack(side="right")
        AngledButton(btn_row, "Apply", style="primary", command=self._apply, width=100, height=28, bg=DUSK).pack(
            side="right", padx=(0, 8)
        )

        self.show_modal()

    def _build_row(self, parent, label_text: str) -> ttk.Combobox:
        row = tk.Frame(parent, bg=DUSK)
        row.pack(fill="x", pady=(0, 10))
        tk.Label(row, text=label_text, bg=DUSK, fg=TEAL, font=("Segoe UI", 9, "bold"), width=14, anchor="w").pack(
            side="left"
        )
        combo = ttk.Combobox(row, state="readonly", width=22)
        combo.pack(side="left")
        return combo

    def _refresh_outfit_color_combo(self, select: int):
        outfit_index = self.outfit_combo.current()
        count = cosmetic_names.outfit_color_count(outfit_index)
        self.outfit_color_combo["values"] = [
            cosmetic_names.outfit_color_label(outfit_index, i) for i in range(count)
        ]
        self.outfit_color_combo.current(min(select, count - 1))

    def _apply(self):
        values = {
            "IndexSkin": self.outfit_combo.current(),
            "IndexRecolor": self.outfit_color_combo.current(),
            "IndexRecolorEspada": self.weapon_color_combo.current(),
        }
        if not confirm(
            self,
            headline=f"Apply changes to {self.active_path.name}?",
            detail="This overwrites your active save's outfit, outfit color, and sword skin color.",
            note="Your current save is backed up first, automatically — nothing is lost.",
            confirm_text="Apply",
            skip=self.parent_app.skip_confirm_var.get(),
        ):
            return
        try:
            cosmetics.apply_cosmetic_values(self.active_path, values)
        except Exception as exc:
            messagebox.showerror("Couldn't apply", f"Failed to write changes:\n{exc}")
            return
        self.destroy()
        messagebox.showinfo(
            "Applied",
            f"Updated {self.active_path.name}. Your previous save was backed up automatically.\n\n"
            "Retry/reload in-game to pick it up (walking between zones won't).",
        )


class ShardsDialog(CenteredDialog):
    """Set the exact shard (currency) count on the active save directly."""

    def __init__(self, parent: LoaderApp, active_path: Path):
        super().__init__(parent, "Shards")
        self.parent_app = parent
        self.active_path = active_path

        current = shards.read_shards(active_path)

        body = tk.Frame(self, bg=DUSK, padx=20, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Shards", bg=DUSK, fg=AMBER, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(
            body,
            text=f"Set the exact shard count on your active save.\nApplies to {active_path.name}.",
            bg=DUSK,
            fg=INK_DIM,
            font=("Segoe UI", 9),
            justify="left",
        ).pack(anchor="w", pady=(4, 14))

        row = tk.Frame(body, bg=DUSK)
        row.pack(fill="x")
        tk.Label(row, text="Shards", bg=DUSK, fg=TEAL, font=("Segoe UI", 9, "bold"), width=14, anchor="w").pack(
            side="left"
        )
        self.shards_var = tk.StringVar(value=str(current))
        entry = ttk.Entry(row, textvariable=self.shards_var, width=24)
        entry.pack(side="left")
        entry.focus_set()
        entry.select_range(0, "end")

        tk.Frame(body, bg=EDGE, height=1).pack(fill="x", pady=(14, 12))

        btn_row = tk.Frame(body, bg=DUSK)
        btn_row.pack(fill="x")
        AngledButton(btn_row, "Cancel", command=self.destroy, width=90, height=28, bg=DUSK).pack(side="right")
        AngledButton(btn_row, "Apply", style="primary", command=self._apply, width=100, height=28, bg=DUSK).pack(
            side="right", padx=(0, 8)
        )

        self.bind("<Return>", lambda _e: self._apply())
        self.show_modal()

    def _apply(self):
        raw = self.shards_var.get().strip()
        try:
            value = int(raw)
        except ValueError:
            messagebox.showerror("Invalid value", "Shards must be a whole number.")
            return
        if value < 0 or value > 2_147_483_647:
            messagebox.showerror("Invalid value", "Shards must be between 0 and 2,147,483,647.")
            return
        if not confirm(
            self,
            headline=f"Apply changes to {self.active_path.name}?",
            detail=f"This sets your active save's shard count to {value:,}.",
            note="Your current save is backed up first, automatically — nothing is lost.",
            confirm_text="Apply",
            skip=self.parent_app.skip_confirm_var.get(),
        ):
            return
        try:
            shards.apply_shards(self.active_path, value)
        except Exception as exc:
            messagebox.showerror("Couldn't apply", f"Failed to write changes:\n{exc}")
            return
        self.destroy()
        messagebox.showinfo(
            "Applied",
            f"Updated {self.active_path.name}. Your previous save was backed up automatically.\n\n"
            "Retry/reload in-game to pick it up (walking between zones won't).",
        )


if __name__ == "__main__":
    app = LoaderApp()
    app.mainloop()
