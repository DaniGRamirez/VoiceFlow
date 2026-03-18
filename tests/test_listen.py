import asyncio
import json
import pytest
from unittest.mock import MagicMock

from voiceflow.daemon import VoiceFlowDaemon
from voiceflow.protocol import TranscriptionEvent


@pytest.fixture
def mock_tts():
    engine = MagicMock()
    engine.speak = MagicMock()
    engine.stop = MagicMock()
    engine.initialize = MagicMock()
    engine.shutdown = MagicMock()
    return engine


@pytest.mark.asyncio
async def test_transcription_broadcast(mock_tts):
    import websockets

    daemon = VoiceFlowDaemon(tts_engine=mock_tts, port=0)
    await daemon.start()
    port = daemon.port

    try:
        async with websockets.connect(f"ws://localhost:{port}") as ws:
            await daemon.broadcast(TranscriptionEvent(text="hola cerebro", final=True))
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert response["type"] == "transcription"
            assert response["text"] == "hola cerebro"
            assert response["final"] is True
    finally:
        await daemon.stop()
