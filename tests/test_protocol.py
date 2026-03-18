import json
from voiceflow.protocol import (
    SayMessage, InterruptMessage, StatusRequest, MuteMessage, UnmuteMessage,
    AckResponse, StatusResponse, SpokenEvent, TranscriptionEvent,
    Priority, parse_client_message, serialize_server_message,
)


def test_say_message_parsing():
    raw = json.dumps({"type": "say", "text": "hello", "priority": "urgent", "source": "cerebro"})
    msg = parse_client_message(raw)
    assert isinstance(msg, SayMessage)
    assert msg.text == "hello"
    assert msg.priority == Priority.URGENT
    assert msg.source == "cerebro"


def test_say_message_defaults():
    raw = json.dumps({"type": "say", "text": "hello"})
    msg = parse_client_message(raw)
    assert msg.priority == Priority.NORMAL
    assert msg.source is None


def test_interrupt_message():
    raw = json.dumps({"type": "interrupt"})
    msg = parse_client_message(raw)
    assert isinstance(msg, InterruptMessage)


def test_ack_serialization():
    ack = AckResponse(id="msg-001", queued=True, position=2)
    data = json.loads(serialize_server_message(ack))
    assert data["type"] == "ack"
    assert data["id"] == "msg-001"
    assert data["position"] == 2


def test_status_response_serialization():
    status = StatusResponse(
        daemon="running", speaking=False, current_text=None,
        queue_length=0, engine="sapi", muted=False
    )
    data = json.loads(serialize_server_message(status))
    assert data["type"] == "status"
    assert data["queueLength"] == 0


def test_transcription_event():
    evt = TranscriptionEvent(text="cerebro ejecuta algo", final=True)
    data = json.loads(serialize_server_message(evt))
    assert data["type"] == "transcription"
    assert data["final"] is True
