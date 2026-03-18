"""VoiceFlow WebSocket daemon — queue + TTS + broadcast."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Set

from websockets.asyncio.server import ServerConnection, serve

from voiceflow.config import load_config
from voiceflow.protocol import (
    AckResponse,
    InterruptMessage,
    MuteMessage,
    Priority,
    SayMessage,
    SpokenEvent,
    StatusRequest,
    StatusResponse,
    TranscriptionEvent,
    UnmuteMessage,
    generate_id,
    parse_client_message,
    serialize_server_message,
)
from voiceflow.queue import SpeechQueue
from voiceflow.tts.base import TTSEngine

logger = logging.getLogger("voiceflow.daemon")


class VoiceFlowDaemon:
    def __init__(
        self,
        tts_engine: TTSEngine,
        host: str = "localhost",
        port: int = 9800,
        config: dict | None = None,
    ):
        self._tts = tts_engine
        self._host = host
        self._port = port
        self._config = config or load_config()
        self._clients: Set[ServerConnection] = set()
        self._muted = False
        self._speaking = False
        self._current_text: str | None = None
        self._server = None
        self._speak_task: asyncio.Task | None = None

        queue_cfg = self._config.get("queue", {})
        tts_cfg = self._config.get("tts", {})
        self._queue = SpeechQueue(
            max_size=queue_cfg.get("max_size", 50),
            max_chars=tts_cfg.get("max_chars", 220),
            dedup=queue_cfg.get("dedup", False),
            dedup_threshold=queue_cfg.get("dedup_threshold", 0.8),
        )

    @property
    def port(self) -> int:
        """Actual port (useful when started with port=0)."""
        if self._server and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self._port

    async def start(self) -> None:
        """Start WebSocket server and speech loop."""
        self._tts.initialize()
        self._event_loop = asyncio.get_running_loop()
        server_ctx = serve(self._handle_client, self._host, self._port)
        self._server = await server_ctx.__aenter__()
        self._speak_task = asyncio.create_task(self._speech_loop())
        logger.info(f"VoiceFlow daemon started on ws://{self._host}:{self.port}")

    async def stop(self) -> None:
        """Stop daemon."""
        if self._speak_task:
            self._speak_task.cancel()
            try:
                await self._speak_task
            except asyncio.CancelledError:
                pass
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self._tts.shutdown()
        logger.info("VoiceFlow daemon stopped")

    def broadcast_transcription_threadsafe(self, text: str, final: bool = True) -> None:
        """Broadcast a transcription from any thread (e.g., speech engine thread)."""
        msg = TranscriptionEvent(text=text, final=final)
        loop = self._loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(msg), loop)

    @property
    def _loop(self):
        """Get the running event loop (set during start)."""
        return getattr(self, "_event_loop", None)

    async def broadcast(self, msg: Any) -> None:
        """Send a server message to all connected clients."""
        import websockets

        data = serialize_server_message(msg)
        for client in list(self._clients):
            try:
                await client.send(data)
            except websockets.ConnectionClosed:
                self._clients.discard(client)

    async def _handle_client(self, ws: ServerConnection) -> None:
        self._clients.add(ws)
        try:
            async for raw in ws:
                try:
                    msg = parse_client_message(raw)
                    await self._process_message(ws, msg)
                except (ValueError, KeyError) as e:
                    await ws.send(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
        finally:
            self._clients.discard(ws)

    async def _process_message(self, ws: ServerConnection, msg: Any) -> None:
        if isinstance(msg, SayMessage):
            item = self._queue.enqueue(msg.text, msg.priority, msg.source)
            if item:
                ack = AckResponse(id=item.id, queued=True, position=self._queue.size())
                await ws.send(serialize_server_message(ack))
            else:
                await ws.send(
                    json.dumps({"type": "ack", "id": "", "queued": False, "position": -1})
                )

        elif isinstance(msg, InterruptMessage):
            self._tts.stop()

        elif isinstance(msg, StatusRequest):
            status = StatusResponse(
                daemon="running",
                speaking=self._speaking,
                current_text=self._current_text,
                queue_length=self._queue.size(),
                engine=self._config.get("tts", {}).get("engine", "unknown"),
                muted=self._muted,
            )
            await ws.send(serialize_server_message(status))

        elif isinstance(msg, MuteMessage):
            self._muted = True

        elif isinstance(msg, UnmuteMessage):
            self._muted = False

    async def _speech_loop(self) -> None:
        """Background loop that processes the queue and speaks."""
        while True:
            try:
                # Check for interrupt first (urgent bypasses mute)
                if self._queue.should_interrupt:
                    item = self._queue.get_interrupt()
                    if item:
                        self._tts.stop()
                        if not self._muted:
                            await self._speak_item(item)
                        continue

                # Normal dequeue
                item = self._queue.dequeue()
                if item and not self._muted:
                    await self._speak_item(item)
                else:
                    await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Speech loop error: {e}")
                await asyncio.sleep(0.5)

    async def _speak_item(self, item: Any) -> None:
        """Speak a single queue item in a thread (TTS is blocking)."""
        self._speaking = True
        self._current_text = item.text
        try:
            await asyncio.get_running_loop().run_in_executor(
                None, self._tts.speak, item.text
            )
            await self.broadcast(SpokenEvent(id=item.id))
        finally:
            self._speaking = False
            self._current_text = None
