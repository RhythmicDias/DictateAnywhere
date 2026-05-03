"""
DictateAnywhere — entry point.

Wires all components together:
  - ConfigManager + SecureStorage
  - AudioCapture + VADFilter
  - LocalEngine + CloudEngine (hybrid)
  - HotkeyManager
  - TextInjector
  - TrayIcon + FloatingWidget + SettingsWindow (all on the tkinter main thread)
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from typing import Optional

# ── Bootstrap logging before any other import ──────────────────────────────────
def _setup_logging(log_path: Path, level: str = "INFO") -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(level=numeric, format=fmt, handlers=handlers)


from .utils.config import ConfigManager
from .utils.secure_storage import SecureStorage
from .audio.capture import TimedCapture
from .audio.vad import VADFilter
from .transcription.local_engine import LocalEngine
from .transcription.cloud_engine import CloudEngine
from .transcription.engine import EngineStatus
from .core.hotkey_manager import HotkeyManager
from .core.text_injector import TextInjector
from .core.punctuation import process as process_text, clean_whisper_artifacts
from .ui.tray import TrayIcon
from .ui.floating_widget import FloatingWidget
from .ui.settings_window import SettingsWindow

logger = logging.getLogger(__name__)

# RMS energy threshold below which audio is treated as true digital silence.
# 0.0005 ≈ -66 dBFS — this only catches a completely dead signal.
# Whisper's internal VAD (threshold=0.3) is the real hallucination guard.
_SPEECH_ENERGY_THRESHOLD = 0.0005


def _audio_has_speech_energy(audio_bytes: bytes, threshold: float = _SPEECH_ENERGY_THRESHOLD) -> bool:
    """
    Return True if the audio has any energy above true digital silence.

    Threshold is intentionally very low (0.0005) — we only want to skip
    recordings that are a completely dead signal (e.g. mic unplugged).
    Whisper's internal VAD handles near-silence hallucination suppression.
    """
    if not audio_bytes:
        return False
    import numpy as np
    arr = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(arr ** 2)))
    # Log at INFO so the user can see actual mic levels for calibration
    logger.info("Audio RMS: %.5f (silence gate: %.4f)", rms, threshold)
    return rms >= threshold


class DictateAnywhere:
    """
    Top-level application controller.

    Owns and coordinates every subsystem. All UI operations happen on the
    tkinter main thread via self._root.after(). Audio and transcription
    run on background threads.
    """

    def __init__(self) -> None:
        # ── Config & secrets ──────────────────────────────────────────────────
        self._cfg = ConfigManager()
        self._sec = SecureStorage()

        _setup_logging(self._cfg.log_path(), self._cfg.get("log_level", "INFO"))
        logger.info("DictateAnywhere starting …")

        # ── State ──────────────────────────────────────────────────────────────
        self._dictating = False
        self._timed_capture: Optional[TimedCapture] = None
        self._state_lock = threading.Lock()

        # ── Tkinter root (hidden — we only need the event loop) ───────────────
        self._root = tk.Tk()
        self._root.withdraw()               # no main window; we use tray + widget
        self._root.title("DictateAnywhere")

        # ── Core components ───────────────────────────────────────────────────
        self._injector = TextInjector(
            method=self._cfg.get("inject_method", "clipboard"),
            delay_ms=self._cfg.get("inject_delay_ms", 50),
        )
        self._vad = VADFilter(
            aggressiveness=int(self._cfg.get("vad_aggressiveness", 2))
        )

        # ── Engines ───────────────────────────────────────────────────────────
        self._local_engine = LocalEngine(
            model_size=self._cfg.get("model_size", "small"),
            compute_type=self._cfg.get("compute_type", "int8"),
            language=self._cfg.get("language", "en"),
        )
        self._cloud_engine = CloudEngine(
            api_key=self._sec.get_azure_key(),
            region=self._cfg.get("cloud_region", "eastus"),
            language=self._cfg.get("language", "en"),
        )

        # Load local engine in background so startup is instant
        threading.Thread(target=self._load_local_engine, daemon=True).start()

        # ── UI components ─────────────────────────────────────────────────────
        self._floating = FloatingWidget(
            root=self._root,
            on_toggle=self._toggle_dictation,
            x=self._cfg.get("widget_x", 100),
            y=self._cfg.get("widget_y", 100),
            size=self._cfg.get("widget_size", 64),
            opacity=self._cfg.get("widget_opacity", 0.85),
            always_on_top=self._cfg.get("widget_always_on_top", True),
            on_position_changed=self._on_widget_moved,
        )

        self._settings_win = SettingsWindow(
            root=self._root,
            config_manager=self._cfg,
            secure_storage=self._sec,
            on_save=self._on_settings_saved,
        )

        self._tray = TrayIcon(
            on_start_dictation=self._start_dictation,
            on_stop_dictation=self._stop_dictation,
            on_open_settings=self._settings_win.open,
            on_toggle_widget=self._floating.toggle_visibility,
            on_quit=self._quit,
            schedule_gui=self._schedule,
        )

        # ── Hotkey ────────────────────────────────────────────────────────────
        self._hotkey = HotkeyManager(
            hotkey=self._cfg.get("hotkey", "ctrl+alt+d"),
            mode=self._cfg.get("hotkey_mode", "toggle"),
            on_start=self._start_dictation,
            on_stop=self._stop_dictation,
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start all subsystems and enter the tkinter event loop."""
        self._tray.start()
        self._hotkey.register()

        if self._cfg.get("show_floating_widget", True):
            self._floating.show()

        logger.info(
            "DictateAnywhere ready. Hotkey: %s | Engine: %s",
            self._cfg.get("hotkey"),
            self._cfg.get("engine_mode"),
        )
        self._root.mainloop()

    def _quit(self) -> None:
        logger.info("Quitting …")
        self._hotkey.unregister()
        self._tray.stop()
        self._floating.destroy()
        if self._timed_capture:
            self._timed_capture.stop()
        self._root.after(200, self._root.destroy)

    # ── Dictation control ──────────────────────────────────────────────────────

    def _toggle_dictation(self) -> None:
        if self._dictating:
            self._stop_dictation()
        else:
            self._start_dictation()

    def _start_dictation(self) -> None:
        with self._state_lock:
            if self._dictating:
                return
            self._dictating = True

        logger.info("Dictation started")
        self._set_state("active")

        vad = VADFilter(aggressiveness=self._cfg.get("vad_aggressiveness", 2))
        self._timed_capture = TimedCapture(
            vad=vad,
            on_complete=self._on_audio_ready,
            device_index=self._cfg.get("mic_device_index", -1),
            silence_timeout_ms=self._cfg.get("silence_timeout_ms", 1500),
            max_seconds=self._cfg.get("max_record_seconds", 30),
        )
        self._timed_capture.start()

    def _stop_dictation(self) -> None:
        with self._state_lock:
            if not self._dictating:
                return
            self._dictating = False

        logger.info("Dictation stopped by user")
        if self._timed_capture:
            self._timed_capture.stop()
        self._set_state("idle")

    def _on_audio_ready(self, audio_bytes: bytes) -> None:
        """Called from the capture thread when audio is ready to transcribe."""
        # If we used a fallback device, persist it so the warning doesn't repeat
        if self._timed_capture is not None:
            working = self._timed_capture.working_device
            configured = self._cfg.get("mic_device_index", -1)
            # working=None means system default (-1 in our convention)
            working_idx = -1 if working is None else working
            if working_idx != int(configured):
                logger.info("Saving working audio device index: %s", working_idx)
                self._cfg.update({"mic_device_index": working_idx})
                self._cfg.save()

        with self._state_lock:
            self._dictating = False
        self._set_state("loading")

        threading.Thread(
            target=self._transcribe_and_inject,
            args=(audio_bytes,),
            daemon=True,
        ).start()

    def _transcribe_and_inject(self, audio_bytes: bytes) -> None:
        """Transcribe audio and inject result at cursor. Runs on a worker thread."""
        try:
            # Gate: skip Whisper entirely if the audio is too quiet to be speech.
            # This prevents Whisper hallucinations ("You", "Thank you", etc.)
            # on near-silence recordings from background noise.
            if not _audio_has_speech_energy(audio_bytes):
                logger.info("Audio energy below threshold — skipping transcription")
                self._set_state("idle")
                return

            result = self._run_hybrid_transcription(audio_bytes)
            if result and result.strip():
                text = clean_whisper_artifacts(result)
                text = process_text(
                    text,
                    apply_punctuation=self._cfg.get("spoken_punctuation", True),
                    apply_capitalise=self._cfg.get("auto_capitalise", True),
                )
                if text.strip():
                    logger.info("Injecting: %r", text[:80])
                    self._injector.inject(text + " ")
        except Exception as exc:
            logger.exception("Transcription/injection error: %s", exc)
        finally:
            self._set_state("idle")

    def _run_hybrid_transcription(self, audio_bytes: bytes) -> str:
        """
        Hybrid engine logic:
          - local:   use faster-whisper only
          - cloud:   use Azure only
          - hybrid:  try local first; fall back to cloud on error
        """
        mode = self._cfg.get("engine_mode", "hybrid")
        lang = self._cfg.get("language", "en")

        if mode == "cloud":
            return self._cloud_transcribe(audio_bytes, lang)

        if mode == "local":
            return self._local_transcribe(audio_bytes, lang)

        # Hybrid: local first
        result = self._local_transcribe(audio_bytes, lang)
        if not result and self._cfg.get("cloud_fallback_on_error", True):
            logger.info("Local failed — falling back to Azure cloud engine")
            result = self._cloud_transcribe(audio_bytes, lang)
        return result

    def _local_transcribe(self, audio_bytes: bytes, lang: str) -> str:
        if not self._local_engine.is_ready:
            if not self._local_engine.load():
                return ""
        r = self._local_engine.transcribe(audio_bytes, language=lang)
        return r.text if r.success else ""

    def _cloud_transcribe(self, audio_bytes: bytes, lang: str) -> str:
        api_key = self._sec.get_azure_key()
        if not api_key:
            logger.warning("Azure API key not configured — cloud unavailable")
            return ""
        if not self._cloud_engine.is_available():
            self._cloud_engine.update_credentials(
                api_key, self._cfg.get("cloud_region", "eastus")
            )
        r = self._cloud_engine.transcribe(audio_bytes, language=lang)
        return r.text if r.success else ""

    # ── Model loading ──────────────────────────────────────────────────────────

    def _load_local_engine(self) -> None:
        mode = self._cfg.get("engine_mode", "hybrid")
        if mode in ("local", "hybrid"):
            self._set_state("loading")
            ok = self._local_engine.load()
            self._set_state("idle" if ok else "error")

    # ── Settings callback ──────────────────────────────────────────────────────

    def _on_settings_saved(self) -> None:
        """Apply changed settings to live components."""
        cfg = self._cfg.config

        # Injector
        self._injector.set_method(cfg.inject_method)

        # Hotkey
        self._hotkey.update(
            hotkey=cfg.hotkey,
            mode=cfg.hotkey_mode,
            on_start=self._start_dictation,
            on_stop=self._stop_dictation,
        )

        # Floating widget geometry
        self._floating.update_geometry(
            size=cfg.widget_size,
            opacity=cfg.widget_opacity,
            always_on_top=cfg.widget_always_on_top,
        )
        if cfg.show_floating_widget:
            self._floating.show()
        else:
            self._floating.hide()

        # Engines: reload if model changed
        if (cfg.model_size != self._local_engine._model_size or
                cfg.compute_type != self._local_engine._compute_type):
            self._local_engine.set_model_size(cfg.model_size)
            self._local_engine._compute_type = cfg.compute_type
            threading.Thread(target=self._load_local_engine, daemon=True).start()

        # Azure key might have changed
        self._cloud_engine.update_credentials(
            self._sec.get_azure_key() or "",
            cfg.cloud_region,
        )

        logger.info("Settings applied to live components")

    # ── State broadcast ────────────────────────────────────────────────────────

    def _set_state(self, state: str) -> None:
        """Thread-safe state update to all UI components."""
        self._schedule(lambda: self._apply_state(state))

    def _apply_state(self, state: str) -> None:
        self._tray.set_state(state)
        self._floating.set_state(state)

    # ── Widget moved ───────────────────────────────────────────────────────────

    def _on_widget_moved(self, x: int, y: int) -> None:
        self._cfg.set("widget_x", x)
        self._cfg.set("widget_y", y)
        self._cfg.save()

    # ── Thread-safe GUI scheduling ─────────────────────────────────────────────

    def _schedule(self, fn, delay_ms: int = 0) -> None:
        """Schedule *fn* to run on the tkinter main thread."""
        try:
            self._root.after(delay_ms, fn)
        except RuntimeError:
            pass


def main() -> None:
    """CLI entry point registered in pyproject.toml."""
    # Windows: ensure the app can be found by its process name
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW("DictateAnywhere")
        except Exception:
            pass

    app = DictateAnywhere()
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception:
        logger.exception("Fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
