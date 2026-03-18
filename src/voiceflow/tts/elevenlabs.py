"""ElevenLabs TTS — cloud neural voice synthesis via REST API.

Uses the REST API directly instead of the SDK to avoid pydantic/Python 3.14 issues.
Free tier: 10k credits/month. Free users must use their own cloned voices or
the default voice IDs that come with the account.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import urllib.request
import urllib.error
import json

from voiceflow.tts.base import TTSEngine

# Default voice IDs available on all accounts (including free)
DEFAULT_VOICES = {
    "aria": "9BWtsMINqrJLrRacOk9x",
    "roger": "CwhRBWXzGAHq8TQ4Fs17",
    "sarah": "EXAVITQu4vr4xnSDxMaL",
    "laura": "FGY2WhTYpPnrIDTdsKH5",
    "charlie": "IKne3meq5aSn9XLyUdCD",
    "george": "JBFqnCBsd6RMkjVDRZzb",
    "callum": "N2lVS1w4EtoT3dr4eOWO",
    "river": "SAz9YHcvj6GT2YYXdXww",
    "liam": "TX3LPaxmHKxFdv7VOQHJ",
    "charlotte": "XB0fDUnXU5powFXDhCwa",
    "alice": "Xb7hH8MSUJpSbSDYk0k2",
    "matilda": "XrExE9yKIg1WjnnlVkGX",
    "will": "bIHbv24MWmeRgasZH58o",
    "jessica": "cgSgspJ2msm6clMCkdW9",
    "eric": "cjVigY5qzO86Huf0OWal",
    "chris": "iP95p4xoKVk53GoZ742B",
    "brian": "nPczCjzI2devNBz1zQrb",
    "daniel": "onwK4e9ZLuTAKqWW03F9",
    "lily": "pFZP5JQG7iQjIQuC4Bku",
    "bill": "pqHfZKP75CvOlQylNhV4",
}

API_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsEngine(TTSEngine):
    """Cloud TTS using ElevenLabs REST API.

    No SDK dependency — uses urllib directly.
    """

    def __init__(self, voice: str = "aria", api_key: str | None = None):
        self._voice = voice
        self._api_key = api_key
        self._stop_requested = False

    def initialize(self) -> None:
        if not self._api_key:
            self._api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not self._api_key:
            raise ValueError(
                "ElevenLabs API key no encontrada. "
                "Configura tts.api_key en ~/.voiceflow/config.yaml "
                "o exporta ELEVENLABS_API_KEY"
            )
        print(f"[ElevenLabs] Inicializado (voice={self._voice})")

    def speak(self, text: str) -> None:
        if not self._api_key:
            self.initialize()

        self._stop_requested = False
        voice_id = self._resolve_voice_id()

        # Call ElevenLabs TTS API
        url = f"{API_BASE}/text-to-speech/{voice_id}"
        payload = json.dumps({
            "text": text,
            "model_id": "eleven_flash_v2_5",
        }).encode("utf-8")

        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                audio_bytes = response.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"[ElevenLabs] Error API ({e.code}): {body}")
            return
        except Exception as e:
            print(f"[ElevenLabs] Error: {e}")
            return

        if self._stop_requested or not audio_bytes:
            return

        # Write to temp mp3 and play via PowerShell MediaPlayer
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            if not self._stop_requested:
                subprocess.run(
                    [
                        "powershell", "-NoProfile", "-Command",
                        f"Add-Type -AssemblyName PresentationCore; "
                        f"$p = New-Object System.Windows.Media.MediaPlayer; "
                        f"$p.Open([Uri]'{tmp_path}'); "
                        f"$p.Play(); "
                        f"Start-Sleep -Milliseconds 500; "
                        f"while($p.Position -lt $p.NaturalDuration.TimeSpan) {{ Start-Sleep -Milliseconds 100 }}; "
                        f"$p.Close()"
                    ],
                    capture_output=True,
                    timeout=30,
                )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _resolve_voice_id(self) -> str:
        voice_lower = self._voice.lower()
        if voice_lower in DEFAULT_VOICES:
            return DEFAULT_VOICES[voice_lower]
        return self._voice

    def stop(self) -> None:
        self._stop_requested = True

    def shutdown(self) -> None:
        self.stop()
