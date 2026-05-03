"""
Global hotkey management.

Uses the *keyboard* library which hooks into the Windows low-level
keyboard event stream so hotkeys fire regardless of which app has focus.

Supports two modes:
  - toggle   : one press starts dictation, next press stops it
  - push_to_talk : hold to dictate, release to stop
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import keyboard

logger = logging.getLogger(__name__)


class HotkeyManager:
    """
    Register / unregister a global hotkey combination.

    Example:
        manager = HotkeyManager(
            hotkey="ctrl+alt+d",
            mode="toggle",
            on_start=start_dictation,
            on_stop=stop_dictation,
        )
        manager.register()
        ...
        manager.unregister()
    """

    def __init__(
        self,
        hotkey: str = "ctrl+alt+d",
        mode: str = "toggle",           # "toggle" | "push_to_talk"
        on_start: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
    ) -> None:
        self._hotkey = hotkey
        self._mode = mode
        self._on_start = on_start
        self._on_stop = on_stop
        self._active = False             # whether dictation is currently ON
        self._registered = False
        self._lock = threading.Lock()

    # ── Public API ─────────────────────────────────────────────────────────────

    def register(self) -> bool:
        """Register the hotkey. Returns True on success."""
        if self._registered:
            return True
        try:
            if self._mode == "push_to_talk":
                keyboard.on_press_key(
                    self._hotkey.split("+")[-1],
                    self._on_push_down,
                    suppress=False,
                )
                keyboard.on_release_key(
                    self._hotkey.split("+")[-1],
                    self._on_push_up,
                    suppress=False,
                )
            else:
                keyboard.add_hotkey(
                    self._hotkey,
                    self._on_toggle,
                    suppress=False,
                )
            self._registered = True
            logger.info("Hotkey registered: %r (mode=%s)", self._hotkey, self._mode)
            return True
        except Exception as exc:
            logger.error("Failed to register hotkey %r: %s", self._hotkey, exc)
            return False

    def unregister(self) -> None:
        """Remove the currently registered hotkey."""
        if not self._registered:
            return
        try:
            keyboard.remove_hotkey(self._hotkey)
        except Exception:
            pass
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self._registered = False
        logger.info("Hotkey unregistered: %r", self._hotkey)

    def update(
        self,
        hotkey: Optional[str] = None,
        mode: Optional[str] = None,
        on_start: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
    ) -> bool:
        """Apply new settings by unregistering and re-registering."""
        was_registered = self._registered
        self.unregister()
        if hotkey:
            self._hotkey = hotkey
        if mode:
            self._mode = mode
        if on_start is not None:
            self._on_start = on_start
        if on_stop is not None:
            self._on_stop = on_stop
        if was_registered:
            return self.register()
        return True

    @property
    def hotkey(self) -> str:
        return self._hotkey

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_active(self) -> bool:
        return self._active

    # ── Callbacks ──────────────────────────────────────────────────────────────

    def _on_toggle(self) -> None:
        with self._lock:
            self._active = not self._active
            if self._active:
                logger.debug("Hotkey: dictation START (toggle)")
                if self._on_start:
                    threading.Thread(target=self._on_start, daemon=True).start()
            else:
                logger.debug("Hotkey: dictation STOP (toggle)")
                if self._on_stop:
                    threading.Thread(target=self._on_stop, daemon=True).start()

    def _on_push_down(self, event) -> None:
        with self._lock:
            if not self._active:
                self._active = True
                logger.debug("Hotkey: dictation START (push-to-talk)")
                if self._on_start:
                    threading.Thread(target=self._on_start, daemon=True).start()

    def _on_push_up(self, event) -> None:
        with self._lock:
            if self._active:
                self._active = False
                logger.debug("Hotkey: dictation STOP (push-to-talk)")
                if self._on_stop:
                    threading.Thread(target=self._on_stop, daemon=True).start()

    def force_stop(self) -> None:
        """Programmatically stop dictation (e.g. from tray menu)."""
        with self._lock:
            if self._active:
                self._active = False
                if self._on_stop:
                    threading.Thread(target=self._on_stop, daemon=True).start()

    def force_start(self) -> None:
        """Programmatically start dictation (e.g. from tray menu)."""
        with self._lock:
            if not self._active:
                self._active = True
                if self._on_start:
                    threading.Thread(target=self._on_start, daemon=True).start()


def validate_hotkey(combo: str) -> bool:
    """
    Return True if *combo* is a valid keyboard combination string.

    Examples of valid combos: "ctrl+alt+d", "ctrl+shift+space", "f9"
    """
    if not combo or not combo.strip():
        return False
    try:
        # keyboard.parse_hotkey raises ValueError on bad combos
        keyboard.parse_hotkey(combo.strip().lower())
        return True
    except (ValueError, Exception):
        return False
