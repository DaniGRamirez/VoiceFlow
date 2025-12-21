"""
TTS Providers - Definiciones de proveedores de Text-to-Speech.

Cada provider es un dict con:
    - name: Nombre del provider
    - url_contains: Texto para identificar la pestaña
    - actions: Dict con pipelines de acciones browser
        - speak: Acciones para pegar texto y reproducir
        - pause: Acciones para pausar reproducción
        - resume: Acciones para reanudar
        - stop: Acciones para detener
"""

from typing import Optional

# Providers de TTS disponibles
TTS_PROVIDERS = {
    "elevenlabs": {
        "name": "ElevenLabs",
        "url_contains": "elevenlabs.io",
        "description": "ElevenLabs Speech Synthesis - Alta calidad, voces realistas",
        "actions": {
            "speak": [
                {"action": "connect"},
                {"action": "find_tab", "url_contains": "elevenlabs.io"},
                {"action": "focus_window", "title": "Edge"},
                {"action": "wait_for", "selector": "[data-testid='tts-editor']", "timeout": 5},
                {"action": "clear_textarea", "selector": "[data-testid='tts-editor']"},
                {"action": "paste", "selector": "[data-testid='tts-editor']"},
                {"action": "wait", "seconds": 0.3},
                {"action": "click", "selector": "[data-testid='tts-generate']"},
            ],
            "pause": [
                {"action": "connect"},
                {"action": "find_tab", "url_contains": "elevenlabs.io"},
                {"action": "click", "selector": "[data-testid='audio-player-play-button']"},
            ],
            "resume": [
                {"action": "connect"},
                {"action": "find_tab", "url_contains": "elevenlabs.io"},
                {"action": "click", "selector": "[data-testid='audio-player-play-button']"},
            ],
            "stop": [
                {"action": "connect"},
                {"action": "find_tab", "url_contains": "elevenlabs.io"},
                {"action": "click", "selector": "[data-testid='audio-player-play-button']"},
            ],
        },
    },

    "naturalreaders": {
        "name": "NaturalReaders",
        "url_contains": "naturalreaders.com",
        "description": "NaturalReaders - TTS gratuito online",
        "actions": {
            "speak": [
                {"action": "connect"},
                {"action": "find_tab", "url_contains": "naturalreaders.com"},
                {"action": "focus_window", "title": "Edge"},
                {"action": "wait_for", "selector": "textarea", "timeout": 5},
                {"action": "clear_textarea", "selector": "textarea"},
                {"action": "paste", "selector": "textarea"},
                {"action": "wait", "seconds": 0.3},
                {"action": "click", "selector": "button.play-button"},
            ],
            "pause": [
                {"action": "connect"},
                {"action": "find_tab", "url_contains": "naturalreaders.com"},
                {"action": "click", "selector": "button.pause-button"},
            ],
        },
    },

    # Template para añadir más providers
    # "nuevo_provider": {
    #     "name": "Nombre Display",
    #     "url_contains": "dominio.com",
    #     "description": "Descripción del provider",
    #     "actions": {
    #         "speak": [...],
    #         "pause": [...],
    #     },
    # },
}

# Provider por defecto
DEFAULT_PROVIDER = "elevenlabs"


def get_provider(name: Optional[str] = None) -> Optional[dict]:
    """
    Obtiene un provider TTS por nombre.

    Args:
        name: Nombre del provider (None = default)

    Returns:
        Dict con configuración del provider o None si no existe
    """
    if name is None:
        name = DEFAULT_PROVIDER
    return TTS_PROVIDERS.get(name)


def list_providers() -> list:
    """Lista nombres de providers disponibles."""
    return list(TTS_PROVIDERS.keys())
