# sidecar/whisper_sidecar.py
import os
import sys
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Add src/ to path for development/testing
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Configure logging to go to stderr so it doesn't corrupt stdout JSON lines
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("whisper_sidecar")

# Fix for MKL/OpenMP conflicts on Windows that can cause hangs in faster-whisper
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

def _setup_nvidia_dlls():
    """Add NVIDIA library paths from site-packages to DLL search path on Windows."""
    if sys.platform != "win32":
        return
    
    # If running inside a PyInstaller bundle, add the bundle folder
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            try:
                os.add_dll_directory(meipass)
                logger.info(f"Added PyInstaller bundle directory: {meipass}")
            except Exception as e:
                logger.warning(f"Failed to add PyInstaller bundle directory to DLL search path: {e}")
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
                            logger.info(f"Added NVIDIA DLL directory: {bin_dir}")
                            found = True
                        except Exception:
                            pass
    except Exception as e:
        logger.warning(f"Failed to auto-setup NVIDIA DLL paths: {e}")
    
    if not found:
        # Fallback: check if we are in a venv and look there directly
        venv_path = Path(sys.prefix)
        nvidia_venv = venv_path / "Lib" / "site-packages" / "nvidia"
        if nvidia_venv.exists():
             for bin_dir in nvidia_venv.glob("**/bin"):
                if bin_dir.is_dir():
                    try:
                        os.add_dll_directory(str(bin_dir))
                        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
                        logger.info(f"Added NVIDIA DLL directory (venv fallback): {bin_dir}")
                    except Exception:
                        pass

_setup_nvidia_dlls()

try:
    import tqdm
    tqdm.tqdm.monitor_interval = 0
except ImportError:
    pass

from dictateanywhere.utils.config import ConfigManager
from dictateanywhere.audio.capture import TimedCapture
from dictateanywhere.audio.vad import VADFilter
from dictateanywhere.transcription.local_engine import LocalEngine
from dictateanywhere.transcription.cloud_engine import CloudEngine
from dictateanywhere.transcription.sarvam_engine import SarvamEngine
from dictateanywhere.transcription.gemini_engine import GeminiEngine
from dictateanywhere.transcription.engine import TranscriptionResult
from dictateanywhere.core.punctuation import process as process_text, clean_whisper_artifacts
from dictateanywhere.core.corrections import CorrectionsManager

_SPEECH_ENERGY_THRESHOLD = 0.0005

def _audio_has_speech_energy(audio_bytes: bytes, threshold: float = _SPEECH_ENERGY_THRESHOLD) -> bool:
    if not audio_bytes:
        return False
    import numpy as np
    arr = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(arr ** 2)))
    logger.info("Audio RMS: %.5f (silence gate: %.4f)", rms, threshold)
    return rms >= threshold

class SidecarRunner:
    def __init__(self) -> None:
        self.cfg = ConfigManager()
        self.corr = CorrectionsManager(self.cfg.config_dir() / "corrections.json")
        self.state_lock = threading.Lock()
        self.dictating = False
        self.timed_capture: Optional[TimedCapture] = None
        self.previous_text = ""
        
        # Lazy initialized engines
        self.local_engine: Optional[LocalEngine] = None
        self.cloud_engine: Optional[CloudEngine] = None
        self.sarvam_engine: Optional[SarvamEngine] = None
        self.gemini_engine: Optional[GeminiEngine] = None

    def preload_local_engine(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Pre-load the local engine in a background thread."""
        threading.Thread(target=self._do_preload, args=(params,), daemon=True).start()

    def _do_preload(self, params: Optional[Dict[str, Any]]) -> None:
        try:
            p = params or {}
            model_size = p.get("model_size", self.cfg.get("model_size", "small"))
            compute_type = p.get("compute_type", self.cfg.get("compute_type", "int8"))
            device = p.get("local_device", self.cfg.get("local_device", "auto"))
            lang = p.get("language", self.cfg.get("language", "auto"))
            mode = p.get("engine_mode", self.cfg.get("engine_mode", "hybrid"))

            if mode not in ("local", "hybrid"):
                return

            if not self.local_engine:
                self.local_engine = LocalEngine(
                    model_size=model_size,
                    compute_type=compute_type,
                    device=device,
                    language=lang
                )
            else:
                if model_size != self.local_engine.model_size:
                    self.local_engine.set_model_size(model_size)
                if compute_type != self.local_engine.compute_type:
                    self.local_engine.set_compute_type(compute_type)
                if device != self.local_engine.device:
                    self.local_engine.set_device(device)
                self.local_engine.set_language(lang)

            if not self.local_engine.is_ready:
                logger.info(f"Pre-loading local Whisper model in background (size={model_size}, device={device}, compute={compute_type}) ...")
                self.local_engine.load()
        except Exception as e:
            logger.error(f"Error during background model pre-loading: {e}")

    def send_event(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        msg = {"type": event_type}
        if data:
            msg.update(data)
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()

    def start_dictation(self, params: Dict[str, Any], api_keys: Dict[str, str]) -> None:
        if params:
            try:
                self.cfg.update(params)
            except Exception as e:
                logger.warning(f"Failed to update sidecar config cache: {e}")

        # Pre-load the Whisper model in parallel while the user is dictating
        self.preload_local_engine(params)

        with self.state_lock:
            if self.dictating:
                logger.warning("Already dictating, ignoring start command")
                return
            self.dictating = True

        # Extract config params with fallbacks from ConfigManager
        mic_index = params.get("mic_device_index", self.cfg.get("mic_device_index", -1))
        silence_timeout = params.get("silence_timeout_ms", self.cfg.get("silence_timeout_ms", 2500))
        max_record_sec = params.get("max_record_seconds", self.cfg.get("max_record_seconds", 30))
        enable_limit = params.get("enable_max_record_limit", self.cfg.get("enable_max_record_limit", True))
        vad_aggressiveness = params.get("vad_aggressiveness", self.cfg.get("vad_aggressiveness", 1))

        logger.info(f"Starting dictation. mic={mic_index}, silence_timeout={silence_timeout}, max_record_sec={max_record_sec}")

        self.send_event("state", {"state": "active"})

        vad = VADFilter(aggressiveness=vad_aggressiveness)
        max_sec = max_record_sec if enable_limit else 3600

        # Create TimedCapture
        self.timed_capture = TimedCapture(
            vad=vad,
            on_complete=lambda audio: self.on_audio_ready(audio, params, api_keys),
            device_index=mic_index,
            silence_timeout_ms=silence_timeout,
            max_seconds=max_sec,
            on_level=lambda rms: self.send_event("audio_level", {"rms": rms}),
        )
        self.timed_capture.start()

    def stop_dictation(self) -> None:
        with self.state_lock:
            if not self.dictating:
                return
            self.dictating = False

        logger.info("Stopping dictation by user command")
        if self.timed_capture:
            self.timed_capture.stop()
        self.send_event("state", {"state": "idle"})

    def on_audio_ready(self, audio_bytes: bytes, params: Dict[str, Any], api_keys: Dict[str, str]) -> None:
        with self.state_lock:
            self.dictating = False
        
        self.send_event("state", {"state": "loading"})
        
        # Run transcription on a worker thread
        threading.Thread(
            target=self.transcribe_and_process,
            args=(audio_bytes, params, api_keys),
            daemon=True
        ).start()

    def transcribe_and_process(self, audio_bytes: bytes, params: Dict[str, Any], api_keys: Dict[str, str]) -> None:
        try:
            if not _audio_has_speech_energy(audio_bytes):
                logger.info("Audio energy below threshold — skipping transcription")
                self.send_event("result", {"text": "", "engine": ""})
                self.send_event("state", {"state": "idle"})
                return

            res = self.run_hybrid_transcription(audio_bytes, params, api_keys)
            
            if res.error:
                error_msg = f"Error: {res.error}"
                logger.error(f"Transcription failed: {error_msg}")
                self.send_event("error", {"message": error_msg})
                self.send_event("state", {"state": "error"})
                return

            text = res.text
            if text and text.strip():
                text = clean_whisper_artifacts(text)
                spoken_punctuation = params.get("spoken_punctuation", self.cfg.get("spoken_punctuation", True))
                auto_capitalise = params.get("auto_capitalise", self.cfg.get("auto_capitalise", True))
                
                text = process_text(
                    text,
                    previous_text=self.previous_text,
                    apply_punctuation=spoken_punctuation,
                    apply_capitalise=auto_capitalise,
                )
                text = self.corr.apply(text)

                # Check for voice launch commands
                cleaned_phrase = text.strip().lower()
                for char in [".", ",", "!", "?", "\"", "'"]:
                    if cleaned_phrase.endswith(char):
                        cleaned_phrase = cleaned_phrase[:-1]
                cleaned_phrase = cleaned_phrase.strip()

                commands = params.get("app_launcher_commands", self.cfg.get("app_launcher_commands", {}))
                matched_path = None
                for cmd, path in commands.items():
                    normalized_cmd = cmd.strip().lower()
                    for char in [".", ",", "!", "?", "\"", "'"]:
                        if normalized_cmd.endswith(char):
                            normalized_cmd = normalized_cmd[:-1]
                    normalized_cmd = normalized_cmd.strip()

                    if cleaned_phrase == normalized_cmd:
                        matched_path = path
                        break

                if matched_path:
                    logger.info(f"Voice command matched: {text!r} -> launching {matched_path}")
                    self.send_event("launch", {"path": matched_path})
                    try:
                        if sys.platform == "win32":
                            os.startfile(matched_path)
                        else:
                            import subprocess
                            subprocess.Popen([matched_path])
                    except Exception as e:
                        logger.error(f"Failed to launch app {matched_path}: {e}")
                        self.send_event("error", {"message": f"Launch failed: {e}"})
                    self.send_event("state", {"state": "idle"})
                    return

                # Text Polish
                enable_polish = params.get("enable_polish", self.cfg.get("enable_polish", False))
                polished = False
                polish_provider = "none"
                polish_model = ""
                polish_status = "disabled"
                polish_error = ""

                raw_text = text # Keep original Whisper text

                if enable_polish:
                    provider = params.get("polish_provider", self.cfg.get("polish_provider", "none"))
                    action = params.get("polish_action", self.cfg.get("polish_action", "Fix Grammar & Spelling"))
                    custom_prompt = params.get("custom_polish_prompt", self.cfg.get("custom_polish_prompt", ""))
                    polish_provider = provider
                    
                    if provider == "ollama":
                        self.send_event("state", {"state": "polishing"})
                        from dictateanywhere.core.polish import polish_with_ollama
                        ollama_url = params.get("ollama_url", self.cfg.get("ollama_url", "http://localhost:11434"))
                        ollama_model = params.get("polish_ollama_model", self.cfg.get("polish_ollama_model", "llama3"))
                        polish_model = ollama_model
                        timeout = float(params.get("polish_ollama_timeout", self.cfg.get("polish_ollama_timeout", 90.0)))
                        logger.info(f"Polishing text using Ollama model {ollama_model} with action: {action} (timeout={timeout}s)")
                        text, success, err = polish_with_ollama(text, ollama_url, ollama_model, action, custom_prompt, timeout=timeout)
                        polished = True
                        polish_status = "success" if success else "failed"
                        polish_error = err
                        
                    elif provider == "gemini":
                        gemini_key = api_keys.get("gemini")
                        if gemini_key:
                            self.send_event("state", {"state": "polishing"})
                            from dictateanywhere.core.polish import polish_with_gemini
                            gemini_model = params.get("polish_gemini_model", self.cfg.get("polish_gemini_model", "gemini-flash-lite-latest"))
                            polish_model = gemini_model
                            logger.info(f"Polishing text using Gemini model {gemini_model} with action: {action}")
                            text, success, err = polish_with_gemini(text, gemini_key, gemini_model, action, custom_prompt)
                            polished = True
                            polish_status = "success" if success else "failed"
                            polish_error = err
                        else:
                            logger.warning("Gemini polish requested but no API key found")
                            polish_status = "failed"
                            polish_error = "API key missing"

                    elif provider == "openrouter":
                        openrouter_key = api_keys.get("openrouter")
                        if openrouter_key:
                            self.send_event("state", {"state": "polishing"})
                            from dictateanywhere.core.polish import polish_with_openrouter
                            openrouter_model = params.get("polish_openrouter_model", self.cfg.get("polish_openrouter_model", ""))
                            polish_model = openrouter_model
                            logger.info(f"Polishing text using OpenRouter model {openrouter_model} with action: {action}")
                            text, success, err = polish_with_openrouter(text, openrouter_key, openrouter_model, action, custom_prompt)
                            polished = True
                            polish_status = "success" if success else "failed"
                            polish_error = err
                        else:
                            logger.warning("OpenRouter polish requested but no API key found")
                            polish_status = "failed"
                            polish_error = "API key missing"

                    elif provider == "groq":
                        groq_key = api_keys.get("groq")
                        if groq_key:
                            self.send_event("state", {"state": "polishing"})
                            from dictateanywhere.core.polish import polish_with_groq
                            groq_model = params.get("polish_groq_model", self.cfg.get("polish_groq_model", ""))
                            polish_model = groq_model
                            logger.info(f"Polishing text using Groq model {groq_model} with action: {action}")
                            text, success, err = polish_with_groq(text, groq_key, groq_model, action, custom_prompt)
                            polished = True
                            polish_status = "success" if success else "failed"
                            polish_error = err
                        else:
                            logger.warning("Groq polish requested but no API key found")
                            polish_status = "failed"
                            polish_error = "API key missing"


                text = text.strip()
                if text:
                    self.send_event("state", {"state": "injecting"})
                    self.send_event("result", {
                        "text": text,
                        "raw_text": raw_text,
                        "engine": res.engine_name,
                        "polished": polished,
                        "polish_provider": polish_provider,
                        "polish_model": polish_model,
                        "polish_status": polish_status,
                        "polish_error": polish_error
                    })
                    self.previous_text = text + " "
                    self.send_event("state", {"state": "idle"})
                    return

            self.send_event("result", {"text": "", "engine": ""})
            self.send_event("state", {"state": "idle"})

        except Exception as exc:
            logger.exception("Error in transcription/injection pipeline")
            self.send_event("error", {"message": str(exc)})
            self.send_event("state", {"state": "error"})

    def _resolve_cloud_provider(self, params: Dict[str, Any]) -> str:
        prov = params.get("cloud_provider") or self.cfg.get("cloud_provider")
        if not prov:
            prov = params.get("cloud_fallback_provider") or self.cfg.get("cloud_fallback_provider")
        return prov or "azure"

    def run_hybrid_transcription(self, audio_bytes: bytes, params: Dict[str, Any], api_keys: Dict[str, Any]) -> TranscriptionResult:
        mode = params.get("engine_mode", self.cfg.get("engine_mode", "hybrid"))
        lang = params.get("language", self.cfg.get("language", "auto"))

        if mode == "azure":
            return self.cloud_transcribe(audio_bytes, lang, api_keys, params)

        if mode == "gemini":
            return self.gemini_transcribe(audio_bytes, lang, api_keys, params)

        if mode == "sarvam":
            return self.sarvam_transcribe(audio_bytes, lang, api_keys, params)

        if mode == "cloud":
            provider = self._resolve_cloud_provider(params)
            logger.info(f"Cloud mode active — routing to {provider} cloud STT engine")
            if provider == "gemini":
                return self.gemini_transcribe(audio_bytes, lang, api_keys, params)
            elif provider == "sarvam":
                return self.sarvam_transcribe(audio_bytes, lang, api_keys, params)
            else:
                return self.cloud_transcribe(audio_bytes, lang, api_keys, params)

        if mode == "local":
            return self.local_transcribe(audio_bytes, lang, params)

        # Hybrid: local first
        res = self.local_transcribe(audio_bytes, lang, params)
        if res.error and params.get("cloud_fallback_on_error", self.cfg.get("cloud_fallback_on_error", True)):
            provider = self._resolve_cloud_provider(params)
            logger.info(f"Local failed — falling back to {provider} cloud engine")
            if provider == "gemini":
                res = self.gemini_transcribe(audio_bytes, lang, api_keys, params)
            elif provider == "sarvam":
                res = self.sarvam_transcribe(audio_bytes, lang, api_keys, params)
            else:
                res = self.cloud_transcribe(audio_bytes, lang, api_keys, params)
        return res

    def local_transcribe(self, audio_bytes: bytes, lang: str, params: Dict[str, Any]) -> TranscriptionResult:
        model_size = params.get("model_size", self.cfg.get("model_size", "small"))
        compute_type = params.get("compute_type", self.cfg.get("compute_type", "int8"))
        device = params.get("local_device", self.cfg.get("local_device", "auto"))

        if not self.local_engine:
            self.local_engine = LocalEngine(
                model_size=model_size,
                compute_type=compute_type,
                device=device,
                language=lang
            )
        else:
            # Reconfigure dynamically if config changed
            if model_size != self.local_engine.model_size:
                self.local_engine.set_model_size(model_size)
            if compute_type != self.local_engine.compute_type:
                self.local_engine.set_compute_type(compute_type)
            if device != self.local_engine.device:
                self.local_engine.set_device(device)
            self.local_engine.set_language(lang)

        if not self.local_engine.is_ready:
            ok = self.local_engine.load()
            if not ok:
                return TranscriptionResult(text="", engine_name="local", error="Failed to load local Whisper model")

        return self.local_engine.transcribe(audio_bytes, language=lang)

    def cloud_transcribe(self, audio_bytes: bytes, lang: str, api_keys: Dict[str, String], params: Dict[str, Any]) -> TranscriptionResult:
        key = api_keys.get("azure")
        region = params.get("cloud_region", self.cfg.get("cloud_region", "eastus"))
        if not key:
            return TranscriptionResult(text="", engine_name="azure", error="Azure API key missing")

        if not self.cloud_engine:
            self.cloud_engine = CloudEngine(api_key=key, region=region, language=lang)
        else:
            self.cloud_engine.update_credentials(key, region)
            self.cloud_engine.set_language(lang)

        return self.cloud_engine.transcribe(audio_bytes, language=lang)

    def gemini_transcribe(self, audio_bytes: bytes, lang: str, api_keys: Dict[str, String], params: Dict[str, Any]) -> TranscriptionResult:
        key = api_keys.get("gemini")
        model = params.get("gemini_stt_model", self.cfg.get("gemini_stt_model", "gemini-flash-lite-latest"))
        if not key:
            return TranscriptionResult(text="", engine_name="gemini", error="Gemini API key missing")

        if not self.gemini_engine:
            self.gemini_engine = GeminiEngine(api_key=key, model=model, language=lang)
        else:
            self.gemini_engine.update_credentials(key)
            self.gemini_engine._model = model
            self.gemini_engine._language = lang

        return self.gemini_engine.transcribe(audio_bytes, language=lang)

    def sarvam_transcribe(self, audio_bytes: bytes, lang: str, api_keys: Dict[str, String], params: Dict[str, Any]) -> TranscriptionResult:
        key = api_keys.get("sarvam")
        model = params.get("sarvam_model", self.cfg.get("sarvam_model", "saarika:v2.5"))
        if not key:
            return TranscriptionResult(text="", engine_name="sarvam", error="Sarvam API key missing")

        if not self.sarvam_engine:
            self.sarvam_engine = SarvamEngine(api_key=key, model=model, language=lang)
        else:
            self.sarvam_engine.update_credentials(key)
            self.sarvam_engine._model = model
            self.sarvam_engine._language = lang

        return self.sarvam_engine.transcribe(audio_bytes, language=lang)

def main():
    if "--list-devices" in sys.argv:
        try:
            from dictateanywhere.audio.capture import list_input_devices
            devices = list_input_devices()
            sys.stdout.write(json.dumps(devices) + "\n")
            sys.stdout.flush()
        except Exception as e:
            logger.exception("Failed to list audio input devices")
            sys.stderr.write(str(e) + "\n")
            sys.stderr.flush()
            sys.exit(1)
        return

    logger.info("Whisper sidecar runner started")
    runner = SidecarRunner()
    runner.preload_local_engine()
    runner.send_event("ready")

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        if not line.strip():
            continue
        try:
            msg = json.loads(line.strip())
            cmd = msg.get("cmd")
            if cmd == "ping":
                runner.send_event("pong")
            elif cmd == "start":
                params = msg.get("config", {})
                api_keys = msg.get("api_keys", {})
                runner.start_dictation(params, api_keys)
            elif cmd == "stop":
                runner.stop_dictation()
            else:
                logger.warning(f"Unknown command: {cmd}")
        except Exception as e:
            logger.exception("Error processing line from stdin")
            runner.send_event("error", {"message": f"IPC Parse error: {e}"})

if __name__ == "__main__":
    main()
