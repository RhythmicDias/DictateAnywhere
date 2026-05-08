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
from pathlib import Path

# Fix for MKL/OpenMP conflicts on Windows that can cause hangs in faster-whisper
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

def _setup_nvidia_dlls():
    """Add NVIDIA library paths from site-packages to DLL search path on Windows."""
    if sys.platform != "win32":
        return
    
    found = False
    try:
        import site
        # Search in all potential site-packages locations
        prefixes = site.getsitepackages()
        if hasattr(site, "getusersitepackages"):
            prefixes.append(site.getusersitepackages())
            
        for prefix in prefixes:
            nvidia_dir = Path(prefix) / "nvidia"
            if nvidia_dir.exists():
                for bin_dir in nvidia_dir.glob("**/bin"):
                    if bin_dir.is_dir():
                        try:
                            # os.add_dll_directory is for Python 3.8+
                            os.add_dll_directory(str(bin_dir))
                            # Also add to PATH for subprocesses and some DLL loaders
                            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
                            print(f"[DictateAnywhere] Added NVIDIA DLL directory: {bin_dir}")
                            found = True
                        except Exception:
                            pass
    except Exception as e:
        print(f"[DictateAnywhere] Warning: Failed to auto-setup NVIDIA DLL paths: {e}")
    
    if not found:
        # Fallback: check if we are in a venv and look there directly
        venv_path = Path(sys.prefix)
        nvidia_venv = venv_path / "Lib" / "site-packages" / "nvidia"
        if nvidia_venv.exists():
             for bin_dir in nvidia_venv.glob("**/bin"):
                if bin_dir.is_dir():
                    os.add_dll_directory(str(bin_dir))
                    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
                    print(f"[DictateAnywhere] Added NVIDIA DLL directory (venv fallback): {bin_dir}")

_setup_nvidia_dlls()

import threading
import tkinter as tk
from tkinter import ttk
import webbrowser
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
from .transcription.sarvam_engine import SarvamEngine
from .transcription.gemini_engine import GeminiEngine
from .transcription.engine import EngineStatus, TranscriptionResult
from .core.hotkey_manager import HotkeyManager
from .core.text_injector import TextInjector
from .core.punctuation import process as process_text, clean_whisper_artifacts
from .core.corrections import CorrectionsManager
from .core.updater import UpdateChecker
from . import __version__ as _APP_VERSION
from .ui.tray import TrayIcon
from .ui.floating_widget import FloatingWidget
from .ui.settings_window import SettingsWindow
from .ui.preview_window import PreviewWindow
from .ui.history_window import HistoryWindow

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
        self._corr = CorrectionsManager(
            self._cfg.config_dir() / "corrections.json"
        )
        self._updater = UpdateChecker(self._cfg, current_version=_APP_VERSION)

        _setup_logging(self._cfg.log_path(), self._cfg.get("log_level", "INFO"))
        logger.info("DictateAnywhere starting …")

        # ── State ──────────────────────────────────────────────────────────────
        self._dictating = False
        self._continuous_session = False  # True = keep listening after each utterance
        self._timed_capture: Optional[TimedCapture] = None
        self._state_lock = threading.Lock()
        self._previous_text = ""
        self._active_stream_engine = None
        
        # Real-time chunking state
        import queue
        self._chunk_queue = queue.Queue(maxsize=1)
        threading.Thread(target=self._chunk_worker, daemon=True).start()

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
            device=self._cfg.get("local_device", "auto"),
            language=self._cfg.get("language", "en"),
        )
        self._cloud_engine = CloudEngine(
            api_key=self._sec.get_azure_key(),
            region=self._cfg.get("cloud_region", "eastus"),
            language=self._cfg.get("language", "en"),
        )
        self._sarvam_engine = SarvamEngine(
            api_key=self._sec.get_sarvam_key(),
            model=self._cfg.get("sarvam_model"),
            language=self._cfg.get("sarvam_language"),
        )
        self._gemini_engine = GeminiEngine(
            api_key=self._sec.get_gemini_key(),
            model=self._cfg.get("gemini_stt_model"),
            language=self._cfg.get("gemini_stt_language")
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
            corrections_manager=self._corr,
            update_checker=self._updater,
        )

        self._preview = PreviewWindow(
            root=self._root,
            config_manager=self._cfg,
        )

        self._history = HistoryWindow(root=self._root)

        self._tray = TrayIcon(
            on_start_dictation=self._start_dictation,
            on_stop_dictation=self._stop_dictation,
            on_open_settings=self._settings_win.open,
            on_toggle_widget=self._floating.toggle_visibility,
            on_toggle_preview=self._preview.toggle_visibility,
            on_open_history=self._history.open,
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

        # Start background update check (15-second delay, once per day)
        self._updater.start(
            on_update_available=lambda latest, url:
                self._root.after(0, self._show_update_dialog, latest, url)
        )

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
        if self._continuous_session:
            # Second press — end the continuous session
            self._continuous_session = False
            self._stop_dictation()
        else:
            # First press — start a continuous session
            self._continuous_session = True
            self._start_dictation()

    def _start_dictation(self) -> None:
        with self._state_lock:
            if self._dictating:
                return
            self._dictating = True

        logger.info("Dictation started (continuous=%s)", self._continuous_session)
        self._set_state("active")

        # Recording limit logic
        enable_limit = self._cfg.get("enable_max_record_limit", True)
        max_sec = self._cfg.get("max_record_seconds", 30) if enable_limit else 3600

        enable_rt = self._cfg.get("enable_realtime", True)
        rt_freq = self._cfg.get("realtime_frequency_ms", 800)
        
        # Start engine-level streaming if supported (e.g. Sarvam WebSocket)
        self._active_stream_engine = None
        mode = self._cfg.get("engine_mode", "hybrid")
        if mode == "sarvam" and self._cfg.get("enable_sarvam_websocket", True):
            self._active_stream_engine = self._sarvam_engine
            self._sarvam_engine.start_stream(
                on_text=lambda text: self._root.after(0, self._preview.show_tentative_text, text),
                language=self._cfg.get("language", "auto")
            )
            logger.info("Sarvam WebSocket stream started")
        
        self._timed_capture = TimedCapture(
            vad=self._vad,
            on_complete=self._on_audio_ready,
            device_index=self._cfg.get("mic_device_index", -1),
            silence_timeout_ms=self._cfg.get("silence_timeout_ms", 1500),
            max_seconds=max_sec,
            on_level=lambda rms: self._root.after(0, self._preview.set_level, rms),
            on_chunk=self._on_audio_chunk if enable_rt else None,
            chunk_interval_ms=rt_freq,
        )
        self._timed_capture.start()

    def _stop_dictation(self) -> None:
        self._continuous_session = False
        with self._state_lock:
            if not self._dictating:
                return
            self._dictating = False

        logger.info("Dictation stopped by user")
        if self._active_stream_engine:
            self._active_stream_engine.stop_stream()
            self._active_stream_engine = None
        if self._timed_capture:
            self._timed_capture.stop()
        self._set_state("idle")

    def _on_audio_ready(self, audio_bytes: bytes) -> None:
        """Called from the capture thread when audio is ready to transcribe."""
        # If we were streaming, stop it now
        if hasattr(self, '_active_stream_engine') and self._active_stream_engine:
            self._active_stream_engine.stop_stream()
            self._active_stream_engine = None

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

    def _on_audio_chunk(self, chunk_bytes: bytes) -> None:
        """Called periodically by TimedCapture with the accumulating audio buffer."""
        # 1. Send to engine-level stream if active
        if hasattr(self, '_active_stream_engine') and self._active_stream_engine:
            self._active_stream_engine.send_chunk(chunk_bytes)
            return # Skip local fallback worker if we have a primary stream

        # 2. Otherwise fall back to local worker queue
        import queue
        try:
            # Overwrite any pending chunk so the worker gets the freshest one
            try:
                self._chunk_queue.get_nowait()
            except queue.Empty:
                pass
            self._chunk_queue.put_nowait(chunk_bytes)
        except queue.Full:
            pass

    def _chunk_worker(self) -> None:
        """Background thread that continuously processes tentative chunks."""
        while True:
            chunk_bytes = self._chunk_queue.get()
            # If we are no longer dictating, skip (the final transcription handles it)
            with self._state_lock:
                if not self._dictating:
                    continue
                    
            if not _audio_has_speech_energy(chunk_bytes):
                continue
                
            try:
                # Use the selected engine (local, cloud, or sarvam) for chunks
                res = self._run_hybrid_transcription(chunk_bytes)
                if res.success and res.text.strip():
                    text = clean_whisper_artifacts(res.text)
                    text = process_text(
                        text,
                        previous_text=self._previous_text,
                        apply_punctuation=self._cfg.get("spoken_punctuation", True),
                        apply_capitalise=self._cfg.get("auto_capitalise", True),
                    ).strip()
                    
                    if text:
                        # Display on UI
                        self._root.after(0, self._preview.show_tentative_text, text)
            except Exception as e:
                logger.debug("Chunk transcription failed: %s", e)

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

            res = self._run_hybrid_transcription(audio_bytes)
            
            if not res.success:
                error_msg = f"❌ {res.engine_name.title()} Error: {res.error}"
                logger.error(error_msg)
                self._root.after(0, self._preview.show_text, error_msg)
                self._set_state("idle")
                return

            if res.text and res.text.strip():
                text = clean_whisper_artifacts(res.text)
                text = process_text(
                    text,
                    previous_text=self._previous_text,
                    apply_punctuation=self._cfg.get("spoken_punctuation", True),
                    apply_capitalise=self._cfg.get("auto_capitalise", True),
                )
                text = self._corr.apply(text)
                
                # Polish text using LLM if enabled
                if self._cfg.get("enable_polish", False):
                    provider = self._cfg.get("polish_provider", "none")
                    action = self._cfg.get("polish_action", "Fix Grammar & Spelling")
                    custom_prompt = self._cfg.get("custom_polish_prompt", "")
                    
                    if provider == "ollama":
                        self._root.after(0, self._preview.show_status, "Polishing with Ollama…")
                        from .core.polish import polish_with_ollama
                        ollama_url = self._cfg.get("ollama_url", "http://localhost:11434")
                        ollama_model = self._cfg.get("polish_ollama_model", "llama3")
                        logger.info("Polishing text using Ollama model %s with action: %s", ollama_model, action)
                        text = polish_with_ollama(text, ollama_url, ollama_model, action, custom_prompt)
                        
                    elif provider == "gemini":
                        gemini_key = self._sec.get_gemini_key()
                        if gemini_key:
                            self._root.after(0, self._preview.show_status, "Polishing with Gemini…")
                            from .core.polish import polish_with_gemini
                            gemini_model = self._cfg.get("polish_gemini_model", "gemini-flash-lite-latest")
                            logger.info("Polishing text using Gemini model %s with action: %s", gemini_model, action)
                            text = polish_with_gemini(text, gemini_key, gemini_model, action, custom_prompt)
                        else:
                            logger.warning("Gemini polish requested but no API key found")
                
                # Strip text completely to remove any leading spaces from Whisper
                text = text.strip()
                if text:
                    logger.info("Injecting: %r", text[:80])
                    # Inject with exactly ONE trailing space to separate continuous chunks
                    self._injector.inject(text + " ")
                    
                    # Update our rolling context so the next chunk capitalizes correctly
                    self._previous_text = text + " "
                    
                    # Update overlay and history on main thread
                    self._root.after(0, self._preview.show_text, text)
                    self._root.after(0, self._history.add_entry, text)
        except Exception as exc:
            logger.exception("Transcription/injection error: %s", exc)
        finally:
            # In continuous mode, restart listening immediately after each
            # utterance so the user never has to press the hotkey again.
            # _root.after() marshals the call onto the tkinter main thread.
            if self._continuous_session:
                logger.info("Continuous session — restarting dictation")
                self._root.after(0, self._start_dictation)
            else:
                self._set_state("idle")

    def _run_hybrid_transcription(self, audio_bytes: bytes) -> TranscriptionResult:
        """
        Hybrid engine logic:
          - local:   use faster-whisper only
          - azure:   use Azure Speech only
          - gemini:  use Google Gemini only
          - sarvam:  use Sarvam AI only
          - hybrid:  try local first; fall back to azure cloud engine
        """
        mode = self._cfg.get("engine_mode", "hybrid")
        lang = self._cfg.get("language", "auto")

        if mode == "azure" or mode == "cloud": # cloud kept for compat
            return self._cloud_transcribe(audio_bytes, lang)

        if mode == "gemini":
            return self._gemini_transcribe(audio_bytes, lang)

        if mode == "sarvam":
            return self._sarvam_transcribe(audio_bytes, lang)

        if mode == "local":
            return self._local_transcribe(audio_bytes, lang)

        # Hybrid: local first
        res = self._local_transcribe(audio_bytes, lang)
        if not res.success and self._cfg.get("cloud_fallback_on_error", True):
            provider = self._cfg.get("cloud_fallback_provider", "azure")
            logger.info("Local failed — falling back to %s engine", provider)
            if provider == "gemini":
                res = self._gemini_transcribe(audio_bytes, lang)
            elif provider == "sarvam":
                res = self._sarvam_transcribe(audio_bytes, lang)
            else:
                res = self._cloud_transcribe(audio_bytes, lang)
        return res

    def _gemini_transcribe(self, audio_bytes: bytes, lang: str) -> TranscriptionResult:
        key = self._sec.get_gemini_key()
        if not key:
            return TranscriptionResult(text="", engine_name="gemini", error="API key missing")
        self._gemini_engine.update_credentials(key)
        return self._gemini_engine.transcribe(audio_bytes, language=lang)

    def _local_transcribe(self, audio_bytes: bytes, lang: str) -> TranscriptionResult:
        if not self._local_engine.is_ready:
            if not self._local_engine.load():
                return TranscriptionResult(text="", engine_name="local", error="Failed to load local model")
        return self._local_engine.transcribe(audio_bytes, language=lang)

    def _cloud_transcribe(self, audio_bytes: bytes, lang: str) -> TranscriptionResult:
        api_key = self._sec.get_azure_key()
        if not api_key:
            return TranscriptionResult(text="", engine_name="azure", error="API key missing")
        if not self._cloud_engine.is_available():
            self._cloud_engine.update_credentials(
                api_key, self._cfg.get("cloud_region", "eastus")
            )
        return self._cloud_engine.transcribe(audio_bytes, language=lang)

    def _sarvam_transcribe(self, audio_bytes: bytes, lang: str) -> TranscriptionResult:
        key = self._sec.get_sarvam_key()
        if not key:
            return TranscriptionResult(text="", engine_name="sarvam", error="API key missing")
        self._sarvam_engine.update_credentials(key)
        return self._sarvam_engine.transcribe(audio_bytes, language=lang)

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

        # Engines: reload if model or device changed
        if (cfg.model_size != self._local_engine.model_size or
                cfg.compute_type != self._local_engine.compute_type or
                cfg.local_device != self._local_engine.device):
            self._local_engine.set_model_size(cfg.model_size)
            self._local_engine.set_compute_type(cfg.compute_type)
            self._local_engine.set_device(cfg.local_device)
            threading.Thread(target=self._load_local_engine, daemon=True).start()

        # Azure key might have changed
        self._cloud_engine.update_credentials(
            self._sec.get_azure_key(),
            self._cfg.get("cloud_region", "eastus")
        )
        self._sarvam_engine.update_credentials(
            self._sec.get_sarvam_key()
        )
        self._sarvam_engine._model = self._cfg.get("sarvam_model")
        self._sarvam_engine._language = self._cfg.get("sarvam_language")
        
        self._gemini_engine.update_credentials(
            self._sec.get_gemini_key()
        )
        self._gemini_engine._model = self._cfg.get("gemini_stt_model")
        self._gemini_engine._language = self._cfg.get("gemini_stt_language")

        logger.info("Settings applied to live components")

    # ── State broadcast ────────────────────────────────────────────────────────

    def _set_state(self, state: str) -> None:
        """Thread-safe state update to all UI components."""
        self._schedule(lambda: self._apply_state(state))

    def _apply_state(self, state: str) -> None:
        self._tray.set_state(state)
        self._floating.set_state(state)
        self._preview.set_state(state)
        if state == "active":
            if self._cfg.get("enable_max_record_limit", True):
                self._floating.start_countdown(
                    float(self._cfg.get("max_record_seconds", 30)))
        else:
            self._floating.stop_countdown()

    # ── Widget moved ───────────────────────────────────────────────────────────

    def _show_update_dialog(self, latest: str, url: str) -> None:
        """Show a non-blocking update-available dialog on the main thread."""
        win = tk.Toplevel(self._root)
        win.title("Update Available")
        win.geometry("460x210")
        win.resizable(False, False)
        win.lift()
        win.grab_set()

        ttk.Label(
            win,
            text=f"DictateAnywhere {latest} is available!",
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=(20, 4))
        ttk.Label(
            win,
            text=f"You have v{_APP_VERSION}.",
            foreground="gray",
        ).pack()
        ttk.Label(
            win,
            text="Visit GitHub Releases to download the latest installer.",
            foreground="gray",
        ).pack(pady=(4, 16))

        btns = ttk.Frame(win)
        btns.pack(pady=(0, 20))

        def _download():
            webbrowser.open(url)
            win.destroy()

        def _skip():
            self._updater.skip_version(latest)
            win.destroy()

        ttk.Button(btns, text="Download",          command=_download).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Skip this version", command=_skip   ).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Remind me later",   command=win.destroy).pack(side=tk.LEFT, padx=6)

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
