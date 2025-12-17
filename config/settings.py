import json
import os

# Directorio base del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CONFIG = {
    "model_path": os.path.join(BASE_DIR, "models", "vosk-model-small-es-0.42"),

    "overlay": {
        "size": 40,
        "position": [100, 100],
        "opacity": 0.9
    },

    "sounds": {
        "enabled": True,
        "volume": 0.5
    },

    "hotkeys": {
        "vscode_chat": "ctrl+alt+shift+g"
    },

    "wispr": {
        "hold_keys": ["ctrl", "win"]
    }
}


def load_config(config_path: str = "config.json") -> dict:
    """Carga configuracion desde archivo, usa defaults si no existe"""
    config = DEFAULT_CONFIG.copy()

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # Merge user config with defaults
                _deep_merge(config, user_config)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config: {e}")

    return config


def save_config(config: dict, config_path: str = "config.json"):
    """Guarda configuracion a archivo"""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving config: {e}")


def _deep_merge(base: dict, override: dict):
    """Merge recursivo de diccionarios"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
