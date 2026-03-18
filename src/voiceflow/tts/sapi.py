"""Windows SAPI TTS — direct COM interface, no pyttsx3."""
import subprocess
import sys

from voiceflow.tts.base import TTSEngine


class SAPIEngine(TTSEngine):
    """Uses PowerShell + System.Speech for reliable TTS from any thread."""

    def __init__(self):
        self._process: subprocess.Popen | None = None

    def speak(self, text: str) -> None:
        # Escape single quotes for PowerShell
        escaped = text.replace("'", "''")
        cmd = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Speak('{escaped}')"
        )
        self._process = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._process.wait()
        self._process = None

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process = None

    def shutdown(self) -> None:
        self.stop()
