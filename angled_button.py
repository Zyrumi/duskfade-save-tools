"""A Canvas-based button shaped like the website's CTA buttons -- a
slanted parallelogram (matching the site's clip-path:
polygon(0 0, calc(100% - 10px) 0, 100% 100%, 10px 100%)) instead of a
plain rounded rectangle, in the same amber/teal/dusk palette."""
from __future__ import annotations

import tkinter as tk

DUSK = "#1b1626"
PANEL_RAISED = "#2c2438"
EDGE = "#3c3350"
AMBER = "#e8935a"
AMBER_DIM = "#b97245"
TEAL_DIM = "#3d8f88"
INK = "#f0e6d8"
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
            return PANEL_RAISED, INK_DIM, EDGE
        if self.style == "primary":
            fill = AMBER_DIM if self._hover else AMBER
            return fill, DUSK, fill
        fill = EDGE if self._hover else PANEL_RAISED
        outline = TEAL_DIM if self._hover else EDGE
        return fill, INK, outline

    def _draw(self):
        self.delete("all")
        w = int(str(self["width"]))
        h = int(str(self["height"]))
        cut = min(14, w // 6)
        fill, text_color, outline = self._colors()
        self.create_polygon(0, 0, w - cut, 0, w, h, cut, h, fill=fill, outline=outline, width=1)
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
