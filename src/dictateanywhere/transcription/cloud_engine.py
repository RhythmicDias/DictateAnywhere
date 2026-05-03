"""
Cloud STT engine using Azure Cognitive Services Speech SDK.

Requires:
  - An Azure Speech resource (free tier: 5 h/month)
  - SPEECH_KEY stored in Windows Credential Manager (via SecureStorage)
  - SPEECH_REGION from config (e.g. "eastus")

Zero Whisper model download needed; processing runs in Azure's data centres.
CPU overhead is minimal — just audio streaming and SDK threads.
"""

from __future__ import annotations

import io
import logging
import threading
import time
import wave
from typing import Optional

from .engine import EngineStatus, STTEngine, TranscriptionResult

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH = 2  # int16 = 2 bytes


class CloudEngine(STTEngine):
    """Azure Speech SDK based cloud transcription engine."""

    name = "cloud (Azure Speech)"

    def __init__(
        self,
        api_key: Optional[str] = None,
        region: str = "eastus",
        language: str = "en-US",
    ) -> None:
        super().__init__()
        self._api_key = api_key
        self._region = region
        self._language = language

    # ── STTEngine interface ────────────────────────────────────────────────────

    def load(self) -> bool:
        """Validate credentials and import the Azure SDK."""
        if not self._api_key:
            logger.warning("Azure API key not set — cloud engine unavailable")
            self._status = EngineStatus.UNAVAILABLE
            return False
        try:
            import azure.cognitiveservices.speech as speechsdk  # noqa: F401
            self._status = EngineStatus.READY
            logger.info("Azure Speech SDK ready (region=%s)", self._region)
            return True
        except ImportError:
            logger.error(
                "azure-cognitiveservices-speech not installed. "
                "Run: pip install azure-cognitiveservices-speech"
            )
            self._status = EngineStatus.UNAVAILABLE
            return False

    def transcribe(self, audio_bytes: bytes, language: str = "en-US") -> TranscriptionResult:
        """
        Send PCM audio to Azure Speech and return the transcript.

        *audio_bytes* must be 16 kHz mono int16 PCM.
        """
        if self._status == EngineStatus.UNAVAILABLE:
            return TranscriptionResult(
                text="", engine_name=self.name,
                error="Azure engine unavailable — check API key and region"
            )

        if not self._api_key:
            return TranscriptionResult(
                text="", engine_name=self.name, error="Azure API key not configured"
            )

        try:
            import azure.cognitiveservices.speech as speechsdk

            self._status = EngineStatus.BUSY
            t0 = time.monotonic()

            # Wrap PCM in WAV container for the push stream
            wav_bytes = _pcm_to_wav(audio_bytes)
            lang = language or self._language

            speech_config = speechsdk.SpeechConfig(
                subscription=self._api_key,
                region=self._region,
            )
            speech_config.speech_recognition_language = lang
            speech_config.set_property(
                speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, "1500"
            )
            speech_config.enable_dictation()

            audio_format = speechsdk.audio.AudioStreamFormat(
                samples_per_second=SAMPLE_RATE,
                bits_per_sample=16,
                channels=CHANNELS,
            )
            push_stream = speechsdk.audio.PushAudioInputStream(audio_format)
            audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

            recogniser = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config,
            )

            # Push all audio then signal EOF
            push_stream.write(wav_bytes)
            push_stream.close()

            result = recogniser.recognize_once_async().get()

            elapsed_ms = (time.monotonic() - t0) * 1000

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                tr = TranscriptionResult(
                    text=result.text,
                    language=lang,
                    engine_name=self.name,
                    duration_ms=elapsed_ms,
                )
            elif result.reason == speechsdk.ResultReason.NoMatch:
                tr = TranscriptionResult(
                    text="", engine_name=self.name,
                    error="Azure: no speech detected"
                )
            else:
                details = speechsdk.CancellationDetails.from_result(result)
                tr = TranscriptionResult(
                    text="", engine_name=self.name,
                    error=f"Azure cancelled: {details.reason} — {details.error_details}"
                )

            self._log_result(tr)
            return tr

        except Exception as exc:
            logger.exception("Azure Speech transcription error")
            return TranscriptionResult(
                text="", engine_name=self.name, error=str(exc)
            )
        finally:
            self._status = EngineStatus.READY

    def is_available(self) -> bool:
        return bool(self._api_key) and self._status in (
            EngineStatus.READY, EngineStatus.BUSY
        )

    # ── Configuration ──────────────────────────────────────────────────────────

    def update_credentials(self, api_key: str, region: str) -> None:
        self._api_key = api_key
        self._region = region
        self._status = EngineStatus.UNLOADED
        self.load()

    def set_language(self, language: str) -> None:
        self._language = language


def _pcm_to_wav(pcm_bytes: bytes) -> bytes:
    """Wrap raw int16 PCM bytes in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()
