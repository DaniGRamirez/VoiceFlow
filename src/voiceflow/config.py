"""Configuration management for VoiceFlow global CLI."""
import os
from pathlib import Path
from typing import Any

import yaml

VF_HOME = Path(os.environ.get("VF_HOME", Path.home() / ".voiceflow"))
DEFAULT_CONFIG = {
    "daemon": {"port": 9800, "host": "localhost"},
    "tts": {
        "engine": "sapi",
        "voice": None,
        "lang": "es",
        "max_chars": 220,
        "fallback_engine": None,
    },
    "listen": {
        "engine": "picovoice",
        "dictation": "winh",
        "wake_word": "cerebro",
    },
    "queue": {
        "max_size": 50,
        "dedup": True,
        "dedup_threshold": 0.8,
    },
}


def ensure_home() -> Path:
    """Create ~/.voiceflow/ and subdirs if they don't exist."""
    VF_HOME.mkdir(parents=True, exist_ok=True)
    (VF_HOME / "commands").mkdir(exist_ok=True)
    return VF_HOME


def load_config() -> dict[str, Any]:
    """Load config from ~/.voiceflow/config.yaml, merged with defaults."""
    config_path = VF_HOME / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            user_config = yaml.safe_load(f) or {}
    else:
        user_config = {}
    return _deep_merge(DEFAULT_CONFIG, user_config)


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
