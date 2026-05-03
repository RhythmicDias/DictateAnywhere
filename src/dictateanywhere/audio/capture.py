"""
Microphone audio capture using sounddevice.

Produces 16 kHz mono int16 PCM frames into a thread-safe queue.

On Windows, WASAPI shared mode requires the stream to be opened at the
device's native sample rate (typically 44 100 or 48 000 Hz).  Requesting
16 000 Hz on a device whose mix-format is different causes WASAPI to return
silent (zero) audio without raising any error.

This module always opens the stream at the device's native rate and
resamples each captured block to TARGET_RATE (16 000 Hz) in the callback,
so all downstream code (VAD, Whisper) continues to receive standard 16 kHz
int16 PCM without any changes.
"""

from __future__ import annotations

import logging
import math
import queue
import threading
import time
from fractions import Fraction
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

TARGET_RATE = 16_000          # Hz — Whisper / VAD requirement
CHANNELS = 1                  # mono
FRAME_DURATION_MS = 30        # VAD frame size (10 | 20 | 30 ms)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_device_native_rate(device: Optional[int]) -> int:
    """
    Return the native default sample rate for *device*.

    Falls back to TARGET_RATE if the query fails.
    """
    try:
        info = sd.query_devices(device if device is not None else sd.default.device[0])
        rate = int(info["default_samplerate"])
        if rate > 0:
            return rate
    except Exception:
        pass
    return TARGET_RATE


def _resample_f32(chunk: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """
    Resample a float32 mono array from *from_rate* to *to_rate*.

    Uses scipy.signal.resample_poly when available (highest quality);
    falls back to numpy linear interpolation.
    """
    if from_rate == to_rate:
        return chunk
    try:
        from scipy.signal import resample_poly
        frac = Fraction(to_rate, from_rate).limit_denominator(1000)
        return resample_poly(chunk, frac.numerator, frac.denominator).astype(np.float32)
    except Exception:
        # Simple linear interpolation fallback (no extra deps)
        n_out = int(math.ceil(len(chunk) * to_rate / from_rate))
        x_old = np.linspace(0.0, 1.0, len(chunk), dtype=np.float64)
        x_new = np.linspace(0.0, 1.0, n_out, dtype=np.float64)
        return np.interp(x_new, x_old, chunk.astype(np.float64)).astype(np.float32)


def list_input_devices() -> list[dict]:
    """Return all available input devices as a list of dicts."""
    devices = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devices.append({
                "index": i,
                "name": dev["name"],
                "channels": dev["max_input_channels"],
                "default_samplerate": dev["default_samplerate"],
            })
    return devices


# ---------------------------------------------------------------------------
# AudioCapture
# ---------------------------------------------------------------------------

class AudioCapture:
    """
    Stream audio from the microphone into an internal queue.

    The stream opens at the device's native sample rate and resamples
    every block to TARGET_RATE (16 000 Hz) before queuing, so callers
    always receive 16 kHz int16 PCM regardless of the hardware rate.

    Usage:
        capture = AudioCapture(device_index=-1)
        capture.start()
        while recording:
            frames = capture.read_frames(timeout=1.0)
        audio_bytes = capture.stop()  # complete recording at 16 kHz
    """

    def __init__(
        self,
        device_index: int = -1,
        sample_rate: int = TARGET_RATE,   # kept for API compat; ignored internally
        on_speech_start: Optional[Callable] = None,
        on_speech_end: Optional[Callable] = None,
    ) -> None:
        self._requested_device = None if device_index < 0 else device_index
        self._on_speech_start = on_speech_start
        self._on_speech_end = on_speech_end

        self._frame_queue: queue.Queue[bytes] = queue.Queue()
        self._all_frames: list[bytes] = []
        self._stream: Optional[sd.InputStream] = None
        self._recording = False
        self._working_device: Optional[int] = self._requested_device

        # Populated by start():
        self._native_rate: int = TARGET_RATE

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def sample_rate(self) -> int:
        """Rate of the PCM data returned by stop() / read_frames()."""
        return TARGET_RATE

    @property
    def working_device(self) -> Optional[int]:
        """The device index that successfully opened (None = system default)."""
        return self._working_device

    def is_recording(self) -> bool:
        return self._recording

    def read_frames(self, timeout: float = 1.0) -> bytes:
        """Blocking read of the next 16 kHz int16 frame."""
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return b""

    def start(self) -> None:
        """Open the microphone and start buffering audio."""
        if self._recording:
            return
        self._all_frames.clear()
        self._recording = True

        # Build try list: configured device first, then system default.
        devices_to_try: list[Optional[int]] = [self._requested_device]
        if self._requested_device is not None:
            devices_to_try.append(None)

        last_exc: Optional[Exception] = None
        for device in devices_to_try:
            try:
                native_rate = _get_device_native_rate(device)
                # Block size = 30 ms at native rate (matches VAD frame at 16 kHz
                # after resampling, since 30 ms is rate-independent).
                native_block = int(native_rate * FRAME_DURATION_MS / 1000)

                self._native_rate = native_rate
                self._stream = sd.InputStream(
                    samplerate=native_rate,
                    channels=CHANNELS,
                    dtype="float32",       # float32 is universal across WASAPI modes
                    device=device,
                    blocksize=native_block,
                    callback=self._callback,
                )
                self._stream.start()
                self._working_device = device
                logger.info(
                    "Audio capture started — device=%s native_sr=%d target_sr=%d",
                    device if device is not None else "default",
                    native_rate,
                    TARGET_RATE,
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
            f"Could not open any microphone.\n\nLast error: {last_exc}\n\n"
            "Check that a microphone is connected and Windows audio is working.\n"
            "If mics appear in the list but give no signal, open:\n"
            "  Settings → Privacy & Security → Microphone\n"
            "  → Let desktop apps access your microphone  (must be ON)"
        ) from last_exc

    def stop(self) -> bytes:
        """Stop capture and return the complete recording as 16 kHz int16 bytes."""
        if not self._recording:
            return b""
        self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        while not self._frame_queue.empty():
            try:
                self._all_frames.append(self._frame_queue.get_nowait())
            except queue.Empty:
                break

        audio_bytes = b"".join(self._all_frames)
        duration_s = len(audio_bytes) / (TARGET_RATE * 2)   # int16 = 2 bytes/sample
        logger.info("Audio capture stopped — %.2f s recorded (16 kHz int16)", duration_s)
        return audio_bytes

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

        mono_f32 = indata[:, 0]   # (frames,) float32 at native_rate

        # Resample to TARGET_RATE if needed
        if self._native_rate != TARGET_RATE:
            mono_f32 = _resample_f32(mono_f32, self._native_rate, TARGET_RATE)

        # Convert to int16 PCM
        chunk = np.clip(mono_f32, -1.0, 1.0)
        chunk_int16 = (chunk * 32767.0).astype(np.int16).tobytes()

        self._all_frames.append(chunk_int16)
        self._frame_queue.put(chunk_int16)


# ---------------------------------------------------------------------------
# TimedCapture
# ---------------------------------------------------------------------------

class TimedCapture:
    """
    Higher-level recorder that stops automatically after a silence timeout
    or a maximum duration, using VAD internally.

    Returns the complete audio as bytes via the *on_complete* callback.
    Audio is always 16 kHz int16 PCM regardless of hardware.
    """

    def __init__(
        self,
        vad,
        on_complete: Callable[[bytes], None],
        device_index: int = -1,
        silence_timeout_ms: int = 1500,
        max_seconds: int = 30,
        sample_rate: int = TARGET_RATE,   # kept for API compat
    ) -> None:
        self._vad = vad
        self._on_complete = on_complete
        self._device_index = device_index
        self._silence_timeout = silence_timeout_ms / 1000.0
        self._max_seconds = max_seconds

        self._capture: Optional[AudioCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._capture = AudioCapture(device_index=self._device_index)
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

    @property
    def working_device(self) -> Optional[int]:
        if self._capture is not None:
            return self._capture.working_device
        return None
