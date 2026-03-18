"""WebSocket client for VoiceFlow daemon."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets

from voiceflow.protocol import Priority


class VoiceFlowClient:
    """Short-lived client that connects, sends one message, and disconnects."""

    def __init__(self, host: str = "localhost", port: int = 9800, timeout: float = 5.0):
        self._url = f"ws://{host}:{port}"
        self._timeout = timeout

    async def say(
        self, text: str, priority: Priority = Priority.NORMAL, source: str | None = None
    ) -> dict[str, Any]:
        """Send a say message and return the ack."""
        msg: dict[str, Any] = {"type": "say", "text": text, "priority": priority.value}
        if source:
            msg["source"] = source
        return await self._send_and_recv(msg)

    async def status(self) -> dict[str, Any]:
        """Request daemon status."""
        return await self._send_and_recv({"type": "status"})

    async def interrupt(self) -> None:
        """Send interrupt."""
        await self._send({"type": "interrupt"})

    async def mute(self) -> None:
        await self._send({"type": "mute"})

    async def unmute(self) -> None:
        await self._send({"type": "unmute"})

    async def _send_and_recv(self, msg: dict) -> dict[str, Any]:
        try:
            async with websockets.connect(self._url) as ws:
                await ws.send(json.dumps(msg))
                response = await asyncio.wait_for(ws.recv(), timeout=self._timeout)
                return json.loads(response)
        except (OSError, ConnectionRefusedError) as e:
            raise ConnectionError(f"Cannot connect to VoiceFlow daemon at {self._url}") from e

    async def _send(self, msg: dict) -> None:
        try:
            async with websockets.connect(self._url) as ws:
                await ws.send(json.dumps(msg))
        except (OSError, ConnectionRefusedError) as e:
            raise ConnectionError(f"Cannot connect to VoiceFlow daemon at {self._url}") from e
