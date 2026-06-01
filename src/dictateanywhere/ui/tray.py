"""
System tray icon and menu.

Lives in the Windows notification area. Right-click shows a context menu
with dictation controls, widget toggle, settings, and quit.
"""

from __future__ import annotations

import logging
import os
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


_BASE_ICON: Optional[Image.Image] = None


def _get_base_icon() -> Image.Image:
    global _BASE_ICON
    if _BASE_ICON is None:
        try:
            # Locate assets/icon.png relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            icon_path = os.path.join(base_dir, "assets", "icon.png")
            if os.path.exists(icon_path):
                img = Image.open(icon_path).convert("RGBA")
                _BASE_ICON = img.resize(_ICON_SIZE, Image.Resampling.LANCZOS)
            else:
                logger.warning("Tray base icon not found: %s", icon_path)
        except Exception as e:
            logger.error("Failed to load tray base icon: %s", e)
    
    if _BASE_ICON is not None:
        return _BASE_ICON.copy()
    return Image.new("RGBA", _ICON_SIZE, (0, 0, 0, 0))


def _make_icon(state: str = "idle") -> Image.Image:
    """Generate a system tray icon by overlaying a state status dot on the official app icon."""
    colour_map = {
        "idle":    "#00E5FF",   # neon cyan/ice blue matching the glowing microphone
        "active":  "#FF1744",   # vibrant neon red (recording)
        "loading": "#FFEA00",   # neon yellow/amber (model loading)
        "error":   "#9E9E9E",   # grey (error)
    }
    colour = colour_map.get(state, "#00E5FF")

    # Load base icon
    img = _get_base_icon()
    
    # If the base icon couldn't be loaded, draw the legacy microphone icon as fallback
    if _BASE_ICON is None:
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

    # Draw status indicator dot in the bottom-right corner of the premium icon
    draw = ImageDraw.Draw(img)
    dot_box = [42, 42, 56, 56]
    
    # Draw a dark border/glow around the status dot for visibility on any background
    draw.ellipse([40, 40, 58, 58], fill="#121212")
    draw.ellipse(dot_box, fill=colour)
    
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
        on_open_history: Callable,
        on_quit: Callable,
        schedule_gui: Callable,         # thread-safe tk.after equivalent
    ) -> None:
        self._on_start = on_start_dictation
        self._on_stop = on_stop_dictation
        self._on_settings = on_open_settings
        self._on_toggle_widget = on_toggle_widget
        self._on_toggle_preview = on_toggle_preview
        self._on_history = on_open_history
        self._on_quit = on_quit
        self._schedule_gui = schedule_gui

        self._icon = None
        self._dictating = False
        self._thread: Optional[threading.Thread] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Launch the tray icon in a daemon thread."""
        import sys
        if sys.platform == "darwin":
            logger.info("Tray icon disabled on macOS due to OS-level main thread restrictions. Floating widget right-click menu is enabled.")
            return

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
            pystray.MenuItem("Session History…",        self._menu_history),
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

    def _menu_history(self, icon, item) -> None:
        self._schedule_gui(self._on_history)

    def _menu_quit(self, icon, item) -> None:
        self._schedule_gui(self._on_quit)
