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
CONFIG_VERSION = 1


def _app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_PATH = _app_data_dir() / "config.json"
LOG_PATH = _app_data_dir() / "dictateanywhere.log"


@dataclass
class Config:
    # ── Version ──────────────────────────────────────────────────────────────
    version: int = CONFIG_VERSION

    # ── Engine ───────────────────────────────────────────────────────────────
    engine_mode: str = "hybrid"          # "local" | "cloud" | "hybrid"
    model_size: str = "small"            # tiny | base | small | medium | large
    language: str = "en"                 # BCP-47 language code
    compute_type: str = "int8"           # int8 | float16 | float32 (CPU efficiency)
    cloud_region: str = "eastus"         # Azure region

    # ── Audio ─────────────────────────────────────────────────────────────────
    mic_device_index: int = -1           # -1 = system default
    sample_rate: int = 16000            # Hz — Whisper expects 16 kHz
    vad_aggressiveness: int = 1          # 0–3 (0=permissive, 3=aggressive)
    silence_timeout_ms: int = 2500       # ms of silence before stopping capture
    max_record_seconds: int = 30         # hard cap per utterance

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
    local_fallback_on_cloud_error: bool = True

    # ── UI theme ──────────────────────────────────────────────────────────────
    theme: str = "system"               # "system" | "light" | "dark"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


class ConfigManager:
    """Load, save, and validate application configuration."""

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self._path = path
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
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            logger.warning("Config corrupt (%s) — resetting to defaults", exc)
            self._config = Config()
            self.save()

    def reset(self) -> None:
        self._config = Config()
        self.save()

    # ── Convenience helpers ───────────────────────────────────────────────────

    def config_dir(self) -> Path:
        return self._path.parent

    def log_path(self) -> Path:
        return LOG_PATH
