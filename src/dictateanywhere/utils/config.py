"""
Configuration management.

Settings are persisted to %APPDATA%\\DictateAnywhere\\config.json.
No secrets are stored here — API keys go through secure_storage.py.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

APP_NAME = "DictateAnywhere"
CONFIG_VERSION = 2


def app_data_dir() -> Path:
    """Return (and create) the per-user app data directory."""
    base = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


# Keep for backward compat — alias
_app_data_dir = app_data_dir


def _default_config_path() -> Path:
    return app_data_dir() / "config.json"


def _default_log_path() -> Path:
    return app_data_dir() / "dictateanywhere.log"


@dataclass
class Config:
    # ── Version ──────────────────────────────────────────────────────────────
    version: int = CONFIG_VERSION  # bump when adding migrations

    # ── Engine ───────────────────────────────────────────────────────────────
    engine_mode: str = "hybrid"          # "local" | "cloud" | "hybrid"
    model_size: str = "small"            # tiny | base | small | medium | large
    language: str = "en"                 # BCP-47 language code
    compute_type: str = "int8"           # int8 | float16 | float32 (CPU efficiency)
    local_device: str = "cuda"           # cpu | cuda | auto
    cloud_region: str = "eastus"         # Azure region
    sarvam_model: str = "saarika:v2.5"   # Sarvam model (saarika:v2.5 | saaras:v3)
    sarvam_language: str = "hi-IN"       # Default Indian language for Sarvam
    enable_sarvam_websocket: bool = True # Use WebSocket for real-time transcription


    # ── Audio ─────────────────────────────────────────────────────────────────
    mic_device_index: int = -1           # -1 = system default
    sample_rate: int = 16000            # Hz — Whisper expects 16 kHz
    vad_aggressiveness: int = 1          # 0–3; default changed 2→1 in v1.1
    silence_timeout_ms: int = 2500       # ms of silence before stopping capture
    max_record_seconds: int = 30         # hard cap per utterance
    enable_max_record_limit: bool = True  # whether to enforce the cap


    # ── Hotkey ───────────────────────────────────────────────────────────────
    hotkey: str = "ctrl+alt+d"           # configurable key combo
    hotkey_mode: str = "toggle"          # "toggle" | "push_to_talk"

    # ── Text injection ────────────────────────────────────────────────────────
    inject_method: str = "clipboard"     # "clipboard" | "sendinput"
    inject_delay_ms: int = 50           # small delay for stability

    # ── Punctuation ───────────────────────────────────────────────────────────
    spoken_punctuation: bool = True      # "period" → "."
    auto_capitalise: bool = True         # capitalise after sentence end

    # ── Floating widget ───────────────────────────────────────────────────────
    show_floating_widget: bool = True
    widget_x: int = 100
    widget_y: int = 100
    widget_size: int = 64               # px (width = height)
    widget_opacity: float = 0.85        # 0.1 – 1.0
    widget_always_on_top: bool = True

    # ── System ────────────────────────────────────────────────────────────────
    start_with_windows: bool = False
    log_level: str = "INFO"
    check_updates: bool = True

    # ── Cloud fallback ────────────────────────────────────────────────────────
    cloud_fallback_on_error: bool = True  # fall back to cloud if local fails
    cloud_fallback_provider: str = "azure" # azure | gemini | sarvam
    local_fallback_on_cloud_error: bool = True

    # ── UI theme ──────────────────────────────────────────────────────────────
    theme: str = "system"               # "system" | "light" | "dark"

    # ── Transcription preview overlay ─────────────────────────────────────────
    show_preview_window: bool = True     # show floating preview after dictation
    preview_hide_after_ms: int = 8000   # ms before overlay auto-hides (0 = never)
    preview_opacity: float = 0.85       # 0.1 – 1.0
    preview_text_color: str = "#ffffff" # hex color for newest text

    # ── Update checker ────────────────────────────────────────────────────────
    last_update_check: str = ""          # ISO date (YYYY-MM-DD) of last check
    skipped_update_version: str = ""    # release tag the user chose to skip

    # ── Cloud STT Settings ────────────────────────────────────────────────────
    sarvam_model: str = "saarika:v2.5"
    sarvam_language: str = "hi-IN"
    enable_sarvam_websocket: bool = True
    
    gemini_stt_model: str = "gemini-flash-lite-latest"
    gemini_stt_language: str = "en"

    # ── Text Polish ───────────────────────────────────────────────────────────
    enable_polish: bool = False
    polish_provider: str = "ollama"
    polish_action: str = "Fix Grammar & Spelling"
    custom_polish_prompt: str = "Rewrite this text to be more concise."
    ollama_url: str = "http://localhost:11434"
    polish_ollama_model: str = "llama3"
    polish_gemini_model: str = "gemini-flash-lite-latest"

    # ── Real-time Transcription ───────────────────────────────────────────────
    enable_realtime: bool = False
    realtime_frequency_ms: int = 800

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


class ConfigManager:
    """Load, save, and validate application configuration."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _default_config_path()
        self._config: Config = Config()
        self.load()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def config(self) -> Config:
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self._config, key, default)

    def set(self, key: str, value: Any) -> None:
        if not hasattr(self._config, key):
            raise KeyError(f"Unknown config key: {key!r}")
        setattr(self._config, key, value)

    def update(self, data: dict[str, Any]) -> None:
        for k, v in data.items():
            self.set(k, v)

    def save(self) -> None:
        try:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._config.to_dict(), indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._path)
            logger.debug("Config saved to %s", self._path)
        except OSError as exc:
            logger.error("Failed to save config: %s", exc)

    def load(self) -> None:
        if not self._path.exists():
            logger.info("No config found — using defaults")
            self.save()
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._config = Config.from_dict(data)
            logger.info("Config loaded from %s", self._path)
            self._migrate()
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            logger.warning("Config corrupt (%s) — resetting to defaults", exc)
            self._config = Config()
            self.save()

    def _migrate(self) -> None:
        """
        One-time upgrades guarded by config version.
        Only runs when config.version < CONFIG_VERSION.
        """
        changed = False

        # v1.0 → v1.1: silence timeout increased 1500 → 2500 ms
        if self._config.version < 2 and self._config.silence_timeout_ms == 1500:
            self._config.silence_timeout_ms = 2500
            logger.info("Config migrated: silence_timeout_ms 1500 → 2500")
            changed = True

        # v1.0 → v1.1: VAD aggressiveness reduced 2 → 1
        if self._config.version < 2 and self._config.vad_aggressiveness == 2:
            self._config.vad_aggressiveness = 1
            logger.info("Config migrated: vad_aggressiveness 2 → 1")
            changed = True

        # Stamp current version
        if self._config.version < CONFIG_VERSION:
            self._config.version = CONFIG_VERSION
            changed = True

        if changed:
            self.save()

    def reset(self) -> None:
        self._config = Config()
        self.save()

    # ── Convenience helpers ───────────────────────────────────────────────────

    def config_dir(self) -> Path:
        return self._path.parent

    def log_path(self) -> Path:
        return _default_log_path()
