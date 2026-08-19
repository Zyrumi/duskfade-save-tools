"""
Duskfade Save Loader
---------------------
Successor to "Zyrumi's Sheepy Loader" — browse a library of saved game
states (auto-captured load zones/bosses from auto_save_copier.py, plus your
own manually-saved spots) and inject any of them into a live save slot.

Your current save is always backed up automatically before anything is
overwritten, so loading a library save is non-destructive.

Run via run_save_loader.bat, or `python save_loader.py`.
"""
from __future__ import annotations

import json
import os
import shutil
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


def _parse_timestamp(stem: str) -> datetime | None:
    try:
        return datetime.strptime(stem, "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        return None


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
    captured = _parse_timestamp(sav.stem)
    if captured is None:
        captured = datetime.fromtimestamp(sav.stat().st_mtime)
    return Entry(sav, group, group, captured, shards, momento)


class LoaderApp(tk.Tk):
    COLUMNS = ("group", "shards", "momento")
    HEADINGS = {
        "group": "Zone / Name",
        "shards": "Shards",
        "momento": "Story Progress",
    }

    def __init__(self):
        super().__init__()
        self.title("Duskfade Save Loader")
        self.geometry("900x560")
        self.minsize(720, 420)
        try:
            self.iconbitmap(str(tool_config.resource_path("duskfade.ico")))
        except Exception:
            pass  # missing/unsupported icon shouldn't block the app from starting

        self.cfg = tool_config.load_config()
        tool_config.ensure_seed_library(self.cfg)
        self.entries: list[Entry] = []

        self._apply_theme()
        self._build_banner()
        self._build_top_bar()
        self._build_table()
        self._build_bottom_bar()
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
        banner = tk.Frame(self, bg=DUSK)
        banner.pack(fill="x")
        tk.Label(
            banner,
            text="Duskfade Save Loader",
            bg=DUSK,
            fg=AMBER,
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(
            banner,
            text="Browse captured checkpoints and your own saved spots, then inject one into a live slot.",
            bg=DUSK,
            fg=INK_DIM,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=12, pady=(0, 8))
        tk.Label(
            banner,
            text="built by Zyrumi",
            bg=DUSK,
            fg=INK_DIM,
            font=("Segoe UI", 8),
        ).place(relx=1.0, rely=1.0, anchor="se", x=-8, y=-6)
        tk.Frame(banner, bg=EDGE, height=1).pack(fill="x")

        self.update_btn = AngledButton(
            banner, "", style="primary", command=self._on_update_clicked, width=150, height=26, bg=DUSK,
            font=("Segoe UI", 9, "bold"),
        )
        # Hidden until an update is actually found (see _show_update_banner).

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
        AngledButton(bar, "Unlocks...", command=self._open_unlocks, width=110, height=32).pack(
            side="left", padx=(8, 0)
        )
        AngledButton(bar, "Outfit...", command=self._open_cosmetics, width=100, height=32).pack(
            side="left", padx=(8, 0)
        )
        AngledButton(
            bar, "Load Selected Save", style="primary", command=self._load_selected, width=170, height=32
        ).pack(side="right")
        AngledButton(bar, "Launch Duskfade", command=self._launch_game, width=140, height=32).pack(
            side="right", padx=(0, 8)
        )

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

    def _launch_game(self):
        os.startfile(f"steam://rungameid/{STEAM_APP_ID}")

    def _open_unlocks(self):
        active = self._active_slot_path()
        if active is None:
            return
        if not active.exists():
            messagebox.showinfo(
                "No save yet", f"{active.name} doesn't exist yet -- reach the first in-game checkpoint first."
            )
            return
        UnlocksDialog(self, active)

    def _open_cosmetics(self):
        active = self._active_slot_path()
        if active is None:
            return
        if not active.exists():
            messagebox.showinfo(
                "No save yet", f"{active.name} doesn't exist yet -- reach the first in-game checkpoint first."
            )
            return
        CosmeticsDialog(self, active)

    def _active_slot_path(self) -> Path | None:
        slot = self.slot_var.get()
        if not slot:
            messagebox.showerror("No active slot", "No DFSlot_*.sav files found in the live save folder.")
            return None
        return Path(self.save_dir_var.get()) / slot

    def _confirm_overwrite(self, active_name: str, incoming_label: str, incoming_filename: str) -> bool:
        """A themed stand-in for messagebox.askyesno -- the native dialog
        renders as a plain unthemed system box that, at a glance, reads as
        an error rather than a normal confirm. This makes "you're about to
        overwrite X" unmistakable: a bold warning-colored headline, the
        swap spelled out, and a clearly separated reassurance that it's
        backed up first."""
        result = {"ok": False}
        dialog = tk.Toplevel(self, bg=DUSK)
        dialog.title("Overwrite active save?")
        dialog.resizable(False, False)
        dialog.transient(self)

        body = tk.Frame(dialog, bg=DUSK, padx=20, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text=f"⚠  This will overwrite {active_name}",
            bg=DUSK,
            fg=AMBER,
            font=("Segoe UI", 12, "bold"),
            justify="left",
        ).pack(anchor="w")

        tk.Label(
            body,
            text=f"Replacing it with:  {incoming_label}\n{incoming_filename}",
            bg=DUSK,
            fg=INK,
            font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

        tk.Label(
            body,
            text="Your current save is backed up first, automatically — nothing is lost.",
            bg=DUSK,
            fg=TEAL,
            font=("Segoe UI", 9),
            justify="left",
            wraplength=340,
        ).pack(anchor="w", pady=(10, 0))

        btn_row = tk.Frame(body, bg=DUSK)
        btn_row.pack(fill="x", pady=(18, 0))

        def cancel():
            result["ok"] = False
            dialog.destroy()

        def confirm():
            result["ok"] = True
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.bind("<Escape>", lambda _e: cancel())
        # Enter defaults to Cancel, not the destructive action -- there's no
        # native "focused button" affordance on a Canvas-based button, so
        # this is bound on the dialog itself instead.
        dialog.bind("<Return>", lambda _e: cancel())

        AngledButton(btn_row, "Cancel", command=cancel, width=90, height=30, bg=DUSK).pack(side="right", padx=(8, 0))
        AngledButton(btn_row, "Overwrite", style="primary", command=confirm, width=110, height=30, bg=DUSK).pack(
            side="right"
        )

        dialog.update_idletasks()
        px, py = self.winfo_rootx(), self.winfo_rooty()
        pw, ph = self.winfo_width(), self.winfo_height()
        dw, dh = dialog.winfo_width(), dialog.winfo_height()
        dialog.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")

        dialog.grab_set()
        self.wait_window(dialog)
        return result["ok"]

    def _load_selected(self):
        e = self._selected_entry()
        if not e:
            messagebox.showinfo("Nothing selected", "Select a save in the list first.")
            return
        active = self._active_slot_path()
        if active is None:
            return

        if not self._confirm_overwrite(
            active_name=active.name,
            incoming_label=e.display_group,
            incoming_filename=e.path.name,
        ):
            return

        if active.exists():
            backup_dir = Path(self.cfg["backups_dir"]) / active.stem
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            shutil.copy2(active, backup_dir / f"{stamp}_before_load.sav")

        active.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(e.path, active)

        messagebox.showinfo(
            "Loaded", f"'{e.display_group}' is now active in {active.name}.\n\nRestart/reload in-game to pick it up."
        )


class UnlocksDialog(tk.Toplevel):
    """Toggle any ability/gadget/upgrade-tier flag directly on the active
    save, bypassing whatever it normally takes to earn it in-game. Operates
    on the live active slot (same file "Load Selected Save" writes to), not
    whatever's selected in the library table -- so it always affects the
    save you're about to actually play."""

    def __init__(self, parent: LoaderApp, active_path: Path):
        super().__init__(parent, bg=DUSK)
        self.parent_app = parent
        self.active_path = active_path
        self.title("Abilities & Upgrades")
        self.resizable(False, False)
        self.transient(parent)

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

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        dw, dh = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")
        self.grab_set()

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


class CosmeticsDialog(tk.Toplevel):
    """Force the equipped outfit / outfit color / sword skin color on the
    active save, bypassing whatever it normally takes to own them. Outfit
    and outfit color are linked -- switching outfit repopulates the color
    dropdown with that outfit's own variant names and resets the choice to
    Default, since color index 5 means a different thing per outfit.
    Weapon (sword) color is a separate, independent equipment slot."""

    def __init__(self, parent: LoaderApp, active_path: Path):
        super().__init__(parent, bg=DUSK)
        self.active_path = active_path
        self.title("Outfit")
        self.resizable(False, False)
        self.transient(parent)

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

        self.outfit_combo = self._build_row(body, "Outfit", self._rename_outfit)
        self.outfit_color_combo = self._build_row(body, "Outfit Color", self._rename_outfit_color)
        self.weapon_color_combo = self._build_row(body, "Sword Skin Color", self._rename_weapon_color)

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

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        dw, dh = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")
        self.grab_set()

    def _build_row(self, parent, label_text: str, rename_command) -> ttk.Combobox:
        row = tk.Frame(parent, bg=DUSK)
        row.pack(fill="x", pady=(0, 10))
        tk.Label(row, text=label_text, bg=DUSK, fg=TEAL, font=("Segoe UI", 9, "bold"), width=14, anchor="w").pack(
            side="left"
        )
        combo = ttk.Combobox(row, state="readonly", width=22)
        combo.pack(side="left", padx=(0, 8))
        AngledButton(row, "Rename", command=rename_command, width=80, height=26, bg=DUSK).pack(side="left")
        return combo

    def _refresh_outfit_color_combo(self, select: int):
        outfit_index = self.outfit_combo.current()
        count = cosmetic_names.outfit_color_count(outfit_index)
        self.outfit_color_combo["values"] = [
            cosmetic_names.outfit_color_label(outfit_index, i) for i in range(count)
        ]
        self.outfit_color_combo.current(min(select, count - 1))

    def _rename_outfit(self):
        i = self.outfit_combo.current()
        if i < 0:
            return
        new_label = simpledialog.askstring("Rename outfit", "Display name:", initialvalue=self.outfit_combo.get())
        if not new_label:
            return
        cosmetic_names.rename_outfit(i, new_label)
        values = list(self.outfit_combo["values"])
        values[i] = new_label
        self.outfit_combo["values"] = values
        self.outfit_combo.current(i)

    def _rename_outfit_color(self):
        outfit_index = self.outfit_combo.current()
        i = self.outfit_color_combo.current()
        if i < 0:
            return
        new_label = simpledialog.askstring(
            "Rename color", "Display name:", initialvalue=self.outfit_color_combo.get()
        )
        if not new_label:
            return
        cosmetic_names.rename_outfit_color(outfit_index, i, new_label)
        values = list(self.outfit_color_combo["values"])
        values[i] = new_label
        self.outfit_color_combo["values"] = values
        self.outfit_color_combo.current(i)

    def _rename_weapon_color(self):
        i = self.weapon_color_combo.current()
        if i < 0:
            return
        new_label = simpledialog.askstring(
            "Rename weapon color", "Display name:", initialvalue=self.weapon_color_combo.get()
        )
        if not new_label:
            return
        cosmetic_names.rename_weapon_color(i, new_label)
        values = list(self.weapon_color_combo["values"])
        values[i] = new_label
        self.weapon_color_combo["values"] = values
        self.weapon_color_combo.current(i)

    def _apply(self):
        values = {
            "IndexSkin": self.outfit_combo.current(),
            "IndexRecolor": self.outfit_color_combo.current(),
            "IndexRecolorEspada": self.weapon_color_combo.current(),
        }
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


if __name__ == "__main__":
    app = LoaderApp()
    app.mainloop()
