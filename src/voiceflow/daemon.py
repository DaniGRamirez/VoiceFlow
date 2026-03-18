"""VoiceFlow WebSocket daemon — queue + TTS + broadcast."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from websockets.asyncio.server import ServerConnection, serve

from voiceflow.config import VF_HOME, load_config
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


class _ConfigWatcher(FileSystemEventHandler):
    """Watches config.yaml and calls back on changes with debounce."""

    def __init__(self, callback, debounce: float = 0.5):
        self._callback = callback
        self._debounce = debounce
        self._timer: threading.Timer | None = None

    def on_modified(self, event):
        if not isinstance(event, FileModifiedEvent):
            return
        if not event.src_path.replace("\\", "/").endswith("config.yaml"):
            return
        # Debounce — editors often write multiple times
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self._debounce, self._callback)
        self._timer.start()


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
        """Start WebSocket server, config watcher, and speech loop."""
        self._tts.initialize()
        self._event_loop = asyncio.get_running_loop()
        server_ctx = serve(self._handle_client, self._host, self._port)
        self._server = await server_ctx.__aenter__()
        self._speak_task = asyncio.create_task(self._speech_loop())
        self._start_config_watcher()
        logger.info(f"VoiceFlow daemon started on ws://{self._host}:{self.port}")

    def _start_config_watcher(self) -> None:
        """Watch ~/.voiceflow/config.yaml for changes and hot-reload TTS settings."""
        handler = _ConfigWatcher(self._on_config_changed)
        self._observer = Observer()
        self._observer.schedule(handler, str(VF_HOME), recursive=False)
        self._observer.daemon = True
        self._observer.start()
        logger.info(f"[ConfigWatcher] Monitoring {VF_HOME / 'config.yaml'}")

    def _on_config_changed(self) -> None:
        """Called from watcher thread when config.yaml changes."""
        try:
            new_config = load_config()
            tts_cfg = new_config.get("tts", {})
            self._apply_tts_config(tts_cfg)
            self._config = new_config
        except Exception as e:
            logger.error(f"[ConfigWatcher] Error reloading config: {e}")

    def _apply_tts_config(self, tts_cfg: dict) -> None:
        """Apply TTS config changes to the running engine."""
        changed = []
        new_voice = tts_cfg.get("voice")
        new_speed = tts_cfg.get("speed")

        if new_voice and hasattr(self._tts, "_voice") and self._tts._voice != new_voice:
            self._tts._voice = new_voice
            changed.append(f"voice={new_voice}")

        if new_speed is not None and hasattr(self._tts, "_speed") and self._tts._speed != new_speed:
            self._tts._speed = new_speed
            changed.append(f"speed={new_speed}")

        if changed:
            logger.info(f"[ConfigWatcher] TTS updated: {', '.join(changed)}")

    async def stop(self) -> None:
        """Stop daemon."""
        if hasattr(self, "_observer"):
            self._observer.stop()
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
