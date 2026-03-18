"""Windows SAPI TTS via pyttsx3."""
import pyttsx3
from voiceflow.tts.base import TTSEngine


class SAPIEngine(TTSEngine):
    def __init__(self):
        self._engine = pyttsx3.init()

    def speak(self, text: str) -> None:
        self._engine.say(text)
        self._engine.runAndWait()

    def stop(self) -> None:
        self._engine.stop()

    def shutdown(self) -> None:
        self._engine.stop()
