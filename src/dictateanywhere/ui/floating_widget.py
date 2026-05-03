"""
Floating draggable microphone button.

An always-on-top, semi-transparent Tkinter window that shows the current
dictation state and lets the user toggle recording with a single click.

The window has no title bar (overrideredirect=True) and can be dragged
anywhere on screen. Its position is saved to config on every move.
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ── Visual constants ──────────────────────────────────────────────────────────
_IDLE_BG     = "#4A90D9"   # blue
_ACTIVE_BG   = "#E74C3C"   # red (recording)
_LOADING_BG  = "#F39C12"   # amber
_ERROR_BG    = "#95A5A6"   # grey
_TEXT_COLOUR = "#FFFFFF"
_FONT_SIZE   = 10


class FloatingWidget:
    """
    A small always-on-top, draggable mic-toggle button.

    Must be created and operated from the main tkinter thread.
    """

    def __init__(
        self,
        root: tk.Tk,
        on_toggle: Callable,           # called when user clicks the button
        x: int = 100,
        y: int = 100,
        size: int = 64,
        opacity: float = 0.85,
        always_on_top: bool = True,
        on_position_changed: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        self._root = root
        self._on_toggle = on_toggle
        self._on_position_changed = on_position_changed
        self._size = size
        self._visible = False

        # Create a separate top-level window
        self._win = tk.Toplevel(root)
        self._win.overrideredirect(True)        # remove title bar / decorations
        self._win.attributes("-topmost", always_on_top)
        self._win.attributes("-alpha", opacity)
        self._win.geometry(f"{size}x{size}+{x}+{y}")
        self._win.configure(bg=_IDLE_BG)
        self._win.withdraw()                    # hidden until show() is called

        # Canvas for drawing the mic icon
        self._canvas = tk.Canvas(
            self._win,
            width=size,
            height=size,
            bg=_IDLE_BG,
            highlightthickness=0,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._draw_mic_icon(_IDLE_BG)

        # Drag support
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._canvas.bind("<ButtonPress-1>",   self._on_drag_start)
        self._canvas.bind("<B1-Motion>",       self._on_drag_motion)
        self._canvas.bind("<ButtonRelease-1>", self._on_drag_release)

        # Click to toggle (only if cursor didn't move — not a drag)
        self._dragged = False

    # ── Public API ─────────────────────────────────────────────────────────────

    def show(self) -> None:
        self._win.deiconify()
        self._visible = True

    def hide(self) -> None:
        self._win.withdraw()
        self._visible = False

    def toggle_visibility(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()

    @property
    def is_visible(self) -> bool:
        return self._visible

    def set_state(self, state: str) -> None:
        """Update icon colour. state: 'idle'|'active'|'loading'|'error'"""
        colour_map = {
            "idle":    _IDLE_BG,
            "active":  _ACTIVE_BG,
            "loading": _LOADING_BG,
            "error":   _ERROR_BG,
        }
        colour = colour_map.get(state, _IDLE_BG)
        self._canvas.configure(bg=colour)
        self._win.configure(bg=colour)
        self._draw_mic_icon(colour)
        tooltip = {
            "idle":    "Click to start dictation",
            "active":  "Dictating… click to stop",
            "loading": "Loading model…",
            "error":   "Error — check settings",
        }.get(state, "")
        self._win.title(tooltip)

    def update_geometry(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        size: Optional[int] = None,
        opacity: Optional[float] = None,
        always_on_top: Optional[bool] = None,
    ) -> None:
        if size is not None:
            self._size = size
        cx, cy = self._get_position()
        nx = x if x is not None else cx
        ny = y if y is not None else cy
        self._win.geometry(f"{self._size}x{self._size}+{nx}+{ny}")
        if opacity is not None:
            self._win.attributes("-alpha", opacity)
        if always_on_top is not None:
            self._win.attributes("-topmost", always_on_top)

    def destroy(self) -> None:
        try:
            self._win.destroy()
        except Exception:
            pass

    # ── Drag ──────────────────────────────────────────────────────────────────

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._dragged = False

    def _on_drag_motion(self, event: tk.Event) -> None:
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        if abs(dx) > 3 or abs(dy) > 3:
            self._dragged = True
        x, y = self._get_position()
        self._win.geometry(f"+{x + dx}+{y + dy}")

    def _on_drag_release(self, event: tk.Event) -> None:
        if not self._dragged:
            # It was a click, not a drag
            self._on_toggle()
        else:
            # Save new position
            x, y = self._get_position()
            if self._on_position_changed:
                self._on_position_changed(x, y)

    def _get_position(self) -> tuple[int, int]:
        geo = self._win.geometry()          # "WxH+X+Y"
        parts = geo.replace("-", "+-").split("+")
        return int(parts[1]), int(parts[2])

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw_mic_icon(self, bg: str) -> None:
        """Draw a simplified microphone shape on the canvas."""
        c = self._canvas
        s = self._size
        c.delete("all")

        # Mic body
        bw = s * 0.25
        bh = s * 0.40
        bx = (s - bw) / 2
        by = s * 0.08
        c.create_rectangle(bx, by, bx + bw, by + bh,
                            fill=_TEXT_COLOUR, outline="", width=0)

        # Rounded top (approximated with oval)
        c.create_oval(bx - 1, by - bw / 2, bx + bw + 1, by + bw / 2,
                      fill=_TEXT_COLOUR, outline="", width=0)

        # Stand arc (two arcs + vertical line + base)
        r = s * 0.30
        cx_ = s / 2
        arc_y = s * 0.30
        c.create_arc(cx_ - r, arc_y, cx_ + r, arc_y + r * 1.5,
                     start=0, extent=-180,
                     style=tk.ARC, outline=_TEXT_COLOUR, width=max(2, s // 22))

        # Vertical stick
        c.create_line(cx_, arc_y + r * 0.75, cx_, s * 0.84,
                      fill=_TEXT_COLOUR, width=max(2, s // 22))

        # Base
        bbase = s * 0.18
        c.create_line(cx_ - bbase, s * 0.84, cx_ + bbase, s * 0.84,
                      fill=_TEXT_COLOUR, width=max(2, s // 22))
