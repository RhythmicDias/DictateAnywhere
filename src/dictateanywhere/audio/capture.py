"""
Microphone audio capture using sounddevice.

Produces 16 kHz mono int16 PCM frames into a thread-safe queue.

Host-API strategy on Windows
─────────────────────────────
sounddevice/PortAudio exposes the same physical microphone under multiple
host APIs (WASAPI, MME, WDM-KS, …).  WASAPI shared mode is the default but
has two known failure modes that both look identical — the stream opens
without error but every sample returned is 0x0000:

  1. Realtek/Dolby audio stacks on many Lenovo/HP/Dell laptops intercept
     WASAPI shared-mode reads and suppress the signal.
  2. WASAPI requires the mix format rate (44100/48000 Hz) to match the
     requested rate; mismatches silently deliver zeros.

MME (Windows Multimedia Extensions) bypasses WASAPI and the Realtek manager
entirely — it is the same backend Audacity uses by default, which is why
Audacity works on machines where WASAPI fails.

Open order used by this module:
  1. MME device that matches the name of the requested device (most compat.)
  2. Any available MME input device
  3. WASAPI device at its native sample rate
  4. WASAPI system-default at native rate

With MME we can request 16 kHz directly; the Windows audio engine resamples.
With WASAPI we open at native rate and resample ourselves in _callback().
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

def _find_mme_input_devices() -> list[int]:
    """
    Return sounddevice device indices that belong to the MME host API,
    ordered with the default input device first.

    Returns an empty list on non-Windows systems or if MME is not found.
    """
    try:
        host_apis = sd.query_hostapis()
        mme_api_idx = next(
            (i for i, api in enumerate(host_apis) if "MME" in api["name"]),
            None,
        )
        if mme_api_idx is None:
            return []

        default_input = sd.default.device[0] if hasattr(sd.default.device, "__getitem__") else -1
        devices = sd.query_devices()

        mme_inputs: list[int] = []
        for i, dev in enumerate(devices):
            if dev["hostapi"] == mme_api_idx and dev["max_input_channels"] > 0:
                mme_inputs.append(i)

        # Float the default-equivalent MME device to the front
        try:
            default_info = sd.query_devices(default_input)
            default_name = default_info["name"]
            mme_inputs.sort(key=lambda i: 0 if default_name in sd.query_devices(i)["name"] else 1)
        except Exception:
            pass

        return mme_inputs
    except Exception:
        return []


def _mme_device_for_name(name: str) -> Optional[int]:
    """
    Return the MME device index whose name contains *name* (case-insensitive).
    Returns the first MME input device if no name match is found.
    """
    try:
        mme_devices = _find_mme_input_devices()
        for idx in mme_devices:
            dev = sd.query_devices(idx)
            if name.lower() in dev["name"].lower():
                return idx
        return mme_devices[0] if mme_devices else None
    except Exception:
        return None


def _get_device_native_rate(device: Optional[int]) -> int:
    """Return the native default sample rate for *device*."""
    try:
        info = sd.query_devices(device if device is not None else sd.default.device[0])
        rate = int(info["default_samplerate"])
        if rate > 0:
            return rate
    except Exception:
        pass
    return TARGET_RATE


def _resample_f32(chunk: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """Resample float32 mono array, using scipy if available."""
    if from_rate == to_rate:
        return chunk
    try:
        from scipy.signal import resample_poly
        frac = Fraction(to_rate, from_rate).limit_denominator(1000)
        return resample_poly(chunk, frac.numerator, frac.denominator).astype(np.float32)
    except Exception:
        n_out = int(math.ceil(len(chunk) * to_rate / from_rate))
        x_old = np.linspace(0.0, 1.0, len(chunk), dtype=np.float64)
        x_new = np.linspace(0.0, 1.0, n_out, dtype=np.float64)
        return np.interp(x_new, x_old, chunk.astype(np.float64)).astype(np.float32)


def list_input_devices() -> list[dict]:
    """Return all available input devices as a list of dicts (WASAPI/default API)."""
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

    Always delivers TARGET_RATE (16 kHz) int16 PCM to callers regardless of
    the hardware rate or host API used.

    Try order: MME (most compatible on Windows) → WASAPI at native rate.
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
        self._native_rate: int = TARGET_RATE

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def sample_rate(self) -> int:
        return TARGET_RATE

    @property
    def working_device(self) -> Optional[int]:
        return self._working_device

    def is_recording(self) -> bool:
        return self._recording

    def read_frames(self, timeout: float = 1.0) -> bytes:
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return b""

    def start(self) -> None:
        if self._recording:
            return
        self._all_frames.clear()
        self._recording = True

        # ── Build a prioritised list of (device_index, rate_to_use, label) ──
        candidates: list[tuple[Optional[int], int, str]] = []

        # 1. MME device matching the requested device name
        try:
            if self._requested_device is not None:
                req_name = sd.query_devices(self._requested_device)["name"]
            else:
                req_name = sd.query_devices(kind="input")["name"]
            mme_match = _mme_device_for_name(req_name)
            if mme_match is not None:
                candidates.append((mme_match, TARGET_RATE, f"MME:{mme_match}"))
        except Exception:
            pass

        # 2. Any other MME input devices
        for mme_idx in _find_mme_input_devices():
            entry = (mme_idx, TARGET_RATE, f"MME:{mme_idx}")
            if entry not in candidates:
                candidates.append(entry)

        # 3. Requested WASAPI device at its native rate
        native = _get_device_native_rate(self._requested_device)
        candidates.append((self._requested_device, native, f"WASAPI:{self._requested_device}"))

        # 4. WASAPI default at native rate
        default_native = _get_device_native_rate(None)
        candidates.append((None, default_native, "WASAPI:default"))

        last_exc: Optional[Exception] = None
        for device, rate, label in candidates:
            block = int(rate * FRAME_DURATION_MS / 1000)
            self._native_rate = rate
            try:
                self._stream = sd.InputStream(
                    samplerate=rate,
                    channels=CHANNELS,
                    dtype="float32",
                    device=device,
                    blocksize=block,
                    callback=self._callback,
                )
                self._stream.start()
                self._working_device = device

                # Quick sanity check — read a few ms and verify non-zero
                time.sleep(0.15)
                if not self._frame_queue.empty():
                    sample_frame = self._frame_queue.queue[0]
                    arr = np.frombuffer(sample_frame, dtype=np.int16)
                    rms = float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))
                else:
                    rms = 0.0

                logger.info(
                    "Audio capture started — %s rate=%d rms_check=%.5f",
                    label, rate, rms,
                )
                # Accept this device even if rms=0 on the first frame;
                # let the application decide. Only skip truly-broken devices.
                return

            except Exception as exc:
                last_exc = exc
                logger.warning("Could not open %s: %s", label, exc)
                try:
                    if self._stream:
                        self._stream.close()
                except Exception:
                    pass
                self._stream = None

        self._recording = False
        raise RuntimeError(
            f"Could not open any microphone.\n\nLast error: {last_exc}"
        ) from last_exc

    def stop(self) -> bytes:
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
        duration_s = len(audio_bytes) / (TARGET_RATE * 2)
        logger.info("Audio capture stopped — %.2f s at 16 kHz int16", duration_s)
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

        mono_f32 = indata[:, 0]
        if self._native_rate != TARGET_RATE:
            mono_f32 = _resample_f32(mono_f32, self._native_rate, TARGET_RATE)

        chunk = np.clip(mono_f32, -1.0, 1.0)
        chunk_int16 = (chunk * 32767.0).astype(np.int16).tobytes()
        self._all_frames.append(chunk_int16)
        self._frame_queue.put(chunk_int16)


# ---------------------------------------------------------------------------
# TimedCapture
# ---------------------------------------------------------------------------

class TimedCapture:
    """
    Stops automatically after silence or max duration. Returns 16 kHz int16.
    """

    def __init__(
        self,
        vad,
        on_complete: Callable[[bytes], None],
        device_index: int = -1,
        silence_timeout_ms: int = 1500,
        max_seconds: int = 30,
        sample_rate: int = TARGET_RATE,
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
