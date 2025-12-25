"""
VoiceFlow CLI - Argument parsing and help.
"""

import argparse
import os
import sys

from config.settings import load_config, BASE_DIR


# Model aliases
MODEL_ALIASES = {
    "small": "vosk-model-small-es-0.42",
    "large": "vosk-model-es-0.42",
    "s": "vosk-model-small-es-0.42",
    "l": "vosk-model-es-0.42",
}

# Engine aliases
ENGINE_ALIASES = {
    "openwakeword": "openwakeword",
    "oww": "openwakeword",
    "wakeword": "openwakeword",
    "hybrid": "hybrid",
    "mix": "hybrid",
    "mixto": "hybrid",
    "picovoice": "picovoice",
    "pv": "picovoice",
    "porcupine": "picovoice",
    "vosk": "vosk",
}


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="VoiceFlow - Control por voz para VSCode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Motores de reconocimiento:
  vosk                     ASR completo (reconoce cualquier palabra)
  openwakeword, oww        Solo wake-words (más eficiente, modelos inglés)
  hybrid, mix              OWW wake + Win+H comandos
  picovoice, pv            Picovoice wake + Win+H comandos (recomendado)

Modelos Vosk disponibles:
  small, s                 vosk-model-small-es-0.42 (rápido, menos preciso)
  large, l                 vosk-model-es-0.42 (lento, más preciso)
  <nombre>                 Nombre completo de carpeta en models/

Modos de dictado:
  wispr                    Usa Wispr (Ctrl+Win) - requiere Wispr instalado
  winh                     Usa dictado de Windows (Win+H)

Ejemplos:
  python main.py                       # Picovoice + Win+H (default)
  python main.py -m small              # Vosk + modelo pequeño
  python main.py -e oww                # openWakeWord
  python main.py -e picovoice          # Picovoice (recomendado)
  python main.py -D winh               # Win+H + modelo large
  python main.py -d                    # Modo debug
"""
    )

    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Modo debug (sin reconocimiento de voz)"
    )

    parser.add_argument(
        "-e", "--engine",
        type=str,
        choices=["vosk", "openwakeword", "oww", "hybrid", "mix", "picovoice", "pv"],
        help="Motor de reconocimiento"
    )

    parser.add_argument(
        "-m", "--model",
        type=str,
        help="Modelo Vosk a usar (small, large, o nombre completo)"
    )

    parser.add_argument(
        "-D", "--dictation",
        type=str,
        choices=["wispr", "winh"],
        help="Modo de dictado: wispr o winh"
    )

    return parser.parse_args()


def get_engine_type(args: argparse.Namespace) -> str:
    """Get engine type from args or config."""
    if args.engine:
        engine = args.engine.lower()
        return ENGINE_ALIASES.get(engine, "vosk")

    config = load_config()
    return config.get("engine", "picovoice")


def get_dictation_mode(args: argparse.Namespace) -> str:
    """Get dictation mode from args or config."""
    if args.dictation:
        mode = args.dictation.lower()
        if mode in ("wispr", "winh"):
            return mode
        print(f"[WARN] Modo de dictado '{mode}' no reconocido, usando 'winh'")
        return "winh"

    config = load_config()
    return config.get("dictation_mode", "winh")


def get_model_paths(args: argparse.Namespace) -> tuple:
    """
    Get model paths based on args.

    Returns:
        (initial_model_path, upgrade_model_path)
    """
    small_path = os.path.join(BASE_DIR, "models", "vosk-model-small-es-0.42")
    large_path = os.path.join(BASE_DIR, "models", "vosk-model-es-0.42")

    if args.model:
        model_arg = args.model
        if model_arg in MODEL_ALIASES:
            model_name = MODEL_ALIASES[model_arg]
        else:
            model_name = model_arg
        return (os.path.join(BASE_DIR, "models", model_name), None)

    # Default: small first, upgrade to large
    if os.path.exists(small_path) and os.path.exists(large_path):
        return (small_path, large_path)
    elif os.path.exists(large_path):
        return (large_path, None)
    elif os.path.exists(small_path):
        return (small_path, None)
    else:
        config = load_config()
        return (config.get("model_path", large_path), None)
