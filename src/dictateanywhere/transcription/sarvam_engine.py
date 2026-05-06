"""
Sarvam AI STT engine.
Excellent for Indian languages.
"""

from __future__ import annotations

import io
import logging
import time
import wave
from typing import Optional

import requests

from .engine import EngineStatus, STTEngine, TranscriptionResult

logger = logging.getLogger(__name__)

URL = "https://api.sarvam.ai/speech-to-text"


class SarvamEngine(STTEngine):
    """
    STT engine powered by Sarvam AI.
    Requires an API key from https://www.sarvam.ai/
    """

    name = "cloud (Sarvam AI)"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "saarika:v2.5",
        language: str = "hi-IN",
    ) -> None:
        super().__init__()
        self._api_key = api_key
        self._model = model
        self._language = language

    def update_credentials(self, api_key: str) -> None:
        self._api_key = api_key

    def load(self) -> bool:
        """Sarvam is a cloud API, no local loading needed."""
        self._status = EngineStatus.READY
        return True

    def is_available(self) -> bool:
        return bool(self._api_key)

    def transcribe(self, audio_bytes: bytes, language: str = "") -> TranscriptionResult:
        if not self._api_key:
            return TranscriptionResult(
                text="", engine_name=self.name, error="Sarvam API key missing"
            )

        try:
            self._status = EngineStatus.BUSY
            t0 = time.monotonic()

            # Wrap raw PCM in a WAV container
            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)  # 16-bit
                wav.setframerate(16000)
                wav.writeframes(audio_bytes)
            wav_io.seek(0)

            headers = {
                "api-subscription-key": self._api_key
            }
            files = {
                "file": ("audio.wav", wav_io, "audio/wav")
            }
            data = {
                "model": self._model,
                "with_timestamps": "false",
            }
            # If language is 'auto' or empty, Sarvam might handle it or we use hi-IN
            lang_code = language or self._language
            if lang_code and lang_code != "auto":
                data["language_code"] = lang_code

            response = requests.post(URL, headers=headers, files=files, data=data, timeout=15)
            
            if response.status_code != 200:
                logger.error("Sarvam AI Error %d: %s", response.status_code, response.text)
                return TranscriptionResult(
                    text="", engine_name=self.name, 
                    error=f"Sarvam API Error {response.status_code}: {response.text}"
                )

            # Typical Sarvam response: {"transcript": "..."}
            # Note: actual field name might be 'transcript' or 'text' depending on version
            # Analysis should have confirmed this.
            resp_json = response.json()
            text = resp_json.get("transcript", "") or resp_json.get("text", "")
            
            elapsed_ms = (time.monotonic() - t0) * 1000

            result = TranscriptionResult(
                text=text.strip(),
                engine_name=self.name,
                duration_ms=elapsed_ms,
            )
            self._log_result(result)
            return result

        except Exception as exc:
            logger.exception("Sarvam AI transcription error")
            return TranscriptionResult(
                text="", engine_name=self.name, error=str(exc)
            )
        finally:
            self._status = EngineStatus.READY
