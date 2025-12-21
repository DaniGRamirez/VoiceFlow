"""
TTS Providers - Sistema pluggable de Text-to-Speech.

Cada provider define acciones browser para interactuar con servicios web de TTS.
"""

from .providers import TTS_PROVIDERS, get_provider

__all__ = ["TTS_PROVIDERS", "get_provider"]
