"""Tests for ConfigManager."""

import json
import tempfile
from pathlib import Path

import pytest
from dictateanywhere.utils.config import Config, ConfigManager


@pytest.fixture
def tmp_config(tmp_path):
    """Return a ConfigManager backed by a temp file."""
    config_file = tmp_path / "config.json"
    return ConfigManager(path=config_file)


class TestConfig:
    def test_defaults(self):
        c = Config()
        assert c.engine_mode == "hybrid"
        assert c.model_size == "small"
        assert c.hotkey == "ctrl+alt+d"
        assert c.language == "en"
        assert c.vad_aggressiveness == 1

    def test_to_dict_round_trip(self):
        c = Config()
        d = c.to_dict()
        c2 = Config.from_dict(d)
        assert c == c2

    def test_from_dict_ignores_unknown_keys(self):
        d = Config().to_dict()
        d["nonexistent_key"] = "ignored"
        c = Config.from_dict(d)
        assert not hasattr(c, "nonexistent_key")


class TestConfigManager:
    def test_load_defaults_when_no_file(self, tmp_config):
        assert tmp_config.get("engine_mode") == "hybrid"

    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "config.json"
        mgr = ConfigManager(path=path)
        mgr.set("engine_mode", "cloud")
        mgr.save()

        mgr2 = ConfigManager(path=path)
        assert mgr2.get("engine_mode") == "cloud"

    def test_set_known_key(self, tmp_config):
        tmp_config.set("model_size", "medium")
        assert tmp_config.get("model_size") == "medium"

    def test_set_unknown_key_raises(self, tmp_config):
        with pytest.raises(KeyError):
            tmp_config.set("totally_unknown", "value")

    def test_update_multiple(self, tmp_config):
        tmp_config.update({"engine_mode": "local", "language": "fr"})
        assert tmp_config.get("engine_mode") == "local"
        assert tmp_config.get("language") == "fr"

    def test_reset(self, tmp_config):
        tmp_config.set("engine_mode", "cloud")
        tmp_config.reset()
        assert tmp_config.get("engine_mode") == "hybrid"

    def test_corrupt_config_resets_to_defaults(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("{ this is not valid json }", encoding="utf-8")
        mgr = ConfigManager(path=path)
        assert mgr.get("engine_mode") == "hybrid"

    def test_config_file_created_on_init(self, tmp_path):
        path = tmp_path / "config.json"
        assert not path.exists()
        ConfigManager(path=path)
        assert path.exists()

    def test_saved_file_is_valid_json(self, tmp_path):
        path = tmp_path / "config.json"
        mgr = ConfigManager(path=path)
        mgr.set("engine_mode", "local")
        mgr.save()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["engine_mode"] == "local"
