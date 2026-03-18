"""Tests for TTS engine routing and instantiation."""
from unittest.mock import patch, MagicMock
import pytest


def test_create_sapi_engine():
    from voiceflow.cli import _instantiate_engine
    engine = _instantiate_engine("sapi", {})
    from voiceflow.tts.sapi import SAPIEngine
    assert isinstance(engine, SAPIEngine)


def test_create_unknown_engine_raises():
    from voiceflow.cli import _instantiate_engine
    with pytest.raises(ValueError, match="TTS engine desconocido"):
        _instantiate_engine("nonexistent", {})


def test_create_kokoro_engine():
    from voiceflow.cli import _instantiate_engine
    engine = _instantiate_engine("kokoro", {"lang": "es", "voice": "ef_dora"})
    from voiceflow.tts.kokoro import KokoroEngine
    assert isinstance(engine, KokoroEngine)
    # Pipeline is lazy — only loaded on initialize()/speak()


def test_create_elevenlabs_engine():
    from voiceflow.cli import _instantiate_engine
    engine = _instantiate_engine("elevenlabs", {"voice": "Rachel", "api_key": "test-key"})
    from voiceflow.tts.elevenlabs import ElevenLabsEngine
    assert isinstance(engine, ElevenLabsEngine)


def test_fallback_to_sapi_on_error():
    from voiceflow.cli import _create_tts_engine
    # kokoro not installed properly → should fall back to sapi
    with patch("voiceflow.cli._instantiate_engine") as mock_inst:
        from voiceflow.tts.sapi import SAPIEngine
        mock_inst.side_effect = [ImportError("no kokoro"), SAPIEngine()]
        engine = _create_tts_engine({"engine": "kokoro", "fallback_engine": "sapi"})
        assert isinstance(engine, SAPIEngine)
