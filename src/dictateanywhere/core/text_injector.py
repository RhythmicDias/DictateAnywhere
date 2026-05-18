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

import ctypes
from ctypes import wintypes
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Windows API Structures ──────────────────────────────────────────────────

class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]

class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class Input_I(ctypes.Union):
    _fields_ = [
        ("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)
    ]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]


# Windows Constants
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_V = 0x56

# Specific modifiers
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1


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

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _release_modifiers(self) -> None:
        """
        Wait for physical release and then virtually release Ctrl, Alt, Shift, and Win keys.
        """
        keys = [
            VK_CONTROL, VK_LCONTROL, VK_RCONTROL,
            VK_MENU, VK_LMENU, VK_RMENU,
            VK_SHIFT, VK_LSHIFT, VK_RSHIFT,
            VK_LWIN, VK_RWIN,
            0x73, # F4 (The user's default hotkey)
        ]
        
        user32 = ctypes.windll.user32
        
        # 1. Wait for physical release (up to 1 second)
        # This is critical for push-to-talk to avoid "stuck" keys during injection.
        t0 = time.monotonic()
        while time.monotonic() - t0 < 1.0:
            still_down = False
            for vk in keys:
                if user32.GetAsyncKeyState(vk) & 0x8000:
                    still_down = True
                    break
            if not still_down:
                break
            time.sleep(0.01)
            
        # 2. Force logical release
        for vk in keys:
            if user32.GetKeyState(vk) & 0x8000:
                user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        
        # 3. Batch release via SendInput
        for vk in keys:
            ki = KeyBdInput(vk, 0, KEYEVENTF_KEYUP, 0, 0)
            event = (Input * 1)(Input(INPUT_KEYBOARD, Input_I(ki=ki)))
            user32.SendInput(1, event, ctypes.sizeof(Input))
        
        # 4. Small delay for OS to process key releases
        time.sleep(0.05)

    # ── Clipboard retry helper ──────────────────────────────────────────────

    @staticmethod
    def _open_clipboard_retry(max_attempts: int = 3, delay: float = 0.05) -> bool:
        """Try to open the clipboard with retries for apps that hold the lock."""
        import win32clipboard
        for attempt in range(max_attempts):
            try:
                win32clipboard.OpenClipboard()
                return True
            except Exception:
                if attempt < max_attempts - 1:
                    time.sleep(delay)
        return False

    def inject(self, text: str) -> bool:
        """
        Inject *text* at the current cursor position.
        Returns True on success.
        """
        if not text:
            return True
        with self._lock:
            # Safety: Release modifiers to avoid hotkey interference
            self._release_modifiers()

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
                if self._open_clipboard_retry():
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
            if not self._open_clipboard_retry():
                logger.error("Failed to open clipboard after retries")
                return False
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            win32clipboard.CloseClipboard()

            logger.info("Injecting %d chars via CLIPBOARD", len(text))

            # Small delay so the target app registers the clipboard change
            time.sleep(self._delay)

            # Send Ctrl+V using SendInput
            def _send_v():
                user32 = ctypes.windll.user32
                
                # Small delay to ensure any transient UI state settles
                time.sleep(0.05)

                # Ensure Ctrl is down
                ki_ctrl_down = KeyBdInput(VK_CONTROL, 0, 0, 0, 0)
                event_ctrl_down = (Input * 1)(Input(INPUT_KEYBOARD, Input_I(ki=ki_ctrl_down)))
                user32.SendInput(1, event_ctrl_down, ctypes.sizeof(Input))
                time.sleep(0.1) 

                # V down
                ki_v_down = KeyBdInput(VK_V, 0, 0, 0, 0)
                event_v_down = (Input * 1)(Input(INPUT_KEYBOARD, Input_I(ki=ki_v_down)))
                user32.SendInput(1, event_v_down, ctypes.sizeof(Input))
                time.sleep(0.1)

                # V up
                ki_v_up = KeyBdInput(VK_V, 0, KEYEVENTF_KEYUP, 0, 0)
                event_v_up = (Input * 1)(Input(INPUT_KEYBOARD, Input_I(ki=ki_v_up)))
                user32.SendInput(1, event_v_up, ctypes.sizeof(Input))
                time.sleep(0.1)

                # Ctrl up
                ki_ctrl_up = KeyBdInput(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0, 0)
                event_ctrl_up = (Input * 1)(Input(INPUT_KEYBOARD, Input_I(ki=ki_ctrl_up)))
                user32.SendInput(1, event_ctrl_up, ctypes.sizeof(Input))
                time.sleep(0.05)

            _send_v()

            # Restore original clipboard after a safer delay
            def _restore():
                time.sleep(1.0)
                try:
                    if TextInjector._open_clipboard_retry():
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
            for char in text:
                code = ord(char)
                
                # key down
                ki_down = KeyBdInput(0, code, KEYEVENTF_UNICODE, 0, 0)
                ii_down = Input_I()
                ii_down.ki = ki_down
                event_down = (Input * 1)(Input(INPUT_KEYBOARD, ii_down))
                ctypes.windll.user32.SendInput(1, event_down, ctypes.sizeof(Input))
                
                # Tiny sleep to ensure KeyDown is processed before KeyUp
                time.sleep(0.005)
                
                # key up
                ki_up = KeyBdInput(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)
                ii_up = Input_I()
                ii_up.ki = ki_up
                event_up = (Input * 1)(Input(INPUT_KEYBOARD, ii_up))
                ctypes.windll.user32.SendInput(1, event_up, ctypes.sizeof(Input))
                
                # Avoid flooding the target app's message loop
                time.sleep(0.005)

            logger.info("Injected %d chars via SENDINPUT", len(text))
            return True

        except Exception as exc:
            logger.error("SendInput injection failed: %s", exc)
            return False
