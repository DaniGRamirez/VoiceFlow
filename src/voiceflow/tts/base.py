"""TTS engine abstract base."""
from abc import ABC, abstractmethod


class TTSEngine(ABC):
    @abstractmethod
    def speak(self, text: str) -> None:
        """Speak text. Blocks until done or interrupted."""

    @abstractmethod
    def stop(self) -> None:
        """Stop current speech immediately."""

    def initialize(self) -> None:
        """Optional init (load models, etc). Called once at daemon start."""

    def shutdown(self) -> None:
        """Optional cleanup."""
