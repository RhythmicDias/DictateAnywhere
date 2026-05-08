"""
Google Gemini STT engine.
Uses Gemini 2.0 / 2.5 Flash Lite to transcribe audio files.
"""

from __future__ import annotations

import base64
import logging
import time
import json
from typing import Optional

import requests

from .engine import EngineStatus, STTEngine, TranscriptionResult

logger = logging.getLogger(__name__)

# https://ai.google.dev/gemini-api/docs/multimodal?lang=python#audio
URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

class GeminiEngine(STTEngine):
    """
    STT engine powered by Google Gemini.
    """

    name = "cloud (Google Gemini)"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-flash-lite-latest",
        language: str = "en",
    ) -> None:
        super().__init__()
        self._api_key = api_key
        self._model = model
        self._language = language

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
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self._api_key}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return True, "Gemini connected successfully."
            else:
                err = resp.json().get("error", {}).get("message", "Unknown error")
                return False, f"Gemini error {resp.status_code}: {err}"
        except Exception as e:
            return False, str(e)

    def transcribe(self, audio_bytes: bytes, language: str = "auto") -> TranscriptionResult:
        if not self._api_key:
            return TranscriptionResult(
                text="", engine_name=self.name, error="Gemini API key missing"
            )

        # Use the provided language if it's not "auto", otherwise use the engine's default
        lang_to_use = language if (language and language != "auto") else self._language

        try:
            self._status = EngineStatus.BUSY
            t0 = time.monotonic()

            # Wrap raw PCM in a WAV container
            import io
            import wave
            with io.BytesIO() as wav_io:
                with wave.open(wav_io, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2) # 16-bit
                    wav_file.setframerate(16000)
                    wav_file.writeframes(audio_bytes)
                audio_wav_bytes = wav_io.getvalue()

            # Encode audio to base64
            audio_b64 = base64.b64encode(audio_wav_bytes).decode("utf-8")

            url = URL_TEMPLATE.format(model=self._model, key=self._api_key)
            
            # Simple prompt for transcription
            prompt = "Transcribe the following audio accurately. Output only the transcript text."
            if lang_to_use and lang_to_use != "auto":
                prompt += f" The language is {lang_to_use}."

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "audio/wav",
                                    "data": audio_b64
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.0,
                }
            }

            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code != 200:
                msg = "Unknown Error"
                try:
                    err_data = response.json().get("error", {})
                    msg = err_data.get("message", response.text)
                except:
                    msg = response.text
                
                # Sanitize the key if it appears in any raw response text
                if self._api_key:
                    msg = msg.replace(self._api_key, "***")
                
                logger.error("Gemini STT Error %d: %s", response.status_code, msg)
                return TranscriptionResult(
                    text="", engine_name=self.name, 
                    error=msg
                )

            resp_json = response.json()
            
            # Extract text from Gemini response
            # Response format: { "candidates": [ { "content": { "parts": [ { "text": "..." } ] } } ] }
            text = ""
            try:
                candidates = resp_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text = parts[0].get("text", "")
            except (KeyError, IndexError) as e:
                logger.error("Failed to parse Gemini response: %s", e)
                return TranscriptionResult(text="", engine_name=self.name, error="Parse error")

            elapsed_ms = (time.monotonic() - t0) * 1000

            result = TranscriptionResult(
                text=text.strip(),
                engine_name=self.name,
                duration_ms=elapsed_ms,
            )
            self._log_result(result)
            return result

        except Exception as exc:
            msg = str(exc)
            if self._api_key:
                msg = msg.replace(self._api_key, "***")
            logger.error("Gemini STT transcription error: %s", msg)
            return TranscriptionResult(
                text="", engine_name=self.name, error=msg
            )
        finally:
            self._status = EngineStatus.READY
