import logging
import sys
import threading
from typing import Callable, Optional

if sys.platform != "darwin":
    import keyboard
else:
    keyboard = None

logger = logging.getLogger(__name__)


class MacOSHotkeyListener:
    """
    Private helper class to handle macOS hotkey capturing using pynput.
    Supports both toggle and push-to-talk mode event tracking.
    """

    def __init__(
        self,
        hotkey_str: str,
        mode: str,
        on_start: Optional[Callable],
        on_stop: Optional[Callable],
    ) -> None:
        self.hotkey_str = hotkey_str.strip().lower()
        self.mode = mode
        self.on_start = on_start
        self.on_stop = on_stop

        # Parse hotkey combination parts
        self.parts = self.hotkey_str.split("+")
        self.required_modifiers = set()
        self.trigger_key_char = None
        self.trigger_key_special = None

        for part in self.parts:
            part = part.strip()
            if part in ("ctrl", "control"):
                self.required_modifiers.add("ctrl")
            elif part in ("alt", "option"):
                self.required_modifiers.add("alt")
            elif part in ("shift",):
                self.required_modifiers.add("shift")
            elif part in ("win", "command", "cmd"):
                self.required_modifiers.add("cmd")
            else:
                if part.startswith("f") and part[1:].isdigit():
                    self.trigger_key_special = part
                elif part == "space":
                    self.trigger_key_special = "space"
                elif part == "enter":
                    self.trigger_key_special = "enter"
                else:
                    self.trigger_key_char = part

        self.currently_pressed_modifiers = set()
        self.trigger_pressed = False
        self.listener = None

    def start(self) -> None:
        try:
            from pynput import keyboard as pynput_keyboard
            self.listener = pynput_keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                darwin_intercept=False,
            )
            self.listener.daemon = True
            self.listener.start()
        except Exception as exc:
            logger.error("Failed to start macOS pynput listener (missing Accessibility permissions?): %s", exc)

    def stop(self) -> None:
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None

    def _get_key_name(self, key) -> Optional[str]:
        from pynput import keyboard as pynput_keyboard
        if key in (pynput_keyboard.Key.ctrl, pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r):
            return "ctrl"
        elif key in (pynput_keyboard.Key.alt, pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r, getattr(pynput_keyboard.Key, "option", None)):
            return "alt"
        elif key in (pynput_keyboard.Key.shift, pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r):
            return "shift"
        elif key in (pynput_keyboard.Key.cmd, pynput_keyboard.Key.cmd_l, pynput_keyboard.Key.cmd_r):
            return "cmd"
        return None

    def _is_trigger_key(self, key) -> bool:
        from pynput import keyboard as pynput_keyboard
        if self.trigger_key_char:
            if hasattr(key, "char") and key.char:
                return key.char.lower() == self.trigger_key_char
        if self.trigger_key_special:
            if isinstance(key, pynput_keyboard.Key):
                return key.name.lower() == self.trigger_key_special
        return False

    def _on_press(self, key) -> None:
        mod = self._get_key_name(key)
        if mod:
            self.currently_pressed_modifiers.add(mod)
            return

        if self._is_trigger_key(key):
            if self.required_modifiers.issubset(self.currently_pressed_modifiers):
                if not self.trigger_pressed:
                    self.trigger_pressed = True
                    if self.on_start:
                        self.on_start()

    def _on_release(self, key) -> None:
        mod = self._get_key_name(key)
        if mod:
            self.currently_pressed_modifiers.discard(mod)
            if self.mode == "push_to_talk" and self.trigger_pressed:
                if mod in self.required_modifiers:
                    self.trigger_pressed = False
                    if self.on_stop:
                        self.on_stop()
            return

        if self._is_trigger_key(key):
            self.trigger_pressed = False
            if self.mode == "push_to_talk":
                if self.on_stop:
                    self.on_stop()


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
        self._mac_listener: Optional[MacOSHotkeyListener] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def register(self) -> bool:
        """Register the hotkey. Returns True on success."""
        if self._registered:
            return True
        try:
            hk = self._hotkey.strip().lower()
            
            if sys.platform == "darwin":
                def _start_wrapper():
                    self._on_push_down()
                def _stop_wrapper():
                    self._on_push_up()
                def _toggle_wrapper():
                    self._on_toggle()

                self._mac_listener = MacOSHotkeyListener(
                    hotkey_str=hk,
                    mode=self._mode,
                    on_start=_toggle_wrapper if self._mode == "toggle" else _start_wrapper,
                    on_stop=None if self._mode == "toggle" else _stop_wrapper,
                )
                self._mac_listener.start()
                self._registered = True
                logger.info("macOS Hotkey registered: %r (mode=%s)", hk, self._mode)
                return True

            # Determine if we should suppress the key.
            # We only suppress if it's a single key (like F9).
            # For combos (like ctrl+alt+d), we don't suppress because:
            # 1. The keyboard library has a bug on Windows where it can block the base key (e.g. 'd').
            # 2. Complex combos are unlikely to interfere with normal app usage if passed through.
            suppress = "+" not in hk

            if self._mode == "push_to_talk":
                # Use add_hotkey for both down and up events to benefit from 
                # the library's internal modifier state tracking.
                keyboard.add_hotkey(
                    hk, self._on_push_down, suppress=suppress, trigger_on_release=False
                )
                keyboard.add_hotkey(
                    hk, self._on_push_up, suppress=suppress, trigger_on_release=True
                )
            else:
                keyboard.add_hotkey(
                    hk, self._on_toggle, suppress=suppress
                )
            
            self._registered = True
            logger.info("Hotkey registered: %r (mode=%s, suppress=%s)", hk, self._mode, suppress)
            return True
        except Exception as exc:
            logger.error("Failed to register hotkey %r: %s", self._hotkey, exc)
            return False

    def unregister(self) -> None:
        """Remove the currently registered hotkey."""
        if not self._registered:
            return
        try:
            if sys.platform == "darwin":
                if self._mac_listener:
                    self._mac_listener.stop()
                    self._mac_listener = None
            else:
                # remove_hotkey removes all listeners matching the combo string
                keyboard.remove_hotkey(self._hotkey.strip().lower())
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
        """Apply new settings by unregistering and re-registering only if changed."""
        changed = False
        if hotkey is not None and hotkey.strip().lower() != self._hotkey.strip().lower():
            self._hotkey = hotkey
            changed = True
        if mode is not None and mode != self._mode:
            self._mode = mode
            changed = True
        if on_start is not None and on_start != self._on_start:
            self._on_start = on_start
            changed = True
        if on_stop is not None and on_stop != self._on_stop:
            self._on_stop = on_stop
            changed = True

        if not changed:
            return True

        was_registered = self._registered
        self.unregister()
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

    def _on_push_down(self, event=None) -> None:
        # Note: add_hotkey handles modifier verification internally
        with self._lock:
            if not self._active:
                self._active = True
                logger.debug("Hotkey: dictation START (push-to-talk)")
                if self._on_start:
                    threading.Thread(target=self._on_start, daemon=True).start()

    def _on_push_up(self, event=None) -> None:
        # Note: add_hotkey handles modifier verification internally
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
    
    if sys.platform != "darwin":
        try:
            # keyboard.parse_hotkey raises ValueError on bad combos
            keyboard.parse_hotkey(combo.strip().lower())
            return True
        except (ValueError, Exception):
            return False

    # macOS validation fallback (pynput)
    parts = combo.strip().lower().split("+")
    valid_modifiers = {"ctrl", "control", "alt", "option", "shift", "win", "command", "cmd"}
    has_trigger = False
    
    for part in parts:
        part = part.strip()
        if not part:
            return False
        if part in valid_modifiers:
            continue
        
        # Valid triggers: letters, numbers, function keys, space, enter, etc.
        if len(part) == 1 or (part.startswith("f") and part[1:].isdigit()) or part in ("space", "enter", "tab", "esc", "escape"):
            has_trigger = True
        else:
            return False
            
    return has_trigger

