"""
Local STT engine using faster-whisper.

Downloads the chosen model on first use (cached in %APPDATA%/DictateAnywhere/models/).
Runs entirely offline. CPU-optimised via int8 quantisation by default.
"""

from __future__ import annotations

import io
import logging
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

from .engine import EngineStatus, STTEngine, TranscriptionResult
from ..utils.config import app_data_dir

logger = logging.getLogger(__name__)

MODELS_DIR = app_data_dir() / "models"
SUPPORTED_MODELS = ("tiny", "base", "small", "medium", "large-v2", "large-v3")


class LocalEngine(STTEngine):
    """
    faster-whisper backed local transcription engine.

    Model is loaded once into memory and reused across all transcriptions.
    """

    name = "local (faster-whisper)"

    def __init__(
        self,
        model_size: str = "small",
        compute_type: str = "int8",    # int8 = best CPU speed; float16 for GPU
        device: str = "auto",          # cpu | cuda | auto
        language: str = "en",
    ) -> None:
        super().__init__()
        self._model_size = model_size if model_size in SUPPORTED_MODELS else "small"
        self._compute_type = compute_type
        self._device = device
        self._language = language
        self._model = None
        self._lock = threading.Lock()
        MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Properties ─────────────────────────────────────────────────────────────

    @property
    def model_size(self) -> str:
        return self._model_size

    @property
    def compute_type(self) -> str:
        return self._compute_type

    @property
    def device(self) -> str:
        return self._device

    # ── STTEngine interface ────────────────────────────────────────────────────

    def load(self) -> bool:
        """Load (or download) the Whisper model. Blocks until ready."""
        if self._status == EngineStatus.READY:
            return True
        self._status = EngineStatus.LOADING
        try:
            import ctranslate2
            import faster_whisper
            logger.info("ctranslate2 version: %s", ctranslate2.__version__)
            logger.info("faster-whisper version: %s", faster_whisper.__version__)
            from faster_whisper import WhisperModel

            logger.info(
                "Loading faster-whisper model %r (device=%s, compute_type=%s) …",
                self._model_size,
                self._device,
                self._compute_type,
            )
            t0 = time.monotonic()
            
            try:
                self._model = WhisperModel(
                    self._model_size,
                    device=self._device,
                    compute_type=self._compute_type,
                    download_root=str(MODELS_DIR),
                    cpu_threads=4,
                )
            except Exception as e:
                # Handle common float16 / CPU mismatch OR CUDA initialization failures
                err_str = str(e).lower()
                is_cuda_err = (self._device == "cuda") or ("cuda" in err_str) or ("cublas" in err_str) or ("cudnn" in err_str)
                is_float16_cpu_err = ("float16" in err_str and self._device != "cuda")

                if is_float16_cpu_err or is_cuda_err:
                    fallback_reason = "float16 on CPU" if is_float16_cpu_err else f"Hardware acceleration failed ({e})"
                    logger.warning("%s. Falling back to int8/cpu.", fallback_reason)
                    self._device = "cpu"
                    self._compute_type = "int8"
                    try:
                        from faster_whisper import WhisperModel
                        self._model = WhisperModel(
                            self._model_size,
                            device="cpu",
                            compute_type="int8",
                            download_root=str(MODELS_DIR),
                            cpu_threads=4,
                        )
                        logger.info("Successfully fell back to CPU engine")
                    except Exception as fallback_err:
                        logger.error("Critical: Fallback to CPU also failed: %s", fallback_err)
                        raise fallback_err
                else:
                    raise e

            elapsed = time.monotonic() - t0
            logger.info("Model loaded in %.1f s", elapsed)
            self._status = EngineStatus.READY
            return True
        except Exception as exc:
            logger.error("Failed to load faster-whisper model: %s", exc)
            self._status = EngineStatus.ERROR
            return False

    def transcribe(self, audio_bytes: bytes, language: str = "en") -> TranscriptionResult:
        """Transcribe raw 16 kHz mono int16 PCM bytes."""
        if not self.is_ready:
            return TranscriptionResult(
                text="", engine_name=self.name,
                error="Engine not loaded — call load() first"
            )

        try:
            self._status = EngineStatus.BUSY
            audio_array = _pcm_to_float32(audio_bytes)

            logger.info("Transcribing audio (%.1f s) with Whisper model %s ...", len(audio_array) / 16000.0, self._model_size)
            t0 = time.monotonic()
            lang_code = language or self._language
            if lang_code == "auto":
                lang_code = None

            with self._lock:
                segments, info = self._model.transcribe(  # type: ignore[union-attr]
                    audio_array,
                    language=lang_code,
                    beam_size=1,
                    best_of=1,
                    temperature=0.0,
                    # Disable internal VAD filter if it's causing issues, 
                    # as we already have a high-quality capture-level VAD.
                    vad_filter=False, 
                    word_timestamps=False,
                    condition_on_previous_text=False,
                )

                logger.info("Detected language: %s (prob: %.3f)", info.language, info.language_probability)

                text_parts = []
                logger.info("Iterating segments ...")
                try:
                    for seg in segments:
                        if seg.text.strip():
                            text_parts.append(seg.text.strip())
                            logger.debug("Whisper segment: %r", seg.text)
                except (RuntimeError, Exception) as seg_err:
                    err_str = str(seg_err).lower()
                    if any(x in err_str for x in ["cublas", "cuda", "cudnn", "load library"]):
                        logger.error("CUDA error during segment iteration: %s. Forcing CPU fallback.", seg_err)
                        self._device = "cpu"
                        self._compute_type = "int8"
                        self.unload()
                        if self.load():
                            # Recursive retry with safe settings
                            return self.transcribe(audio_bytes, language)
                    
                    logger.error("Error during segment iteration: %s", seg_err)
                    raise seg_err

            text = " ".join(text_parts).strip()
            logger.info("Transcription finished. Text length: %d", len(text))
            elapsed_ms = (time.monotonic() - t0) * 1000

            result = TranscriptionResult(
                text=text,
                language=info.language,
                confidence=None,
                engine_name=self.name,
                duration_ms=elapsed_ms,
            )
            self._log_result(result)
            return result

        except Exception as exc:
            logger.exception("faster-whisper transcription error")
            return TranscriptionResult(
                text="", engine_name=self.name, error=str(exc)
            )
        finally:
            self._status = EngineStatus.READY

    def is_available(self) -> bool:
        """Local engine is always available once loaded."""
        return self._status in (EngineStatus.READY, EngineStatus.BUSY)

    def unload(self) -> None:
        """Release model from memory."""
        self._model = None
        self._status = EngineStatus.UNLOADED
        logger.info("Local engine unloaded")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def set_model_size(self, model_size: str) -> None:
        if model_size not in SUPPORTED_MODELS:
            raise ValueError(f"Unknown model size: {model_size!r}")
        if model_size != self._model_size:
            self._model_size = model_size
            self.unload()

    def set_language(self, language: str) -> None:
        self._language = language

    def set_compute_type(self, compute_type: str) -> None:
        if compute_type != self._compute_type:
            self._compute_type = compute_type
            self.unload()

    def set_device(self, device: str) -> None:
        if device != self._device:
            self._device = device
            self.unload()


def _pcm_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """Convert raw int16 PCM bytes to a normalised float32 numpy array."""
    int16_array = np.frombuffer(pcm_bytes, dtype=np.int16)
    return int16_array.astype(np.float32) / 32768.0
