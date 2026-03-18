import pytest
from unittest.mock import MagicMock, patch
from voiceflow.tts.base import TTSEngine
from voiceflow.tts.sapi import SAPIEngine


def test_tts_engine_is_abstract():
    with pytest.raises(TypeError):
        TTSEngine()


def test_sapi_engine_speak():
    with patch("voiceflow.tts.sapi.pyttsx3") as mock_pyttsx3:
        mock_engine = MagicMock()
        mock_pyttsx3.init.return_value = mock_engine

        engine = SAPIEngine()
        engine.speak("hello")

        mock_engine.say.assert_called_once_with("hello")
        mock_engine.runAndWait.assert_called_once()


def test_sapi_engine_stop():
    with patch("voiceflow.tts.sapi.pyttsx3") as mock_pyttsx3:
        mock_engine = MagicMock()
        mock_pyttsx3.init.return_value = mock_engine

        engine = SAPIEngine()
        engine.stop()

        mock_engine.stop.assert_called_once()
