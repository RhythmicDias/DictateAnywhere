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
import os
import time
import tkinter as tk
import ctypes
from typing import Callable, Optional

from PIL import Image, ImageTk

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

        # Countdown ring state
        self._countdown_start: float = 0.0
        self._countdown_max:   float = 30.0
        self._counting_down:   bool  = False
        
        # Icon assets (loaded on demand/init)
        self._icons: dict[str, ImageTk.PhotoImage] = {}
        self._load_assets()

        # Transparent top-level window (no border, no title bar)
        self._win = tk.Toplevel(root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", always_on_top)
        self._win.attributes("-alpha", opacity)
        # Use a magic colour for window-level transparency (the outer bg)
        self._win.configure(bg="#010101")
        self._win.attributes("-transparentcolor", "#010101")
        self._win.geometry(f"{size}x{size}+{x}+{y}")
        
        # Windows-specific: prevent focus activation
        try:
            self._win.attributes("-noactivate", True)
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            hwnd = self._win.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
        except:
            pass

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

    # ── Countdown ring ─────────────────────────────────────────────────────────

    def start_countdown(self, max_seconds: float = 30.0) -> None:
        """Begin the recording countdown ring. Call when recording starts."""
        self._countdown_max   = max(1.0, max_seconds)
        self._countdown_start = time.monotonic()
        self._counting_down   = True

    def stop_countdown(self) -> None:
        """Clear the countdown ring. Call when recording ends."""
        self._counting_down = False

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
        elapsed = (
            time.monotonic() - self._countdown_start
            if self._counting_down else 0.0
        )
        self._draw(state="active", pulse=self._pulse_step, elapsed=elapsed)
        self._pulse_after = self._root.after(50, self._animate_pulse)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self, state: str = "idle", pulse: int = 0, elapsed: float = 0.0) -> None:
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
            pulse_alpha = abs(math.sin(pulse * math.pi / 15))
            pulse_r = r + 4 + pulse_alpha * 6
            pulse_col = self._alpha_blend(ring, "#010101", pulse_alpha * 0.55)
            c.create_oval(
                cx - pulse_r, cy - pulse_r,
                cx + pulse_r, cy + pulse_r,
                fill=pulse_col, outline="", width=0,
            )

        # ── Main circle ─────────────────────────────────────────────────────
        # Only draw the manual circle if the icon asset failed to load
        if not self._icons.get(state):
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          fill=bg, outline=ring, width=max(1, s // 32))

        # ── Microphone icon ─────────────────────────────────────────────────
        # Note: In premium mode, the icon IS the button background
        self._draw_mic(c, cx, cy, state)

        # ── Countdown ring (active state while recording) ───────────────────
        if state == "active" and self._counting_down and self._countdown_max > 0:
            remaining = max(0.0, self._countdown_max - elapsed)
            fraction  = remaining / self._countdown_max    # 1.0 → 0.0
            sweep_deg = fraction * 360.0

            # Color shifts: green → amber → red as time runs out
            if fraction > 0.50:
                arc_col = "#4CAF50"   # green
            elif fraction > 0.20:
                arc_col = "#FFC107"   # amber
            else:
                arc_col = "#FF5252"   # red

            ring_r = r - 3                        # just inside the circle edge
            ring_w = max(3, s // 20)

            # Background track — full dim circle
            c.create_arc(
                cx - ring_r, cy - ring_r,
                cx + ring_r, cy + ring_r,
                start=90, extent=-359.9,
                style=tk.ARC,
                outline=self._alpha_blend(arc_col, bg, 0.20),
                width=ring_w,
            )

            # Remaining-time arc — sweeps clockwise from 12 o'clock
            if sweep_deg > 1.0:
                c.create_arc(
                    cx - ring_r, cy - ring_r,
                    cx + ring_r, cy + ring_r,
                    start=90,
                    extent=-min(sweep_deg, 359.9),
                    style=tk.ARC,
                    outline=arc_col,
                    width=ring_w,
                )

            # Seconds label — top of button, above the mic icon
            secs_left = int(math.ceil(remaining))
            font_size = max(7, s // 9)
            # Only show text when button is large enough and time is running short
            if s >= 48:
                label_y = cy - r * 0.60
                c.create_text(
                    cx, label_y,
                    text=f"{secs_left}s",
                    fill=arc_col,
                    font=("Segoe UI", font_size, "bold"),
                    anchor=tk.CENTER,
                )

    def _load_assets(self) -> None:
        """Load and resize icon PNGs from the assets folder."""
        # Find assets folder relative to this file
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        icons_dir = os.path.join(base_dir, "assets", "icons")
        
        icon_files = {
            "idle":    "mic_idle.png",
            "active":  "mic_active.png",
            "loading": "mic_loading.png",
            "error":   "mic_idle.png",
        }
        
        target_size = int(self._size - 4)  # Fill the whole button minus a tiny border
        
        for state, filename in icon_files.items():
            path = os.path.join(icons_dir, filename)
            if os.path.exists(path):
                try:
                    import numpy as np
                    img = Image.open(path).convert("RGBA")
                    img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)

                    # Tkinter's create_image ignores PNG alpha — transparent pixels
                    # render as the canvas bg colour (#010101). We pre-composite and
                    # then apply a hard alpha threshold so the anti-aliased fringe
                    # (which would otherwise appear as a dark ring) is forced to
                    # exactly #010101, which the window's transparentcolor hides.
                    rgba  = np.array(img, dtype=np.float32)
                    alpha = rgba[:, :, 3:4] / 255.0           # 0.0 – 1.0
                    rgb   = rgba[:, :, :3]
                    bg_np = np.array([1.0, 1.0, 1.0])         # #010101
                    comp  = (alpha * rgb + (1.0 - alpha) * bg_np).astype(np.uint8)
                    # Hard-clip: any pixel whose original alpha < 50% → #010101
                    comp[alpha[:, :, 0] < 0.50] = [1, 1, 1]
                    bg = Image.fromarray(comp, mode="RGB")
                    self._icons[state] = ImageTk.PhotoImage(bg)
                except Exception as exc:
                    logger.error("Failed to load icon %s: %s", filename, exc)
            else:
                logger.warning("Icon not found: %s", path)

    def _draw_mic(self, c: tk.Canvas, cx: float, cy: float, state: str) -> None:
        """Render the high-quality PNG icon for the current state."""
        icon = self._icons.get(state) or self._icons.get("idle")
        if icon:
            c.create_image(cx, cy, image=icon, anchor=tk.CENTER)
        else:
            # Fallback to a very simple circle if loading failed
            c.create_oval(cx-4, cy-4, cx+4, cy+4, fill="white", outline="")

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
        return self._win.winfo_x(), self._win.winfo_y()

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
