"""
Session history window.

Shows every utterance dictated in the current session with timestamps,
real-time search with highlighting, copy, and export.

Design
──────
- Normal tk.Toplevel with title bar (appears in Alt+Tab / taskbar).
- Singleton: close button hides it; it is never destroyed mid-session.
- Newest entries at the top; re-rendered on every add_entry() and search.
- Search filters entries and highlights matching substrings in yellow.
- Right-click → Copy selection, or use toolbar buttons.

Thread-safety
─────────────
All public methods MUST be called on the tkinter main thread.
"""

from __future__ import annotations

import datetime
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_FONT_BODY  = ("Segoe UI",  10)
_FONT_MONO  = ("Consolas",  10)
_FG_TIME    = "#888888"
_FG_SEP     = "#cccccc"
_FG_BODY    = "#1a1a1a"
_FG_EMPTY   = "#aaaaaa"
_BG_MAIN    = "#fafafa"
_BG_MATCH   = "#fff176"    # vivid yellow — easy to spot
_PAD        = 8


class HistoryWindow:
    """Searchable log of every dictated utterance in the current session."""

    def __init__(self, root: tk.Tk) -> None:
        self._root          = root
        self._win:          Optional[tk.Toplevel] = None
        self._text_widget:  Optional[tk.Text]     = None
        self._search_var:   Optional[tk.StringVar] = None
        self._status_var:   Optional[tk.StringVar] = None
        self._entries:      List[Tuple[str, str]] = []   # (HH:MM:SS, text)
        self._session_start = datetime.datetime.now()

    # ── Public API (main thread) ───────────────────────────────────────────────

    def add_entry(self, text: str) -> None:
        """Record a transcribed utterance; refresh the display if open."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._entries.append((ts, text.strip()))
        logger.debug("History: +entry #%d", len(self._entries))
        if self._win and self._win.winfo_exists():
            self._render()
            self._update_status()

    def open(self) -> None:
        """Open or raise the history window."""
        if self._win and self._win.winfo_exists():
            self._win.deiconify()
            self._win.lift()
            self._win.focus_force()
            return
        self._build()

    # ── Window construction ────────────────────────────────────────────────────

    def _build(self) -> None:
        win = tk.Toplevel(self._root)
        win.title("DictateAnywhere — Session History")
        win.geometry("740x500")
        win.minsize(480, 300)
        # Hide instead of destroy so history survives re-opens
        win.protocol("WM_DELETE_WINDOW", win.withdraw)

        # ── Toolbar ───────────────────────────────────────────────────────
        toolbar = ttk.Frame(win, padding=(_PAD, _PAD, _PAD, 0))
        toolbar.pack(fill=tk.X)

        ttk.Label(toolbar, text="Search:").pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search_changed())
        search_entry = ttk.Entry(toolbar, textvariable=self._search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(4, 0))
        search_entry.bind("<Escape>", lambda _: self._search_var.set(""))

        ttk.Button(toolbar, text="✕",
                   command=lambda: self._search_var.set(""),
                   width=2).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=6, pady=2)

        ttk.Button(toolbar, text="Export…",
                   command=self._export).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(toolbar, text="Copy All",
                   command=self._copy_all).pack(side=tk.RIGHT, padx=4)
        ttk.Button(toolbar, text="Clear",
                   command=self._confirm_clear).pack(side=tk.RIGHT)

        # ── Text area ─────────────────────────────────────────────────────
        frame = ttk.Frame(win, relief="sunken", borderwidth=1,
                          padding=0)
        frame.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)

        vscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._text_widget = tk.Text(
            frame,
            font=_FONT_BODY,
            fg=_FG_BODY,
            bg=_BG_MAIN,
            wrap=tk.WORD,
            state=tk.DISABLED,
            cursor="arrow",
            relief=tk.FLAT,
            padx=10,
            pady=8,
            spacing1=1,
            spacing3=5,
            yscrollcommand=vscroll.set,
            selectbackground="#b3d9ff",
        )
        self._text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vscroll.configure(command=self._text_widget.yview)

        # Text tags
        self._text_widget.tag_configure("time",
            font=_FONT_MONO, foreground=_FG_TIME)
        self._text_widget.tag_configure("sep",
            foreground=_FG_SEP)
        self._text_widget.tag_configure("body",
            font=_FONT_BODY, foreground=_FG_BODY)
        self._text_widget.tag_configure("match",
            background=_BG_MATCH)
        self._text_widget.tag_configure("empty",
            foreground=_FG_EMPTY, justify=tk.CENTER,
            font=("Segoe UI", 11))

        # Right-click context menu
        ctx = tk.Menu(win, tearoff=False)
        ctx.add_command(label="Copy selection", command=self._copy_selection)
        ctx.add_command(label="Copy all",        command=self._copy_all)
        self._text_widget.bind(
            "<Button-3>", lambda e: ctx.tk_popup(e.x_root, e.y_root))

        # ── Status bar ────────────────────────────────────────────────────
        status_bar = ttk.Frame(win, padding=(_PAD, 0, _PAD, _PAD))
        status_bar.pack(fill=tk.X)
        self._status_var = tk.StringVar()
        ttk.Label(status_bar, textvariable=self._status_var,
                  foreground="gray", font=("Segoe UI", 9)).pack(
            side=tk.LEFT)

        self._win = win
        self._render()
        self._update_status()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render(self) -> None:
        if not self._text_widget:
            return
        tw    = self._text_widget
        query = (self._search_var.get() if self._search_var else "").strip()
        ql    = query.lower()

        # Filter
        if ql:
            entries = [(ts, txt) for ts, txt in self._entries
                       if ql in txt.lower()]
        else:
            entries = self._entries

        tw.configure(state=tk.NORMAL)
        tw.delete("1.0", tk.END)

        if not entries:
            if ql:
                tw.insert(tk.END, f'\n\nNo entries matching "{query}".\n', "empty")
            else:
                tw.insert(tk.END,
                    "\n\nNo dictation yet.\n\n"
                    "Press Ctrl+Alt+D and start speaking.",
                    "empty")
        else:
            # Newest first
            for ts, text in reversed(entries):
                tw.insert(tk.END, ts,          "time")
                tw.insert(tk.END, "  │  ",     "sep")
                if ql:
                    self._insert_highlighted(text, ql)
                else:
                    tw.insert(tk.END, text,    "body")
                tw.insert(tk.END, "\n")

        tw.configure(state=tk.DISABLED)

    def _insert_highlighted(self, text: str, query_lower: str) -> None:
        """Insert *text* into the Text widget with query substrings highlighted."""
        tw  = self._text_widget
        tl  = text.lower()
        pos = 0
        qlen = len(query_lower)
        while True:
            idx = tl.find(query_lower, pos)
            if idx == -1:
                tw.insert(tk.END, text[pos:], "body")
                break
            if idx > pos:
                tw.insert(tk.END, text[pos:idx], "body")
            tw.insert(tk.END, text[idx:idx + qlen], ("body", "match"))
            pos = idx + qlen

    def _on_search_changed(self) -> None:
        self._render()
        self._update_status()

    def _update_status(self) -> None:
        if not self._status_var:
            return
        total = len(self._entries)
        query = (self._search_var.get() if self._search_var else "").strip()
        ql    = query.lower()
        shown = sum(1 for _, t in self._entries if ql in t.lower()) if ql else total
        elapsed = datetime.datetime.now() - self._session_start
        secs    = int(elapsed.total_seconds())
        mins, s = divmod(secs, 60)
        hrs, m  = divmod(mins, 60)
        dur = f"{hrs}h {m}m" if hrs else f"{m}m {s}s"

        if ql:
            msg = (f"Showing {shown} of {total} "
                   f"{'entry' if total == 1 else 'entries'} — "
                   f"filter: \"{query}\"")
        else:
            started = self._session_start.strftime("%H:%M:%S")
            msg = (f"{total} {'entry' if total == 1 else 'entries'} · "
                   f"Session started {started} · Running {dur}")
        self._status_var.set(msg)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _copy_all(self) -> None:
        if not self._entries:
            return
        text = "\n".join(f"[{ts}]  {txt}" for ts, txt in self._entries)
        self._root.clipboard_clear()
        self._root.clipboard_append(text)
        self._flash_status("Copied all entries to clipboard.")

    def _copy_selection(self) -> None:
        if not self._text_widget:
            return
        try:
            sel = self._text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            self._root.clipboard_clear()
            self._root.clipboard_append(sel)
        except tk.TclError:
            pass

    def _confirm_clear(self) -> None:
        if not self._entries:
            return
        if messagebox.askyesno(
            "Clear History",
            f"Delete all {len(self._entries)} "
            f"{'entry' if len(self._entries) == 1 else 'entries'}?\n"
            "This cannot be undone.",
            parent=self._win,
        ):
            self._entries.clear()
            self._render()
            self._update_status()

    def _export(self) -> None:
        if not self._entries:
            messagebox.showinfo("Export", "No entries to export yet.",
                                parent=self._win)
            return
        default_name = (
            f"dictation_{self._session_start.strftime('%Y%m%d_%H%M%S')}.txt"
        )
        path = filedialog.asksaveasfilename(
            parent=self._win,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_name,
            title="Export session history",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("DictateAnywhere — Session History\n")
                fh.write(
                    f"Date:    {self._session_start.strftime('%Y-%m-%d')}\n"
                    f"Started: {self._session_start.strftime('%H:%M:%S')}\n"
                    f"Entries: {len(self._entries)}\n"
                )
                fh.write("─" * 60 + "\n\n")
                for ts, txt in self._entries:
                    fh.write(f"[{ts}]  {txt}\n")
            messagebox.showinfo(
                "Exported",
                f"Saved {len(self._entries)} "
                f"{'entry' if len(self._entries) == 1 else 'entries'} to:\n{path}",
                parent=self._win,
            )
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self._win)

    def _flash_status(self, msg: str, ms: int = 2500) -> None:
        """Temporarily replace the status bar text."""
        if not self._status_var:
            return
        self._status_var.set(msg)
        self._root.after(ms, self._update_status)
