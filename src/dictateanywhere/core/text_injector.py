"""
Text injection at the current cursor position.

Strategy:
  1. Save the current clipboard contents.
  2. Copy the transcribed text to the clipboard.
  3. Send Ctrl+V to paste it at the cursor.
  4. Restore the original clipboard.

Falls back to SendInput character-by-character for apps that block
clipboard paste (e.g. some password managers, terminals).

Windows-only (uses pywin32 and ctypes).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class TextInjector:
    """Inject text at the active cursor position."""

    def __init__(
        self,
        method: str = "clipboard",   # "clipboard" | "sendinput"
        delay_ms: int = 50,
    ) -> None:
        self._method = method
        self._delay = delay_ms / 1000.0
        self._lock = threading.Lock()

    def inject(self, text: str) -> bool:
        """
        Inject *text* at the current cursor position.
        Returns True on success.
        """
        if not text:
            return True
        with self._lock:
            if self._method == "sendinput":
                return self._inject_sendinput(text)
            return self._inject_clipboard(text)

    def set_method(self, method: str) -> None:
        self._method = method

    # ── Clipboard strategy ─────────────────────────────────────────────────────

    def _inject_clipboard(self, text: str) -> bool:
        try:
            import win32clipboard
            import win32con
            import win32api

            # Save current clipboard
            old_content: Optional[str] = None
            try:
                win32clipboard.OpenClipboard()
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    old_content = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            except Exception:
                pass
            finally:
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass

            # Set new clipboard content
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            win32clipboard.CloseClipboard()

            # Small delay so the target app registers the clipboard change
            time.sleep(self._delay)

            # Send Ctrl+V
            import ctypes
            VK_CONTROL = 0x11
            VK_V = 0x56
            KEYEVENTF_KEYUP = 0x0002

            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

            # Restore original clipboard after a brief delay
            def _restore():
                time.sleep(0.3)
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    if old_content is not None:
                        win32clipboard.SetClipboardData(
                            win32con.CF_UNICODETEXT, old_content
                        )
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass

            threading.Thread(target=_restore, daemon=True).start()
            logger.debug("Injected %d chars via clipboard", len(text))
            return True

        except Exception as exc:
            logger.error("Clipboard injection failed: %s", exc)
            return self._inject_sendinput(text)

    # ── SendInput strategy (character-by-character) ────────────────────────────

    def _inject_sendinput(self, text: str) -> bool:
        """
        Use ctypes SendInput to inject each character directly.
        Works in apps that intercept or block clipboard paste.
        """
        try:
            import ctypes
            from ctypes import wintypes

            PUL = ctypes.POINTER(ctypes.c_ulong)

            class KeyBdInput(ctypes.Structure):
                _fields_ = [
                    ("wVk", ctypes.c_ushort),
                    ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", PUL),
                ]

            class HardwareInput(ctypes.Structure):
                _fields_ = [
                    ("uMsg", ctypes.c_ulong),
                    ("wParamL", ctypes.c_short),
                    ("wParamH", ctypes.c_ushort),
                ]

            class MouseInput(ctypes.Structure):
                _fields_ = [
                    ("dx", ctypes.c_long), ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", PUL),
                ]

            class Input_I(ctypes.Union):
                _fields_ = [
                    ("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)
                ]

            class Input(ctypes.Structure):
                _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]

            KEYEVENTF_UNICODE = 0x0004
            KEYEVENTF_KEYUP = 0x0002
            INPUT_KEYBOARD = 1

            extra = ctypes.c_ulong(0)
            ii_ = Input_I()

            inputs = []
            for char in text:
                code = ord(char)
                # key down
                ki_down = KeyBdInput(0, code, KEYEVENTF_UNICODE, 0, ctypes.pointer(extra))
                ii_down = Input_I()
                ii_down.ki = ki_down
                inputs.append(Input(INPUT_KEYBOARD, ii_down))
                # key up
                ki_up = KeyBdInput(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0,
                                   ctypes.pointer(extra))
                ii_up = Input_I()
                ii_up.ki = ki_up
                inputs.append(Input(INPUT_KEYBOARD, ii_up))

            InputArray = Input * len(inputs)
            ctypes.windll.user32.SendInput(
                len(inputs), InputArray(*inputs), ctypes.sizeof(Input)
            )
            logger.debug("Injected %d chars via SendInput", len(text))
            return True

        except Exception as exc:
            logger.error("SendInput injection failed: %s", exc)
            return False
