"""
Transcription preview overlay.

A small always-on-top floating window that shows the last few dictated
utterances and a live "● Listening…" indicator while recording is active.

Design goals
────────────
- Rounded corners for a premium feel.
- Smooth waveform visualizer instead of LED segments.
- Semi-transparent dark background.
- Draggable and auto-hiding.
"""

from __future__ import annotations

import logging
import math
import tkinter as tk
import ctypes
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

# ── Appearance constants ───────────────────────────────────────────────────────
_MAX_HISTORY   = 3
_WIDTH         = 560
_RADIUS        = 28
_FONT_BODY     = ("Segoe UI Semibold", 11)
_FONT_HINT     = ("Segoe UI", 9)
_BG            = "#1a1a1a"
_ACCENT        = "#4fc3f7"   # ice blue
_FG_OLDER      = "#888888"
_FG_HINT       = "#666666"
_PAD_X         = 20
_PAD_Y         = 12
_TRANS_COLOUR  = "#ff00ff"   # magic pink for transparency


class PreviewWindow:
    """Floating overlay that shows recent dictation output with a modern aesthetic."""

    def __init__(self, root: tk.Tk, config_manager) -> None:
        self._root = root
        self._cfg  = config_manager
        self._win:  Optional[tk.Toplevel] = None
        self._visible   = False
        self._listening = False
        self._history: deque[str] = deque(maxlen=_MAX_HISTORY)
        self._hide_id:  Optional[str] = None
        self._drag_x    = 0
        self._drag_y    = 0
        self._level: float = 0.0
        self._level_history: deque[float] = deque([0.0] * 40, maxlen=40)
        
        # widget refs
        self._canvas:       Optional[tk.Canvas] = None
        self._status_lbl:   Optional[tk.Label]  = None
        self._text_labels:  list[tk.Label]      = []
        self._main_frame:   Optional[tk.Frame]  = None

    def show_text(self, text: str) -> None:
        self._tentative_text = ""
        if not text.strip():
            return
        self._history.append(text.strip())
        if not self._cfg.get("show_preview_window", True):
            return
        self._ensure_window()
        self._refresh()
        # Only auto-hide once the final text is actually shown
        self._schedule_auto_hide()

    def show_tentative_text(self, text: str) -> None:
        self._tentative_text = text.strip()
        if not self._cfg.get("show_preview_window", True):
            return
        self._ensure_window()
        self._refresh()
        self._cancel_auto_hide()

    def show_status(self, status: str) -> None:
        """Show a temporary status message (e.g. Polishing...) without changing history."""
        self._tentative_text = ""
        if not self._cfg.get("show_preview_window", True):
            return
        self._ensure_window()
        self._status_text = status
        self._refresh()
        self._cancel_auto_hide()

    def set_state(self, state: str) -> None:
        self._status_text = ""
        if state == "active":
            self._listening = True
            self._cancel_auto_hide()
            self._history.clear()
            self._tentative_text = ""
            if self._cfg.get("show_preview_window", True):
                self._ensure_window()
        elif state == "loading":
            self._listening = False
            self._level = 0.0
            self._cancel_auto_hide()
        elif state == "idle":
            self._listening = False
            self._level = 0.0
            self._tentative_text = ""
            self._schedule_auto_hide()
        elif state == "error":
            self._listening = False
            self._level = 0.0
            self._tentative_text = ""
            self._schedule_auto_hide()
            
        self._refresh()

    def set_level(self, rms: float) -> None:
        self._level = rms
        self._level_history.append(rms)
        if self._listening and self._canvas:
            self._draw_waveform()

    def toggle_visibility(self) -> None:
        if self._visible:
            self.hide()
        else:
            self._ensure_window()

    def hide(self) -> None:
        self._cancel_auto_hide()
        if self._win and self._win.winfo_exists():
            self._win.withdraw()
        self._visible = False

    def refresh_settings(self) -> None:
        """Apply live updates for opacity and color if the window exists."""
        if self._win and self._win.winfo_exists():
            alpha = self._cfg.get("preview_opacity", 0.85)
            self._win.attributes("-alpha", alpha)
            self._refresh()

    def destroy(self) -> None:
        self._cancel_auto_hide()
        if self._win and self._win.winfo_exists():
            self._win.destroy()
        self._win = None
        self._visible = False

    def _ensure_window(self) -> None:
        if self._win and self._win.winfo_exists():
            if not self._visible:
                # deiconify can steal focus, alpha 0 trick helps
                self._win.attributes("-alpha", 0.0)
                self._win.deiconify()
                alpha = self._cfg.get("preview_opacity", 0.85)
                self._win.attributes("-alpha", alpha)
                self._visible = True
            return

        win = tk.Toplevel(self._root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        alpha = self._cfg.get("preview_opacity", 0.85)
        win.attributes("-alpha", alpha)
        win.attributes("-transparentcolor", _TRANS_COLOUR)
        
        # Windows-specific: prevent the window from appearing in taskbar or taking focus
        try:
            # -toolwindow removes from taskbar
            win.attributes("-toolwindow", True)
            # -noactivate prevents taking focus on show/click (Tk 8.6.6+)
            win.attributes("-noactivate", True)
            
            # Force WS_EX_NOACTIVATE via Win32 API to be absolutely sure
            # This prevents the window from stealing focus even when deiconified.
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            hwnd = win.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
        except Exception as e:
            logger.debug("Failed to set window styles: %s", e)

        win.configure(bg=_TRANS_COLOUR)
        win.resizable(False, False)

        # Main canvas for rounded background
        self._canvas = tk.Canvas(
            win, width=_WIDTH, height=120,
            bg=_TRANS_COLOUR, highlightthickness=0
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Initial position
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = (sw - _WIDTH) // 2
        y = sh - 220
        win.geometry(f"{_WIDTH}x120+{x}+{y}")

        # Bindings for drag
        self._canvas.bind("<ButtonPress-1>", self._drag_start)
        self._canvas.bind("<B1-Motion>",     self._drag_motion)

        self._win = win
        self._visible = True
        self._refresh()

    def _refresh(self) -> None:
        if not self._win or not self._win.winfo_exists():
            return

        # 1. Redraw the rounded container
        c = self._canvas
        c.delete("bg")
        w, h = _WIDTH, self._win.winfo_height()
        self._draw_rounded_rect(c, 0, 0, w, h, _RADIUS, fill=_BG, tags="bg")

        # 2. Rebuild/Update internal widgets
        if not self._main_frame:
            # Solid background to prevent transparent holes, inset by 12px
            # so the sharp corners stay safely inside the rounded Canvas polygon.
            self._main_frame = tk.Frame(self._win, bg=_BG)
            self._main_frame.place(x=12, y=12, width=_WIDTH-24, height=h-24)
            
            header = tk.Frame(self._main_frame, bg=_BG)
            header.pack(fill=tk.X, padx=_PAD_X - 12, pady=(4, 5))
            
            self._status_lbl = tk.Label(
                header, text="", font=_FONT_HINT,
                bg=_BG, fg=_ACCENT, anchor=tk.W
            )
            self._status_lbl.pack(side=tk.LEFT)
            
            close_btn = tk.Label(
                header, text="✕", font=_FONT_HINT,
                bg=_BG, fg=_FG_HINT, cursor="hand2"
            )
            close_btn.pack(side=tk.RIGHT)
            close_btn.bind("<Button-1>", lambda _: self.hide())

            # Small canvas specifically for the waveform
            self._wave_canvas = tk.Canvas(header, width=120, height=20, bg=_BG, highlightthickness=0)
            self._wave_canvas.pack(side=tk.RIGHT, padx=10)
            
            self._text_labels = []
            for _ in range(_MAX_HISTORY):
                lbl = tk.Label(
                    self._main_frame, text="", font=_FONT_BODY,
                    bg=_BG, fg=_FG_OLDER, anchor=tk.W, justify=tk.LEFT,
                    wraplength=_WIDTH - 24 - (_PAD_X * 2)
                )
                lbl.pack(fill=tk.X, padx=_PAD_X, pady=1)
                self._text_labels.append(lbl)
                
            self._tentative_lbl = tk.Label(
                self._main_frame, text="", font=_FONT_BODY,
                bg=_BG, fg=_ACCENT, anchor=tk.W, justify=tk.LEFT,
                wraplength=_WIDTH - 24 - (_PAD_X * 2)
            )
            self._tentative_lbl.pack(fill=tk.X, padx=_PAD_X, pady=2)

        # Header text
        status_to_show = getattr(self, '_status_text', "")
        if status_to_show:
            self._status_lbl.configure(text=f"●  {status_to_show}", fg=_ACCENT)
        elif getattr(self, '_tentative_text', ""):
            self._status_lbl.configure(text="●  Transcribing…", fg=_ACCENT)
        elif self._listening:
            self._status_lbl.configure(text="●  Listening…", fg=_ACCENT)
        elif self._history:
            self._status_lbl.configure(text="Last Dictation", fg=_FG_HINT)
        else:
            self._status_lbl.configure(text="Ready", fg=_FG_HINT)

        # Text labels
        history = list(self._history)
        padded = [""] * (_MAX_HISTORY - len(history)) + history
        for i, (lbl, text) in enumerate(zip(self._text_labels, padded)):
            if not text:
                lbl.pack_forget()
            else:
                lbl.pack(fill=tk.X, padx=_PAD_X, pady=2)
                fg = self._cfg.get("preview_text_color", "#ffffff")
                lbl.configure(text=text, fg=fg if i == _MAX_HISTORY-1 else _FG_OLDER)
                
        # Tentative text label
        t_text = getattr(self, '_tentative_text', "")
        if t_text:
            self._tentative_lbl.pack(fill=tk.X, padx=_PAD_X, pady=2)
            self._tentative_lbl.configure(text=t_text)
        else:
            self._tentative_lbl.pack_forget()

        # Dynamic height adjustment
        self._win.update_idletasks()
        # _main_frame reqheight + 24px (12px top/bottom inset) to fully enclose it
        req_h = self._main_frame.winfo_reqheight() + 24
        new_h = max(req_h, 80)
        
        geo = self._win.geometry()
        try:
            _, rest = geo.split("+", 1)
            xp, yp = rest.split("+")
            if int(self._win.winfo_height()) != new_h:
                self._win.geometry(f"{_WIDTH}x{new_h}+{xp}+{yp}")
                self._win.update_idletasks()  # Force canvas to resize before we redraw
                
                # Place frame again to match new height, with 12px inset
                self._main_frame.place(x=12, y=12, width=_WIDTH-24, height=new_h-24)
                # Redraw background
                c.delete("bg")
                self._draw_rounded_rect(c, 0, 0, _WIDTH, new_h, _RADIUS, fill=_BG, tags="bg")
        except:
            pass
            
        self._draw_waveform()

    def _draw_waveform(self) -> None:
        """Draw a smooth rolling wave on the canvas."""
        if not hasattr(self, "_wave_canvas"): return
        c = self._wave_canvas
        if not c: return
        c.delete("wave")
        
        if not self._listening:
            return

        w = 120
        mid_y = 10 # middle of the 20px high canvas
        
        points = []
        hist = list(self._level_history)
        n = len(hist)
        dx = w / (n - 1)
        start_x = 0
        
        for i, rms in enumerate(hist):
            x = start_x + i * dx
            # Log scale for wave height
            amp = min(1.0, math.log10(1.0 + rms * 100) / 2.0) * 8
            points.extend([x, mid_y - amp, x, mid_y + amp])
            
        if len(points) >= 4:
            # Draw as a series of vertical lines (frequency bars but smooth)
            for i in range(0, len(points), 4):
                c.create_line(points[i], points[i+1], points[i+2], points[i+3],
                             fill=_ACCENT, width=2, capstyle=tk.ROUND, tags="wave")

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2, x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return canvas.create_polygon(points, **kwargs, smooth=True)

    def _schedule_auto_hide(self) -> None:
        self._cancel_auto_hide()
        ms = self._cfg.get("preview_hide_after_ms", 8000)
        if ms > 0:
            self._hide_id = self._root.after(ms, self.hide)

    def _cancel_auto_hide(self) -> None:
        if self._hide_id:
            try: self._root.after_cancel(self._hide_id); 
            except: pass
            self._hide_id = None

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x_root - self._win.winfo_x()
        self._drag_y = event.y_root - self._win.winfo_y()

    def _drag_motion(self, event: tk.Event) -> None:
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self._win.geometry(f"+{x}+{y}")
