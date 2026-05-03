"""
Voice Activity Detection using WebRTC VAD.

Filters out silent audio frames so the transcription engine only processes
frames that contain actual speech — keeps CPU usage low.
"""

from __future__ import annotations

import logging
from typing import Optional

import webrtcvad

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
FRAME_DURATION_MS = 30        # Must be 10, 20, or 30 for webrtcvad
FRAME_BYTES = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000) * 2  # int16 = 2 bytes/sample


class VADFilter:
    """
    Wraps webrtcvad with a smoothing ring-buffer to avoid choppy
    start/stop behaviour on short breath noises.

    aggressiveness: 0 (least aggressive) – 3 (most aggressive filtering)
    """

    def __init__(
        self,
        aggressiveness: int = 2,
        sample_rate: int = SAMPLE_RATE,
        speech_pad_frames: int = 5,   # extra frames kept after speech ends
    ) -> None:
        if aggressiveness not in (0, 1, 2, 3):
            raise ValueError("VAD aggressiveness must be 0, 1, 2, or 3")
        self._vad = webrtcvad.Vad(aggressiveness)
        self._sample_rate = sample_rate
        self._pad = speech_pad_frames
        self._ring: list[bool] = []
        self._pad_countdown = 0

    def is_speech(self, frame: bytes) -> bool:
        """
        Return True if *frame* is likely speech, with trailing-pad smoothing.

        *frame* must be exactly FRAME_BYTES bytes of 16-bit PCM.
        Shorter frames are zero-padded; longer ones are truncated.
        """
        # Ensure correct frame length
        frame = _pad_frame(frame)
        try:
            detected = self._vad.is_speech(frame, self._sample_rate)
        except Exception as exc:
            logger.debug("VAD error: %s — assuming silence", exc)
            detected = False

        if detected:
            self._pad_countdown = self._pad
            return True

        if self._pad_countdown > 0:
            self._pad_countdown -= 1
            return True

        return False

    def reset(self) -> None:
        self._ring.clear()
        self._pad_countdown = 0


def _pad_frame(frame: bytes) -> bytes:
    """Ensure the frame is exactly FRAME_BYTES long."""
    if len(frame) == FRAME_BYTES:
        return frame
    if len(frame) < FRAME_BYTES:
        return frame + b"\x00" * (FRAME_BYTES - len(frame))
    return frame[:FRAME_BYTES]


def audio_to_frames(audio: bytes, frame_bytes: int = FRAME_BYTES) -> list[bytes]:
    """Split raw PCM *audio* into fixed-size frames for VAD processing."""
    frames = []
    for i in range(0, len(audio) - frame_bytes + 1, frame_bytes):
        frames.append(audio[i : i + frame_bytes])
    return frames


def strip_silence(
    audio: bytes,
    aggressiveness: int = 2,
    sample_rate: int = SAMPLE_RATE,
) -> bytes:
    """
    Remove leading/trailing silence from *audio* PCM bytes.

    Returns the trimmed audio (may be empty if fully silent).
    """
    vad = VADFilter(aggressiveness=aggressiveness, sample_rate=sample_rate)
    frames = audio_to_frames(audio)

    if not frames:
        return b""

    speech_frames: list[bytes] = []
    speech_started = False
    trailing_silence: list[bytes] = []

    for frame in frames:
        if vad.is_speech(frame):
            if not speech_started:
                speech_started = True
            speech_frames.extend(trailing_silence)
            trailing_silence.clear()
            speech_frames.append(frame)
        else:
            if speech_started:
                trailing_silence.append(frame)

    result = b"".join(speech_frames)
    logger.debug(
        "strip_silence: %.2f s → %.2f s (removed %.0f%%)",
        len(audio) / (sample_rate * 2),
        len(result) / (sample_rate * 2),
        100 * (1 - len(result) / max(len(audio), 1)),
    )
    return result
