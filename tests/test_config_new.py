# tests/test_config_new.py
import tempfile
from pathlib import Path
from unittest.mock import patch

from voiceflow.config import load_config, DEFAULT_CONFIG, _deep_merge


def test_default_config_when_no_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("voiceflow.config.VF_HOME", Path(tmpdir)):
            config = load_config()
            assert config["daemon"]["port"] == 9800
            assert config["tts"]["engine"] == "sapi"


def test_user_config_overrides_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        config_file = tmppath / "config.yaml"
        config_file.write_text("tts:\n  engine: kokoro\n  voice: ef_dora\n")
        with patch("voiceflow.config.VF_HOME", tmppath):
            config = load_config()
            assert config["tts"]["engine"] == "kokoro"
            assert config["tts"]["voice"] == "ef_dora"
            assert config["daemon"]["port"] == 9800  # default preserved


def test_deep_merge():
    base = {"a": {"b": 1, "c": 2}, "d": 3}
    override = {"a": {"b": 99}, "e": 4}
    result = _deep_merge(base, override)
    assert result == {"a": {"b": 99, "c": 2}, "d": 3, "e": 4}
