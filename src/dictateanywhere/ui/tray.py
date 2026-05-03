"""
System tray icon and menu.

Lives in the Windows notification area. Right-click shows a context menu
with dictation controls, widget toggle, settings, and quit.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# ── Icon colours ──────────────────────────────────────────────────────────────
_COLOUR_IDLE     = "#4A90D9"   # blue
_COLOUR_ACTIVE   = "#E74C3C"   # red (recording)
_COLOUR_LOADING  = "#F39C12"   # amber (model loading)
_COLOUR_BG       = "#FFFFFF"   # white background
_ICON_SIZE       = (64, 64)


def _make_icon(state: str = "idle") -> Image.Image:
    """Generate a simple round mic icon for the system tray."""
    colour_map = {
        "idle":    _COLOUR_IDLE,
        "active":  _COLOUR_ACTIVE,
        "loading": _COLOUR_LOADING,
        "error":   "#95A5A6",
    }
    colour = colour_map.get(state, _COLOUR_IDLE)

    img = Image.new("RGBA", _ICON_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer circle
    draw.ellipse([2, 2, 61, 61], fill=colour, outline=None)

    # Microphone body (white rectangle)
    draw.rounded_rectangle([22, 10, 42, 38], radius=10, fill="#FFFFFF")

    # Microphone stand (white arc shape simplified as rect + line)
    draw.arc([16, 28, 48, 50], start=0, end=180, fill="#FFFFFF", width=3)
    draw.line([32, 50, 32, 56], fill="#FFFFFF", width=3)
    draw.line([24, 56, 40, 56], fill="#FFFFFF", width=3)

    return img


class TrayIcon:
    """
    Manages the pystray system tray icon and its menu.

    All callbacks are invoked in a background thread by pystray.
    GUI operations (opening windows) must be delegated back to the
    main tkinter thread via the *schedule_gui* callback.
    """

    def __init__(
        self,
        on_start_dictation: Callable,
        on_stop_dictation: Callable,
        on_open_settings: Callable,
        on_toggle_widget: Callable,
        on_toggle_preview: Callable,
        on_quit: Callable,
        schedule_gui: Callable,         # thread-safe tk.after equivalent
    ) -> None:
        self._on_start = on_start_dictation
        self._on_stop = on_stop_dictation
        self._on_settings = on_open_settings
        self._on_toggle_widget = on_toggle_widget
        self._on_toggle_preview = on_toggle_preview
        self._on_quit = on_quit
        self._schedule_gui = schedule_gui

        self._icon = None
        self._dictating = False
        self._thread: Optional[threading.Thread] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Launch the tray icon in a daemon thread."""
        import pystray

        menu = pystray.Menu(
            pystray.MenuItem("DictateAnywhere", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Start Dictation",
                self._menu_start,
                visible=lambda item: not self._dictating,
            ),
            pystray.MenuItem(
                "Stop Dictation",
                self._menu_stop,
                visible=lambda item: self._dictating,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Toggle Floating Button",  self._menu_toggle_widget),
            pystray.MenuItem("Toggle Preview Overlay",  self._menu_toggle_preview),
            pystray.MenuItem("Settings…",               self._menu_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",                    self._menu_quit),
        )

        self._icon = pystray.Icon(
            name="DictateAnywhere",
            icon=_make_icon("idle"),
            title="DictateAnywhere — Idle",
            menu=menu,
        )

        self._thread = threading.Thread(
            target=self._icon.run, name="tray-thread", daemon=True
        )
        self._thread.start()
        logger.info("Tray icon started")

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    # ── State updates (thread-safe) ────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        """Update the icon and tooltip. state: 'idle'|'active'|'loading'|'error'"""
        if not self._icon:
            return
        labels = {
            "idle":    "DictateAnywhere — Idle",
            "active":  "DictateAnywhere — Recording…",
            "loading": "DictateAnywhere — Loading model…",
            "error":   "DictateAnywhere — Error (check settings)",
        }
        self._dictating = state == "active"
        try:
            self._icon.icon = _make_icon(state)
            self._icon.title = labels.get(state, "DictateAnywhere")
        except Exception as exc:
            logger.debug("Tray update error: %s", exc)

    # ── Menu callbacks ─────────────────────────────────────────────────────────

    def _menu_start(self, icon, item) -> None:
        threading.Thread(target=self._on_start, daemon=True).start()

    def _menu_stop(self, icon, item) -> None:
        threading.Thread(target=self._on_stop, daemon=True).start()

    def _menu_settings(self, icon, item) -> None:
        self._schedule_gui(self._on_settings)

    def _menu_toggle_widget(self, icon, item) -> None:
        self._schedule_gui(self._on_toggle_widget)

    def _menu_toggle_preview(self, icon, item) -> None:
        self._schedule_gui(self._on_toggle_preview)

    def _menu_quit(self, icon, item) -> None:
        self._schedule_gui(self._on_quit)
