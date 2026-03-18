import asyncio
import json
import pytest
from unittest.mock import MagicMock

from voiceflow.client import VoiceFlowClient
from voiceflow.daemon import VoiceFlowDaemon
from voiceflow.protocol import Priority


@pytest.fixture
def mock_tts():
    engine = MagicMock()
    engine.speak = MagicMock()
    engine.stop = MagicMock()
    engine.initialize = MagicMock()
    engine.shutdown = MagicMock()
    return engine


@pytest.mark.asyncio
async def test_client_say(mock_tts):
    daemon = VoiceFlowDaemon(tts_engine=mock_tts, port=0)
    await daemon.start()

    try:
        client = VoiceFlowClient(port=daemon.port)
        ack = await client.say("hello", priority=Priority.NORMAL)
        assert ack["type"] == "ack"
        assert ack["queued"] is True
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_client_status(mock_tts):
    daemon = VoiceFlowDaemon(tts_engine=mock_tts, port=0)
    await daemon.start()

    try:
        client = VoiceFlowClient(port=daemon.port)
        status = await client.status()
        assert status["daemon"] == "running"
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_client_connection_refused():
    client = VoiceFlowClient(port=19999)
    with pytest.raises(ConnectionError):
        await client.say("hello")
