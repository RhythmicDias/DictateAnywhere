"""
Sarvam AI STT engine.
Excellent for Indian languages.
"""

from __future__ import annotations

import io
import logging
import time
import wave
import json
import threading
import base64
from typing import Optional, Callable

import requests
import websocket

from .engine import EngineStatus, STTEngine, TranscriptionResult

logger = logging.getLogger(__name__)

URL = "https://api.sarvam.ai/speech-to-text"
WS_URL = "wss://api.sarvam.ai/speech-to-text/ws"


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
        
        self._ws: Optional[websocket.WebSocketApp] = None
        self._on_text: Optional[Callable[[str], None]] = None
        self._streaming = False

    def update_credentials(self, api_key: str) -> None:
        self._api_key = api_key

    def load(self) -> bool:
        """Sarvam is a cloud API, no local loading needed."""
        self._status = EngineStatus.READY
        return True

    def is_available(self) -> bool:
        return bool(self._api_key)

    def test_connection(self) -> tuple[bool, str]:
        """Verify the API key by sending a tiny silence chunk."""
        if not self._api_key:
            return False, "API key missing."
        try:
            # We use the transcribe method with a 1-second silence chunk
            import io
            import wave
            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"\x00" * 32000) # 1 second silence
            wav_io.seek(0)
            
            headers = {"api-subscription-key": self._api_key}
            files = {"file": ("test.wav", wav_io, "audio/wav")}
            data = {"model": self._model}
            
            resp = requests.post(URL, headers=headers, files=files, data=data, timeout=10)
            if resp.status_code == 200:
                return True, "Sarvam connected successfully."
            else:
                return False, f"Sarvam error {resp.status_code}: {resp.text}"
        except Exception as e:
            return False, str(e)

    def start_stream(self, on_text: Callable[[str], None], language: str = "en") -> None:
        if not self._api_key:
            logger.warning("Cannot start Sarvam stream: API key missing")
            return
            
        self._on_text = on_text
        self._streaming = True
        
        # Map short codes (en, hi, etc.) to Sarvam's required -IN format
        mapping = {
            "en": "en-IN", "hi": "hi-IN", "bn": "bn-IN", "gu": "gu-IN",
            "kn": "kn-IN", "ml": "ml-IN", "mr": "mr-IN", "pa": "pa-IN",
            "ta": "ta-IN", "te": "te-IN",
        }
        lang_code = language if (language and language != "auto") else self._language
        lang_code = mapping.get(lang_code, lang_code)
        
        ws_url = f"{WS_URL}?language-code={lang_code}&model={self._model}"
        headers = {"api-subscription-key": self._api_key}
        
        logger.info("Opening Sarvam WebSocket: %s", ws_url)
        
        self._ws = websocket.WebSocketApp(
            ws_url,
            header=headers,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close,
        )
        # Start the listener loop in a background thread
        threading.Thread(target=self._ws.run_forever, daemon=True).start()

    def _on_ws_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get("type") == "data":
                payload = data.get("data", {})
                text = payload.get("transcript", "")
                if text and self._on_text:
                    self._on_text(text)
        except Exception as e:
            logger.debug("Sarvam WS message parse error: %s", e)

    def _on_ws_error(self, ws, error):
        logger.error("Sarvam WebSocket Error: %s", error)

    def _on_ws_close(self, ws, close_status_code, close_msg):
        logger.info("Sarvam WebSocket closed: %s (%s)", close_msg, close_status_code)
        self._ws = None

    def send_chunk(self, audio_bytes: bytes) -> None:
        if not self._streaming or not self._ws:
            return
            
        try:
            # We must be careful not to send too fast or when socket is connecting
            if self._ws.sock and self._ws.sock.connected:
                # Wrap audio in the format Sarvam expects
                payload = {
                    "audio": {
                        "data": base64.b64encode(audio_bytes).decode("utf-8"),
                        "sample_rate": 16000,
                        "encoding": "pcm_s16le"
                    }
                }
                self._ws.send(json.dumps(payload))
        except Exception as e:
            logger.debug("Sarvam WS send error: %s", e)

    def stop_stream(self) -> None:
        self._streaming = False
        if self._ws:
            self._ws.close()
            self._ws = None
            
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
            # Map short codes (en, hi, etc.) to Sarvam's required -IN format
            mapping = {
                "en": "en-IN",
                "hi": "hi-IN",
                "bn": "bn-IN",
                "gu": "gu-IN",
                "kn": "kn-IN",
                "ml": "ml-IN",
                "mr": "mr-IN",
                "pa": "pa-IN",
                "ta": "ta-IN",
                "te": "te-IN",
            }
            
            # If language is 'auto' or empty, use the engine's default language
            lang_code = language if (language and language != "auto") else self._language
            
            # Apply mapping if it's a known short code
            lang_code = mapping.get(lang_code, lang_code)
            
            if lang_code and lang_code != "auto":
                data["language_code"] = lang_code

            logger.info("Sending request to Sarvam AI (model: %s, lang: %s)", self._model, lang_code)
            response = requests.post(URL, headers=headers, files=files, data=data, timeout=15)
            
            if response.status_code != 200:
                logger.error("Sarvam AI Error %d: %s", response.status_code, response.text)
                return TranscriptionResult(
                    text="", engine_name=self.name, 
                    error=f"Sarvam API Error {response.status_code}: {response.text}"
                )

            resp_json = response.json()
            logger.debug("Sarvam AI raw response: %s", resp_json)
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
