import json
import os

# Directorio base del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_CONFIG = {
    # Motor de reconocimiento: "vosk" (ASR completo) o "openwakeword" (solo wake-words)
    "engine": "vosk",

    "model_path": os.path.join(BASE_DIR, "models", "vosk-model-es-0.42"),

    # Modo de dictado: "wispr" o "winh" (Win+H de Windows)
    "dictation_mode": "winh",

    # Configuración de openWakeWord (solo si engine="openwakeword")
    "openwakeword": {
        "models": [],  # Lista de modelos a cargar (vacío = todos los pre-entrenados)
        "threshold": 0.5  # Umbral de detección (0-1)
    },

    # Configuración del motor híbrido (solo si engine="hybrid")
    "hybrid": {
        "wake_word": "alexa",  # Wake-word OWW a usar
        "threshold": 0.3,  # Umbral de detección (bajado para mejor recall)
        "command_window": 5.0  # Timeout máximo (si hay texto, termina 1s después)
    },

    # Configuración de Picovoice Porcupine (solo si engine="picovoice")
    "picovoice": {
        "access_key": "",  # API key de https://console.picovoice.ai/ (REQUERIDO)
        "keyword_path": "models/Claudia_es_windows_v4_0_0.ppn",  # Modelo wake-word
        "model_path": "models/porcupine_params_es.pv",  # Parámetros español
        "sensitivity": 0.7,  # Sensibilidad 0-1 (mayor = más sensible)
        "command_window": 5.0  # Timeout para captura de comando
    },

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
    },

    "timing": {
        "vscode_focus_delay": 0.3,
        "chat_open_delay": 0.5,
        "dictation_release_delay": 0.5,
        "clipboard_delay": 0.1,
        "key_delay": 0.1
    },

    "audio": {
        "gain": 3.0,  # Multiplicador de volumen (subido para mejor detección)
        "mic_threshold": 1500,  # Umbral para normalización visual (menor = más sensible)
        "blocksize": 1280  # Tamaño de fragmento = frame OWW (80ms a 16kHz)
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
