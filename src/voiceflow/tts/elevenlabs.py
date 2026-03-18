"""ElevenLabs TTS — cloud neural voice synthesis via REST API.

Uses the REST API directly instead of the SDK to avoid pydantic/Python 3.14 issues.
Playback via Windows MCI API (native MP3 support, no ffmpeg needed).
Free tier: 10k credits/month with premade voices.
"""
from __future__ import annotations

import ctypes
import os
import tempfile
import urllib.request
import urllib.error
import json

from voiceflow.tts.base import TTSEngine

# Premade voice IDs available on free tier accounts
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
    "bella": "hpp4J3VqNfWAUOO0d1Us",
    "adam": "pNInz6obpgDQGcFmaJgB",
}

API_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsEngine(TTSEngine):
    """Cloud TTS using ElevenLabs REST API + Windows MCI playback."""

    def __init__(
        self,
        voice: str = "sarah",
        api_key: str | None = None,
        speed: float = 1.0,
        model: str = "eleven_flash_v2_5",
    ):
        self._voice = voice
        self._api_key = api_key
        self._speed = min(max(speed, 0.7), 1.2)  # ElevenLabs range: 0.7-1.2
        self._model = model
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
        print(f"[ElevenLabs] Inicializado (voice={self._voice}, speed={self._speed}, model={self._model})")

    def speak(self, text: str) -> None:
        if not self._api_key:
            self.initialize()

        self._stop_requested = False
        voice_id = self._resolve_voice_id()

        # Call ElevenLabs TTS API
        url = f"{API_BASE}/text-to-speech/{voice_id}"
        payload = json.dumps({
            "text": text,
            "model_id": self._model,
            "speed": self._speed,
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

        # Write to temp mp3
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            if not self._stop_requested:
                _mci_play_sync(tmp_path)
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
        _mci_stop()

    def shutdown(self) -> None:
        self.stop()


def _mci_play_sync(path: str) -> None:
    """Play audio file synchronously using Windows MCI API. Supports MP3, WAV, etc."""
    winmm = ctypes.windll.winmm
    buf = ctypes.create_unicode_buffer(255)
    winmm.mciSendStringW(f'open "{path}" type mpegvideo alias el_tts', buf, 254, 0)
    winmm.mciSendStringW("play el_tts wait", buf, 254, 0)
    winmm.mciSendStringW("close el_tts", buf, 254, 0)


def _mci_stop() -> None:
    """Stop any playing MCI audio."""
    try:
        winmm = ctypes.windll.winmm
        buf = ctypes.create_unicode_buffer(255)
        winmm.mciSendStringW("stop el_tts", buf, 254, 0)
        winmm.mciSendStringW("close el_tts", buf, 254, 0)
    except Exception:
        pass
