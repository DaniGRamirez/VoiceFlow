"""Priority queue with interruption for VoiceFlow TTS daemon."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from voiceflow.protocol import Priority, generate_id


@dataclass
class QueueItem:
    id: str
    text: str
    priority: Priority
    source: str | None = None


class SpeechQueue:
    """Priority queue with interruption, dedup, and truncation."""

    def __init__(
        self,
        max_size: int = 50,
        max_chars: int = 220,
        dedup: bool = False,
        dedup_threshold: float = 0.8,
    ):
        self._queue: list[QueueItem] = []
        self._interrupt_item: QueueItem | None = None
        self.max_size = max_size
        self.max_chars = max_chars
        self.dedup = dedup
        self.dedup_threshold = dedup_threshold

    @property
    def should_interrupt(self) -> bool:
        return self._interrupt_item is not None

    def get_interrupt(self) -> QueueItem | None:
        """Get and clear the interrupt item."""
        item = self._interrupt_item
        self._interrupt_item = None
        return item

    def enqueue(
        self, text: str, priority: Priority, source: str | None = None
    ) -> QueueItem | None:
        """Add a message to the queue. Returns the item or None if discarded."""
        # Truncate (hard cap at max_chars INCLUDING the "...")
        if self.max_chars and len(text) > self.max_chars:
            text = text[: self.max_chars - 3] + "..."

        item = QueueItem(id=generate_id(), text=text, priority=priority, source=source)

        # Urgent: bypass queue, set interrupt
        if priority == Priority.URGENT:
            self._interrupt_item = item
            return item

        # Dedup: only for low/normal
        if self.dedup and priority in (Priority.LOW, Priority.NORMAL) and source:
            for i, existing in enumerate(self._queue):
                if existing.source == source and self._similar(existing.text, text):
                    self._queue[i] = item  # replace
                    return item

        # Check capacity
        if len(self._queue) >= self.max_size:
            if priority == Priority.LOW:
                return None  # Low priority gets discarded when full
            # Try to make room by discarding a low-priority item
            for i in range(len(self._queue) - 1, -1, -1):
                if self._queue[i].priority == Priority.LOW:
                    self._queue.pop(i)
                    break
            else:
                return None  # No room, no low items to discard

        # Insert by priority
        if priority == Priority.HIGH:
            self._queue.insert(0, item)
        else:
            self._queue.append(item)

        return item

    def dequeue(self) -> QueueItem | None:
        """Get next item from queue."""
        if not self._queue:
            return None
        return self._queue.pop(0)

    def size(self) -> int:
        return len(self._queue)

    def clear(self) -> None:
        self._queue.clear()
        self._interrupt_item = None

    def _similar(self, a: str, b: str) -> bool:
        return SequenceMatcher(None, a, b).ratio() >= self.dedup_threshold
