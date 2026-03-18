import pytest
from unittest.mock import MagicMock, patch, call
from voiceflow.tts.base import TTSEngine
from voiceflow.tts.sapi import SAPIEngine


def test_tts_engine_is_abstract():
    with pytest.raises(TypeError):
        TTSEngine()


def test_sapi_engine_speak():
    with patch("voiceflow.tts.sapi.subprocess") as mock_subprocess:
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = 0
        mock_subprocess.Popen.return_value = mock_proc
        mock_subprocess.DEVNULL = -1

        engine = SAPIEngine()
        engine.speak("hello")

        mock_subprocess.Popen.assert_called_once()
        args = mock_subprocess.Popen.call_args
        assert "powershell" in args[0][0][0]
        mock_proc.wait.assert_called_once()


def test_sapi_engine_stop():
    with patch("voiceflow.tts.sapi.subprocess") as mock_subprocess:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running
        mock_subprocess.Popen.return_value = mock_proc
        mock_subprocess.DEVNULL = -1

        engine = SAPIEngine()
        engine._process = mock_proc
        engine.stop()

        mock_proc.terminate.assert_called_once()
