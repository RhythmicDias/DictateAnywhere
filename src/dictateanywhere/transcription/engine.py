"""
Abstract STT engine base class.

All concrete engines (local faster-whisper, Azure cloud) implement this
interface so the orchestrator can swap between them transparently.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

logger = logging.getLogger(__name__)


class EngineStatus(Enum):
    UNLOADED = auto()
    LOADING = auto()
    READY = auto()
    BUSY = auto()
    ERROR = auto()
    UNAVAILABLE = auto()


@dataclass
class TranscriptionResult:
    text: str
    language: Optional[str] = None
    confidence: Optional[float] = None       # 0.0 – 1.0 if available
    engine_name: str = "unknown"
    duration_ms: Optional[float] = None      # processing time
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return not self.error and bool(self.text.strip())


class STTEngine(ABC):
    """Base class for all STT engines."""

    name: str = "base"

    def __init__(self) -> None:
        self._status = EngineStatus.UNLOADED

    @property
    def status(self) -> EngineStatus:
        return self._status

    @property
    def is_ready(self) -> bool:
        return self._status == EngineStatus.READY

    # ── Abstract interface ─────────────────────────────────────────────────────

    @abstractmethod
    def load(self) -> bool:
        """
        Initialise the engine (download model, authenticate, etc.).
        Returns True on success.
        """

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, language: str = "en") -> TranscriptionResult:
        """
        Transcribe raw 16 kHz mono int16 PCM *audio_bytes*.
        Returns a TranscriptionResult.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return True if the engine can be used right now
        (model loaded / API key present / network reachable).
        """

    def unload(self) -> None:
        """Release resources. Override if needed."""
        self._status = EngineStatus.UNLOADED

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _log_result(self, result: TranscriptionResult) -> None:
        if result.success:
            logger.info(
                "[%s] transcribed in %.0f ms: %r",
                self.name,
                result.duration_ms or 0,
                result.text[:80],
            )
        elif result.error:
            logger.warning("[%s] failed: %s", self.name, result.error)
        else:
            # Empty text but no error — VAD filtered out everything (silence / no speech)
            logger.info("[%s] no speech detected", self.name)
