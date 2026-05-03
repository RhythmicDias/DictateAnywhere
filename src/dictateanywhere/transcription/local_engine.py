"""
Local STT engine using faster-whisper.

Downloads the chosen model on first use (cached in %APPDATA%/DictateAnywhere/models/).
Runs entirely offline. CPU-optimised via int8 quantisation by default.
"""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np

from .engine import EngineStatus, STTEngine, TranscriptionResult
from ..utils.config import _app_data_dir

logger = logging.getLogger(__name__)

MODELS_DIR = _app_data_dir() / "models"
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
        language: str = "en",
    ) -> None:
        super().__init__()
        self._model_size = model_size if model_size in SUPPORTED_MODELS else "small"
        self._compute_type = compute_type
        self._language = language
        self._model = None
        MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # ── STTEngine interface ────────────────────────────────────────────────────

    def load(self) -> bool:
        """Load (or download) the Whisper model. Blocks until ready."""
        if self._status == EngineStatus.READY:
            return True
        self._status = EngineStatus.LOADING
        try:
            from faster_whisper import WhisperModel

            logger.info(
                "Loading faster-whisper model %r (compute_type=%s) …",
                self._model_size,
                self._compute_type,
            )
            t0 = time.monotonic()
            self._model = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type=self._compute_type,
                download_root=str(MODELS_DIR),
            )
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

            t0 = time.monotonic()
            segments, info = self._model.transcribe(  # type: ignore[union-attr]
                audio_array,
                language=language or self._language or None,
                beam_size=5,
                best_of=5,
                temperature=0.0,
                # Use a permissive VAD threshold (0.3 vs default 0.5) so
                # Whisper's internal filter catches hallucinations on near-silence
                # without stripping real speech that webrtcvad already passed.
                vad_filter=True,
                vad_parameters={
                    "threshold": 0.3,
                    "min_speech_duration_ms": 100,
                    "min_silence_duration_ms": 200,
                },
                word_timestamps=False,
                condition_on_previous_text=True,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
            )

            text_parts = [seg.text for seg in segments]
            text = " ".join(text_parts).strip()
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


def _pcm_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """Convert raw int16 PCM bytes to a normalised float32 numpy array."""
    int16_array = np.frombuffer(pcm_bytes, dtype=np.int16)
    return int16_array.astype(np.float32) / 32768.0
