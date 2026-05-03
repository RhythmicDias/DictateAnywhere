"""
Microphone audio capture using sounddevice.

Produces 16 kHz mono PCM frames into a thread-safe queue.
VAD filtering is applied per-chunk to minimise CPU usage.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000          # Hz — Whisper requirement
CHANNELS = 1                  # mono
DTYPE = "int16"               # 16-bit PCM
FRAME_DURATION_MS = 30        # VAD frame size (10 | 20 | 30 ms)
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # 480 samples


def list_input_devices() -> list[dict]:
    """Return all available input devices as a list of dicts."""
    devices = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devices.append({"index": i, "name": dev["name"],
                            "channels": dev["max_input_channels"],
                            "default_samplerate": dev["default_samplerate"]})
    return devices


class AudioCapture:
    """
    Stream audio from the microphone into an internal queue.

    Usage:
        capture = AudioCapture(device_index=-1)
        capture.start()
        while recording:
            frames = capture.read_frames(timeout=1.0)
        audio_bytes = capture.stop()  # returns complete recording as bytes
    """

    def __init__(
        self,
        device_index: int = -1,
        sample_rate: int = SAMPLE_RATE,
        on_speech_start: Optional[Callable] = None,
        on_speech_end: Optional[Callable] = None,
    ) -> None:
        self._device = None if device_index < 0 else device_index
        self._sample_rate = sample_rate
        self._on_speech_start = on_speech_start
        self._on_speech_end = on_speech_end

        self._frame_queue: queue.Queue[bytes] = queue.Queue()
        self._all_frames: list[bytes] = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()
        self._recording = False

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Open the microphone stream and start buffering audio."""
        if self._recording:
            return
        self._all_frames.clear()
        self._recording = True

        # Try the configured device first; fall back to system default on error.
        devices_to_try: list = [self._device]
        if self._device is not None:
            devices_to_try.append(None)   # None = PortAudio default

        last_exc: Optional[Exception] = None
        for device in devices_to_try:
            try:
                self._stream = sd.InputStream(
                    samplerate=self._sample_rate,
                    channels=CHANNELS,
                    dtype=DTYPE,
                    device=device,
                    blocksize=FRAME_SAMPLES,
                    callback=self._callback,
                )
                self._stream.start()
                logger.info(
                    "Audio capture started — device=%s sr=%d",
                    device if device is not None else "default",
                    self._sample_rate,
                )
                return
            except Exception as exc:
                last_exc = exc
                logger.warning("Could not open device %r: %s — trying next", device, exc)
                try:
                    if self._stream:
                        self._stream.close()
                except Exception:
                    pass
                self._stream = None

        self._recording = False
        raise RuntimeError(
            f"Could not open any microphone.\n\n"
            f"Last error: {last_exc}\n\n"
            "Check that a microphone is connected, Windows audio is working,\n"
            "and the app has microphone permission (Settings → Privacy → Microphone)."
        ) from last_exc

    def stop(self) -> bytes:
        """
        Stop capture and return all recorded PCM audio as raw bytes.
        """
        if not self._recording:
            return b""
        self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Drain any remaining frames
        while not self._frame_queue.empty():
            try:
                self._all_frames.append(self._frame_queue.get_nowait())
            except queue.Empty:
                break

        audio_bytes = b"".join(self._all_frames)
        logger.info(
            "Audio capture stopped — %.2f s recorded",
            len(audio_bytes) / (self._sample_rate * 2),  # 2 bytes per int16 sample
        )
        return audio_bytes

    def read_frames(self, timeout: float = 1.0) -> bytes:
        """
        Blocking read of the next audio frame. Returns empty bytes on timeout.
        """
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return b""

    def is_recording(self) -> bool:
        return self._recording

    # ── Internal ───────────────────────────────────────────────────────────────

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            logger.debug("sounddevice status: %s", status)
        if not self._recording:
            return
        chunk = indata[:, 0].tobytes()  # first channel, raw bytes
        self._all_frames.append(chunk)
        self._frame_queue.put(chunk)


class TimedCapture:
    """
    Higher-level recorder that stops automatically after a silence timeout
    or a maximum duration, using VAD internally.

    Returns the complete audio as bytes via the *on_complete* callback.
    """

    def __init__(
        self,
        vad,                                        # VADFilter instance
        on_complete: Callable[[bytes], None],
        device_index: int = -1,
        silence_timeout_ms: int = 1500,
        max_seconds: int = 30,
        sample_rate: int = SAMPLE_RATE,
    ) -> None:
        self._vad = vad
        self._on_complete = on_complete
        self._device_index = device_index
        self._silence_timeout = silence_timeout_ms / 1000.0
        self._max_seconds = max_seconds
        self._sample_rate = sample_rate

        self._capture: Optional[AudioCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._capture = AudioCapture(device_index=self._device_index,
                                     sample_rate=self._sample_rate)
        self._capture.start()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        last_speech_time = time.monotonic()
        start_time = time.monotonic()

        while not self._stop_event.is_set():
            elapsed = time.monotonic() - start_time
            if elapsed > self._max_seconds:
                logger.info("Max recording duration reached (%.0f s)", self._max_seconds)
                break

            frame = self._capture.read_frames(timeout=0.1)  # type: ignore[union-attr]
            if not frame:
                continue

            is_speech = self._vad.is_speech(frame)
            if is_speech:
                last_speech_time = time.monotonic()
            else:
                silence_duration = time.monotonic() - last_speech_time
                if silence_duration >= self._silence_timeout:
                    logger.debug("Silence timeout reached (%.2f s)", silence_duration)
                    break

        audio = self._capture.stop()  # type: ignore[union-attr]
        if audio:
            self._on_complete(audio)
