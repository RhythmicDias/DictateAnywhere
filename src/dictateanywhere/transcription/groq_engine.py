"""
Groq Cloud STT engine using OpenAI-compatible Whisper API.
Ultra-fast speech-to-text inference.
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

URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class GroqEngine(STTEngine):
    """
    STT engine powered by Groq Cloud Whisper API.
    Requires an API key from https://console.groq.com/
    """

    name = "cloud (Groq Cloud)"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "whisper-large-v3-turbo",
        language: str = "en",
    ) -> None:
        super().__init__()
        self._api_key = api_key
        self._model = model or "whisper-large-v3-turbo"
        self._language = language
        self._session = requests.Session()

    def update_credentials(self, api_key: str) -> None:
        self._api_key = api_key

    def load(self) -> bool:
        self._status = EngineStatus.READY
        return True

    def is_available(self) -> bool:
        return bool(self._api_key)

    def test_connection(self) -> tuple[bool, str]:
        """Verify the API key by listing models."""
        if not self._api_key:
            return False, "API key missing."
        try:
            resp = self._session.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return True, "Groq connected successfully."
            err = resp.json().get("error", {}).get("message", "Unknown error")
            return False, f"Groq error {resp.status_code}: {err}"
        except Exception as e:
            return False, str(e)

    def transcribe(self, audio_bytes: bytes, language: str = "auto") -> TranscriptionResult:
        if not self._api_key:
            return TranscriptionResult(
                text="", engine_name=self.name, error="Groq API key missing"
            )

        lang_to_use = language if (language and language != "auto") else self._language

        try:
            self._status = EngineStatus.BUSY
            t0 = time.monotonic()

            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(audio_bytes)
            wav_io.seek(0)

            headers = {
                "Authorization": f"Bearer {self._api_key}",
            }
            files = {
                "file": ("audio.wav", wav_io, "audio/wav"),
            }
            data: dict[str, str] = {
                "model": self._model or "whisper-large-v3-turbo",
                "response_format": "json",
            }
            if lang_to_use and lang_to_use != "auto":
                clean_lang = lang_to_use.split("-")[0].lower()
                data["language"] = clean_lang

            resp = self._session.post(URL, headers=headers, files=files, data=data, timeout=30)
            elapsed = time.monotonic() - t0

            if resp.status_code != 200:
                err_msg = f"Groq HTTP {resp.status_code}: {resp.text}"
                logger.error(err_msg)
                return TranscriptionResult(
                    text="", engine_name=self.name, duration_s=elapsed, error=err_msg
                )

            res_json = resp.json()
            text = res_json.get("text", "").strip()
            return TranscriptionResult(
                text=text, engine_name=self.name, duration_s=elapsed, confidence=1.0
            )
        except Exception as exc:
            logger.exception("Groq transcription error")
            return TranscriptionResult(text="", engine_name=self.name, error=str(exc))
        finally:
            self._status = EngineStatus.READY
