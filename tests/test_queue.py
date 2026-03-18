import pytest
from voiceflow.queue import SpeechQueue, QueueItem
from voiceflow.protocol import Priority


def test_enqueue_normal():
    q = SpeechQueue(max_size=10)
    item = q.enqueue("hello", Priority.NORMAL, source="test")
    assert item.text == "hello"
    assert q.size() == 1


def test_high_priority_goes_to_front():
    q = SpeechQueue(max_size=10)
    q.enqueue("first", Priority.NORMAL)
    q.enqueue("urgent one", Priority.HIGH)
    item = q.dequeue()
    assert item.text == "urgent one"


def test_urgent_sets_interrupt_flag():
    q = SpeechQueue(max_size=10)
    q.enqueue("speaking now", Priority.NORMAL)
    q.dequeue()  # now "speaking"
    q.enqueue("ALERT", Priority.URGENT)
    assert q.should_interrupt is True
    interrupt_item = q.get_interrupt()
    assert interrupt_item.text == "ALERT"
    assert q.should_interrupt is False


def test_dedup_replaces_similar():
    q = SpeechQueue(max_size=10, dedup=True, dedup_threshold=0.8)
    q.enqueue("Paso 1 completado", Priority.NORMAL, source="cerebro")
    q.enqueue("Paso 1 completado", Priority.NORMAL, source="cerebro")
    assert q.size() == 1  # deduped


def test_dedup_does_not_affect_urgent():
    q = SpeechQueue(max_size=10, dedup=True)
    q.enqueue("Error grave", Priority.NORMAL, source="cerebro")
    q.enqueue("Error grave", Priority.URGENT, source="cerebro")
    assert q.should_interrupt is True


def test_max_size_discards_low():
    q = SpeechQueue(max_size=3)
    q.enqueue("low1", Priority.LOW)
    q.enqueue("normal1", Priority.NORMAL)
    q.enqueue("normal2", Priority.NORMAL)
    item = q.enqueue("low2", Priority.LOW)
    assert item is None
    assert q.size() == 3


def test_truncation():
    q = SpeechQueue(max_size=10, max_chars=20)
    item = q.enqueue("This is a very long message that exceeds the limit", Priority.NORMAL)
    assert item.text.endswith("...")
    assert len(item.text) <= 20


def test_dequeue_empty_returns_none():
    q = SpeechQueue(max_size=10)
    assert q.dequeue() is None
