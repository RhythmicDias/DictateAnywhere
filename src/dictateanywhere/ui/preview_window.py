"""
Transcription preview overlay.

A small always-on-top floating window that shows the last few dictated
utterances and a live "● Listening…" indicator while recording is active.

Design goals
────────────
- No title bar (overrideredirect) — stays out of Alt+Tab and taskbar.
- Semi-transparent dark background so it reads over any app.
- Draggable via the header bar.
- Auto-hides after a configurable timeout; stays open while listening.
- Never steals keyboard focus.

Thread-safety
─────────────
All public methods MUST be called on the tkinter main thread.
From worker threads, schedule via root.after(0, method).
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

# ── Appearance constants ───────────────────────────────────────────────────────
_MAX_HISTORY  = 3
_WIDTH        = 540
_FONT_BODY    = ("Segoe UI", 11)
_FONT_HINT    = ("Segoe UI", 9)
_BG           = "#1e1e1e"
_HEADER_BG    = "#2c2c2c"
_FG_NEWEST    = "#ffffff"
_FG_OLDER     = "#888888"
_FG_EMPTY     = "#1e1e1e"   # invisible — same as bg
_FG_LISTEN    = "#4fc3f7"   # ice blue
_FG_HINT      = "#555555"
_PAD_X        = 14
_PAD_Y        = 8


class PreviewWindow:
    """Floating overlay that shows recent dictation output."""

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
        # widget refs (populated in _ensure_window)
        self._status_lbl:   Optional[tk.Label] = None
        self._text_labels:  list[tk.Label]     = []
        self._text_frame:   Optional[tk.Frame] = None

    # ── Public API (call on main thread) ──────────────────────────────────────

    def show_text(self, text: str) -> None:
        """Append a completed utterance and (re-)display the overlay."""
        if not text.strip():
            return
        self._history.append(text.strip())
        if not self._cfg.get("show_preview_window", True):
            return
        self._ensure_window()
        self._refresh()
        self._schedule_auto_hide()

    def set_listening(self, active: bool) -> None:
        """Drive the Listening indicator without adding text."""
        self._listening = active
        if not self._cfg.get("show_preview_window", True):
            return
        if active:
            self._cancel_auto_hide()
            self._ensure_window()
        self._refresh()
        if not active:
            self._schedule_auto_hide()

    def toggle_visibility(self) -> None:
        """Show if hidden, hide if visible."""
        if self._visible:
            self.hide()
        else:
            self._ensure_window()

    def hide(self) -> None:
        self._cancel_auto_hide()
        if self._win and self._win.winfo_exists():
            self._win.withdraw()
        self._visible = False

    def destroy(self) -> None:
        self._cancel_auto_hide()
        if self._win and self._win.winfo_exists():
            self._win.destroy()
        self._win = None
        self._visible = False

    # ── Window construction ────────────────────────────────────────────────────

    def _ensure_window(self) -> None:
        if self._win and self._win.winfo_exists():
            if not self._visible:
                self._win.deiconify()
                self._visible = True
            return

        win = tk.Toplevel(self._root)
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)
        win.wm_attributes("-alpha", 0.92)
        win.configure(bg=_BG)
        win.resizable(False, False)
        win.lift()
        # Prevent focus steal
        win.wm_attributes("-disabled", False)

        # ── Position: bottom-centre of primary screen ──────────────────────
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x  = (sw - _WIDTH) // 2
        y  = sh - 200
        win.geometry(f"{_WIDTH}x80+{x}+{y}")

        # ── Header (drag handle · status · close) ─────────────────────────
        header = tk.Frame(win, bg=_HEADER_BG, cursor="fleur")
        header.pack(fill=tk.X)

        self._status_lbl = tk.Label(
            header, text="", font=_FONT_HINT,
            bg=_HEADER_BG, fg=_FG_LISTEN,
            anchor=tk.W, padx=_PAD_X, pady=5,
        )
        self._status_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        close_btn = tk.Label(
            header, text="✕", font=("Segoe UI", 9),
            bg=_HEADER_BG, fg="#555555", cursor="hand2",
            padx=12, pady=5,
        )
        close_btn.pack(side=tk.RIGHT)
        close_btn.bind("<Button-1>",  lambda _e: self.hide())
        close_btn.bind("<Enter>",     lambda _e: close_btn.configure(fg="#ffffff"))
        close_btn.bind("<Leave>",     lambda _e: close_btn.configure(fg="#555555"))

        # ── Text body ─────────────────────────────────────────────────────
        self._text_frame = tk.Frame(win, bg=_BG)
        self._text_frame.pack(fill=tk.BOTH, expand=True,
                              padx=_PAD_X, pady=_PAD_Y)

        self._text_labels = []
        for _ in range(_MAX_HISTORY):
            lbl = tk.Label(
                self._text_frame, text="", font=_FONT_BODY,
                bg=_BG, fg=_FG_OLDER, anchor=tk.W, justify=tk.LEFT,
                wraplength=_WIDTH - _PAD_X * 2,
            )
            lbl.pack(fill=tk.X, pady=1)
            self._text_labels.append(lbl)

        # ── Drag bindings on header and status label ───────────────────────
        for widget in (header, self._status_lbl):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>",     self._drag_motion)

        self._win     = win
        self._visible = True
        self._refresh()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        if not self._win or not self._win.winfo_exists():
            return
        if not self._status_lbl:
            return

        # Header status text
        if self._listening:
            self._status_lbl.configure(text="●  Listening…", fg=_FG_LISTEN)
        elif self._history:
            self._status_lbl.configure(text="DictateAnywhere — last dictation",
                                        fg=_FG_HINT)
        else:
            self._status_lbl.configure(text="DictateAnywhere preview",
                                        fg=_FG_HINT)

        # Text rows — pad deque to _MAX_HISTORY with empty strings
        history  = list(self._history)
        padded   = [""] * (_MAX_HISTORY - len(history)) + history
        last_idx = _MAX_HISTORY - 1

        for i, (lbl, text) in enumerate(zip(self._text_labels, padded)):
            if not text:
                lbl.configure(text=" ", fg=_FG_EMPTY)
            elif i == last_idx:
                lbl.configure(text=text, fg=_FG_NEWEST)
            else:
                lbl.configure(text=text, fg=_FG_OLDER)

        # Auto-fit window height
        self._win.update_idletasks()
        req_h = self._win.winfo_reqheight()
        geo   = self._win.geometry()
        try:
            _, rest = geo.split("+", 1)
            xp, yp  = rest.split("+")
            self._win.geometry(f"{_WIDTH}x{max(req_h, 60)}+{xp}+{yp}")
        except Exception:
            pass

    # ── Auto-hide timer ────────────────────────────────────────────────────────

    def _schedule_auto_hide(self) -> None:
        self._cancel_auto_hide()
        ms = self._cfg.get("preview_hide_after_ms", 8000)
        if ms > 0:
            self._hide_id = self._root.after(ms, self.hide)

    def _cancel_auto_hide(self) -> None:
        if self._hide_id:
            try:
                self._root.after_cancel(self._hide_id)
            except Exception:
                pass
            self._hide_id = None

    # ── Drag ──────────────────────────────────────────────────────────────────

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x_root - self._win.winfo_x()
        self._drag_y = event.y_root - self._win.winfo_y()

    def _drag_motion(self, event: tk.Event) -> None:
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self._win.geometry(f"+{x}+{y}")
