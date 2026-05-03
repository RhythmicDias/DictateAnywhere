"""
Floating draggable microphone button — modern circular design.

An always-on-top, semi-transparent Tkinter window that shows the current
dictation state and lets the user toggle recording with a single click.

The window has no title bar (overrideredirect=True) and can be dragged
anywhere on screen. Its position is saved to config on every move.
"""

from __future__ import annotations

import logging
import math
import tkinter as tk
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ── Colour palette ─────────────────────────────────────────────────────────────
_IDLE_BG      = "#2D7DD2"   # modern blue
_IDLE_RING    = "#5BA4E6"   # lighter ring
_ACTIVE_BG    = "#E63946"   # vivid red (recording)
_ACTIVE_RING  = "#FF6B7A"
_LOADING_BG   = "#F4A261"   # warm amber
_LOADING_RING = "#FFBF80"
_ERROR_BG     = "#6C757D"   # neutral grey
_ERROR_RING   = "#9EA7AD"
_ICON_COLOUR  = "#FFFFFF"


class FloatingWidget:
    """
    A small always-on-top, draggable mic-toggle button with a modern design.

    Must be created and operated from the main tkinter thread.
    """

    def __init__(
        self,
        root: tk.Tk,
        on_toggle: Callable,
        x: int = 100,
        y: int = 100,
        size: int = 64,
        opacity: float = 0.92,
        always_on_top: bool = True,
        on_position_changed: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        self._root = root
        self._on_toggle = on_toggle
        self._on_position_changed = on_position_changed
        self._size = size
        self._visible = False
        self._state = "idle"
        self._pulse_step = 0
        self._pulse_after: Optional[str] = None

        # Transparent top-level window (no border, no title bar)
        self._win = tk.Toplevel(root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", always_on_top)
        self._win.attributes("-alpha", opacity)
        # Use a magic colour for window-level transparency (the outer bg)
        self._win.configure(bg="#010101")
        self._win.attributes("-transparentcolor", "#010101")
        self._win.geometry(f"{size}x{size}+{x}+{y}")
        self._win.withdraw()

        # Canvas fills the entire window
        self._canvas = tk.Canvas(
            self._win,
            width=size,
            height=size,
            bg="#010101",
            highlightthickness=0,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

        self._draw(state="idle")

        # Drag / click bindings
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._dragged = False
        self._canvas.bind("<ButtonPress-1>",   self._on_drag_start)
        self._canvas.bind("<B1-Motion>",       self._on_drag_motion)
        self._canvas.bind("<ButtonRelease-1>", self._on_drag_release)
        self._canvas.bind("<Enter>",           self._on_enter)
        self._canvas.bind("<Leave>",           self._on_leave)

    # ── Public API ─────────────────────────────────────────────────────────────

    def show(self) -> None:
        self._win.deiconify()
        self._visible = True

    def hide(self) -> None:
        self._win.withdraw()
        self._visible = False
        self._stop_pulse()

    def toggle_visibility(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()

    @property
    def is_visible(self) -> bool:
        return self._visible

    def set_state(self, state: str) -> None:
        """Update icon colour and animation. state: 'idle'|'active'|'loading'|'error'"""
        self._state = state
        self._draw(state=state)
        tooltip = {
            "idle":    "Click to start dictation",
            "active":  "Dictating… click to stop",
            "loading": "Loading model…",
            "error":   "Error — check settings",
        }.get(state, "")
        self._win.title(tooltip)

        if state == "active":
            self._start_pulse()
        else:
            self._stop_pulse()
            self._draw(state=state)

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
            self._canvas.config(width=size, height=size)
        cx, cy = self._get_position()
        nx = x if x is not None else cx
        ny = y if y is not None else cy
        self._win.geometry(f"{self._size}x{self._size}+{nx}+{ny}")
        if opacity is not None:
            self._win.attributes("-alpha", opacity)
        if always_on_top is not None:
            self._win.attributes("-topmost", always_on_top)
        self._draw(state=self._state)

    def destroy(self) -> None:
        self._stop_pulse()
        try:
            self._win.destroy()
        except Exception:
            pass

    # ── Pulse animation (recording state) ─────────────────────────────────────

    def _start_pulse(self) -> None:
        self._pulse_step = 0
        self._animate_pulse()

    def _stop_pulse(self) -> None:
        if self._pulse_after is not None:
            try:
                self._root.after_cancel(self._pulse_after)
            except Exception:
                pass
            self._pulse_after = None

    def _animate_pulse(self) -> None:
        if self._state != "active":
            return
        self._pulse_step = (self._pulse_step + 1) % 30
        self._draw(state="active", pulse=self._pulse_step)
        self._pulse_after = self._root.after(50, self._animate_pulse)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self, state: str = "idle", pulse: int = 0) -> None:
        c = self._canvas
        s = self._size
        c.delete("all")

        # Pick colours
        colours = {
            "idle":    (_IDLE_BG,    _IDLE_RING),
            "active":  (_ACTIVE_BG,  _ACTIVE_RING),
            "loading": (_LOADING_BG, _LOADING_RING),
            "error":   (_ERROR_BG,   _ERROR_RING),
        }
        bg, ring = colours.get(state, (_IDLE_BG, _IDLE_RING))

        cx = s / 2
        cy = s / 2
        r  = s / 2 - 2       # main circle radius

        # ── Pulse ring (active state only) ──────────────────────────────────
        if state == "active" and pulse > 0:
            # abs() keeps pulse_alpha in [0, 1] for all steps so colours stay valid
            pulse_alpha = abs(math.sin(pulse * math.pi / 15))
            pulse_r = r + 4 + pulse_alpha * 6
            pulse_col = self._alpha_blend(ring, "#010101", pulse_alpha * 0.55)
            c.create_oval(
                cx - pulse_r, cy - pulse_r,
                cx + pulse_r, cy + pulse_r,
                fill=pulse_col, outline="", width=0,
            )

        # ── Subtle drop shadow ───────────────────────────────────────────────
        shadow_r = r - 1
        c.create_oval(
            cx - shadow_r + 2, cy - shadow_r + 3,
            cx + shadow_r + 2, cy + shadow_r + 3,
            fill="#000000", outline="", width=0,
        )

        # ── Main circle ─────────────────────────────────────────────────────
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=bg, outline=ring, width=max(1, s // 32))

        # ── Inner highlight arc (gives a glossy pill effect) ────────────────
        hr = r * 0.72
        c.create_arc(
            cx - hr, cy - hr * 1.1,
            cx + hr * 0.6, cy,
            start=40, extent=120,
            style=tk.ARC, outline=self._lighten(bg, 0.35),
            width=max(1, s // 40),
        )

        # ── Microphone icon ─────────────────────────────────────────────────
        self._draw_mic(c, cx, cy, s)

    def _draw_mic(self, c: tk.Canvas, cx: float, cy: float, s: float) -> None:
        """Modern, rounded microphone icon centred on (cx, cy)."""
        col = _ICON_COLOUR

        # Body: rounded rectangle (approximated with oval + rect)
        bw = s * 0.22          # body width
        bh = s * 0.32          # body height
        bx = cx - bw / 2
        by = cy - s * 0.22     # top of body

        # Body fill
        c.create_rectangle(
            bx, by + bw / 2,
            bx + bw, by + bh,
            fill=col, outline="", width=0,
        )
        # Rounded top cap
        c.create_oval(
            bx, by,
            bx + bw, by + bw,
            fill=col, outline="", width=0,
        )
        # Rounded bottom cap
        c.create_oval(
            bx, by + bh - bw,
            bx + bw, by + bh,
            fill=col, outline="", width=0,
        )

        # Stand arc
        arc_r  = s * 0.26
        arc_cy = by + bh - bw / 2         # arc centre y = bottom of mic body
        arc_w  = max(2, int(s * 0.055))
        c.create_arc(
            cx - arc_r, arc_cy - arc_r,
            cx + arc_r, arc_cy + arc_r,
            start=0, extent=-180,
            style=tk.ARC, outline=col, width=arc_w,
        )

        # Vertical stem
        stem_top = arc_cy
        stem_bot = cy + s * 0.30
        c.create_line(cx, stem_top, cx, stem_bot,
                      fill=col, width=arc_w, capstyle=tk.ROUND)

        # Base bar
        base_hw = s * 0.16
        c.create_line(cx - base_hw, stem_bot,
                      cx + base_hw, stem_bot,
                      fill=col, width=arc_w, capstyle=tk.ROUND)

    # ── Hover highlight ────────────────────────────────────────────────────────

    def _on_enter(self, _event: tk.Event) -> None:
        self._canvas.configure(cursor="hand2")

    def _on_leave(self, _event: tk.Event) -> None:
        self._canvas.configure(cursor="")

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
            self._on_toggle()
        else:
            x, y = self._get_position()
            if self._on_position_changed:
                self._on_position_changed(x, y)

    def _get_position(self) -> tuple[int, int]:
        geo = self._win.geometry()
        parts = geo.replace("-", "+-").split("+")
        return int(parts[1]), int(parts[2])

    # ── Colour utilities ──────────────────────────────────────────────────────

    @staticmethod
    def _lighten(hex_colour: str, amount: float) -> str:
        """Return a lighter version of a hex colour."""
        h = hex_colour.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = min(255, int(r + (255 - r) * amount))
        g = min(255, int(g + (255 - g) * amount))
        b = min(255, int(b + (255 - b) * amount))
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _alpha_blend(fg: str, bg: str, alpha: float) -> str:
        """Blend fg over bg with the given alpha (0=bg, 1=fg)."""
        alpha = max(0.0, min(1.0, alpha))   # guard against out-of-range values

        def _parse(h: str):
            h = h.lstrip("#")
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

        fr, fg_, fb = _parse(fg)
        br, bg_, bb = _parse(bg)
        r = max(0, min(255, int(fr * alpha + br * (1 - alpha))))
        g = max(0, min(255, int(fg_ * alpha + bg_ * (1 - alpha))))
        b = max(0, min(255, int(fb * alpha + bb * (1 - alpha))))
        return f"#{r:02x}{g:02x}{b:02x}"
