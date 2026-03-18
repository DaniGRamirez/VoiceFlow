import asyncio
import json
import pytest
import websockets
from unittest.mock import MagicMock

from voiceflow.daemon import VoiceFlowDaemon


@pytest.fixture
def mock_tts():
    engine = MagicMock()
    engine.speak = MagicMock()
    engine.stop = MagicMock()
    engine.initialize = MagicMock()
    engine.shutdown = MagicMock()
    return engine


@pytest.mark.asyncio
async def test_daemon_handles_say(mock_tts):
    daemon = VoiceFlowDaemon(tts_engine=mock_tts, port=0)
    await daemon.start()
    port = daemon.port

    try:
        async with websockets.connect(f"ws://localhost:{port}") as ws:
            await ws.send(json.dumps({"type": "say", "text": "hello", "priority": "normal"}))
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert response["type"] == "ack"
            assert response["queued"] is True
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_daemon_handles_status(mock_tts):
    daemon = VoiceFlowDaemon(tts_engine=mock_tts, port=0)
    await daemon.start()
    port = daemon.port

    try:
        async with websockets.connect(f"ws://localhost:{port}") as ws:
            await ws.send(json.dumps({"type": "status"}))
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
            assert response["type"] == "status"
            assert response["daemon"] == "running"
    finally:
        await daemon.stop()
