"""WebSocket protocol messages for VoiceFlow daemon."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from enum import Enum


class Priority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# --- Client → Daemon ---

@dataclass
class SayMessage:
    text: str
    priority: Priority = Priority.NORMAL
    source: str | None = None


@dataclass
class InterruptMessage:
    pass


@dataclass
class StatusRequest:
    pass


@dataclass
class MuteMessage:
    pass


@dataclass
class UnmuteMessage:
    pass


ClientMessage = SayMessage | InterruptMessage | StatusRequest | MuteMessage | UnmuteMessage


# --- Daemon → Client ---

@dataclass
class AckResponse:
    id: str
    queued: bool
    position: int


@dataclass
class StatusResponse:
    daemon: str
    speaking: bool
    current_text: str | None
    queue_length: int
    engine: str
    muted: bool


@dataclass
class SpokenEvent:
    id: str


@dataclass
class TranscriptionEvent:
    text: str
    final: bool


ServerMessage = AckResponse | StatusResponse | SpokenEvent | TranscriptionEvent


def generate_id() -> str:
    """Generate a short message ID."""
    return f"msg-{uuid.uuid4().hex[:8]}"


def parse_client_message(raw: str) -> ClientMessage:
    """Parse a JSON string into a client message."""
    data = json.loads(raw)
    msg_type = data.get("type")
    if msg_type == "say":
        return SayMessage(
            text=data["text"],
            priority=Priority(data.get("priority", "normal")),
            source=data.get("source"),
        )
    elif msg_type == "interrupt":
        return InterruptMessage()
    elif msg_type == "status":
        return StatusRequest()
    elif msg_type == "mute":
        return MuteMessage()
    elif msg_type == "unmute":
        return UnmuteMessage()
    raise ValueError(f"Unknown message type: {msg_type}")


def serialize_server_message(msg: ServerMessage) -> str:
    """Serialize a server message to JSON string."""
    if isinstance(msg, AckResponse):
        return json.dumps({"type": "ack", "id": msg.id, "queued": msg.queued, "position": msg.position})
    elif isinstance(msg, StatusResponse):
        return json.dumps({
            "type": "status", "daemon": msg.daemon, "speaking": msg.speaking,
            "currentText": msg.current_text, "queueLength": msg.queue_length,
            "engine": msg.engine, "muted": msg.muted,
        })
    elif isinstance(msg, SpokenEvent):
        return json.dumps({"type": "spoken", "id": msg.id})
    elif isinstance(msg, TranscriptionEvent):
        return json.dumps({"type": "transcription", "text": msg.text, "final": msg.final})
    raise ValueError(f"Unknown message type: {type(msg)}")
