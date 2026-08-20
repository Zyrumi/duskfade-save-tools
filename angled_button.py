"""A Canvas-based button with two corners notched off (top-left, bottom-
right) -- matching the hud-panel clip-path used across the site/tooling
redesign (polygon(10px 0, 100% 0, 100% calc(100% - 10px),
calc(100% - 10px) 100%, 0 100%, 0 10px)) instead of a plain rounded
rectangle, in the same amber/teal/dusk palette."""
from __future__ import annotations

import tkinter as tk

DUSK = "#1b1626"
PANEL_RAISED = "#2c2438"
EDGE = "#3c3350"
AMBER = "#e8935a"
AMBER_DIM = "#b97245"
AMBER_GLOW = "#f2a877"
TEAL_DIM = "#3d8f88"
INK = "#f0e6d8"
INK_MID = "#c7bcd4"
INK_DIM = "#9184a3"


class AngledButton(tk.Canvas):
    def __init__(
        self,
        parent,
        text: str,
        command=None,
        style: str = "secondary",  # "primary" or "secondary"
        width: int = 150,
        height: int = 32,
        font=("Segoe UI", 10, "bold"),
        **kwargs,
    ):
        # Don't introspect parent["bg"] -- ttk.Frame containers (used
        # throughout this app) don't expose a plain "bg" option the way
        # tk widgets do, so that lookup would raise. Callers placing a
        # button on a non-default background should pass bg= explicitly.
        bg = kwargs.pop("bg", None) or DUSK
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, cursor="hand2", **kwargs)
        self.command = command
        self.style = style
        self.text = text
        self.font = font
        self.enabled = True
        self._hover = False
        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _colors(self):
        if not self.enabled:
            return PANEL_RAISED, INK_DIM, EDGE, 1
        if self.style == "primary":
            # No true gradient fill on a stdlib Canvas -- a lighter,
            # thicker outline on hover stands in for the site's
            # box-shadow glow instead.
            outline = AMBER_GLOW if self._hover else AMBER_DIM
            width = 2 if self._hover else 1
            return AMBER, DUSK, outline, width
        outline = TEAL_DIM if self._hover else EDGE
        text_color = INK if self._hover else INK_MID
        return PANEL_RAISED, text_color, outline, 1

    def _draw(self):
        self.delete("all")
        w = int(str(self["width"]))
        h = int(str(self["height"]))
        cut = min(10, h // 3, w // 6)
        fill, text_color, outline, outline_width = self._colors()
        self.create_polygon(
            cut, 0, w, 0, w, h - cut, w - cut, h, 0, h, 0, cut,
            fill=fill, outline=outline, width=outline_width,
        )
        self.create_text(w / 2, h / 2, text=self.text, fill=text_color, font=self.font)

    def _on_enter(self, _e):
        if self.enabled:
            self._hover = True
            self._draw()

    def _on_leave(self, _e):
        self._hover = False
        self._draw()

    def _on_click(self, _e):
        if self.enabled and self.command:
            self.command()

    def set_text(self, text: str):
        self.text = text
        self._draw()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()
