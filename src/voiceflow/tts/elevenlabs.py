"""ElevenLabs TTS — cloud neural voice synthesis."""
from __future__ import annotations

import os
import tempfile
from voiceflow.tts.base import TTSEngine


class ElevenLabsEngine(TTSEngine):
    """Cloud TTS using ElevenLabs API.

    Requires: pip install elevenlabs
    Requires: ELEVENLABS_API_KEY env var or api_key in config

    Free tier: 10k credits/month.
    """

    def __init__(self, voice: str = "Rachel", api_key: str | None = None):
        self._voice = voice
        self._api_key = api_key
        self._client = None
        self._stop_requested = False

    def initialize(self) -> None:
        """Initialize ElevenLabs client."""
        from elevenlabs.client import ElevenLabs

        if not self._api_key:
            self._api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not self._api_key:
            raise ValueError(
                "ElevenLabs API key no encontrada. "
                "Configura tts.api_key en ~/.voiceflow/config.yaml "
                "o exporta ELEVENLABS_API_KEY"
            )

        self._client = ElevenLabs(api_key=self._api_key)
        print(f"[ElevenLabs] Cliente inicializado (voice={self._voice})")

    def speak(self, text: str) -> None:
        """Generate audio via API and play it."""
        if not self._client:
            self.initialize()

        self._stop_requested = False

        # Generate audio
        audio_generator = self._client.text_to_speech.convert(
            text=text,
            voice_id=self._resolve_voice_id(),
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

        # Collect audio bytes
        audio_bytes = b""
        for chunk in audio_generator:
            if self._stop_requested:
                return
            audio_bytes += chunk

        if self._stop_requested:
            return

        # Write to temp file and play
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            # Use PowerShell MediaPlayer for mp3 playback
            import subprocess
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
        """Resolve voice name to voice ID. Uses name as ID if it looks like one."""
        # Common voice name → ID mapping
        known_voices = {
            "rachel": "21m00Tcm4TlvDq8ikWAM",
            "drew": "29vD33N1CtxCmqQRPOHJ",
            "clyde": "2EiwWnXFnvU5JabPnv8n",
            "paul": "5Q0t7uMcjvnagumLfvZi",
            "domi": "AZnzlk1XvdvUeBnXmlld",
            "dave": "CYw3kZ02Hs0563khs1Fj",
            "fin": "D38z5RcWu1voky8WS1ja",
            "sarah": "EXAVITQu4vr4xnSDxMaL",
            "antoni": "ErXwobaYiN019PkySvjV",
            "thomas": "GBv7mTt0atIp3Br8iCZE",
            "charlie": "IKne3meq5aSn9XLyUdCD",
            "emily": "LcfcDJNUP1GQjkzn1xUU",
            "elli": "MF3mGyEYCl7XYWbV9V6O",
            "callum": "N2lVS1w4EtoT3dr4eOWO",
            "patrick": "ODq5zmih8GrVes37Dizd",
            "harry": "SOYHLrjzK2X1ezoPC6cr",
            "liam": "TX3LPaxmHKxFdv7VOQHJ",
            "dorothy": "ThT5KcBeYPX3keUQqHPh",
            "josh": "TxGEqnHWrfWFTfGW9XjX",
            "arnold": "VR6AewLTigWG4xSOukaG",
            "charlotte": "XB0fDUnXU5powFXDhCwa",
            "matilda": "XrExE9yKIg1WjnnlVkGX",
            "james": "ZQe5CZNOzWyzPSCn5a3c",
            "jessica": "cgSgspJ2msm6clMCkdW9",
            "lily": "pFZP5JQG7iQjIQuC4Bku",
            "michael": "flq6f7yk4E4fJM5XTYuZ",
        }

        voice_lower = self._voice.lower()
        if voice_lower in known_voices:
            return known_voices[voice_lower]

        # Assume it's already a voice ID
        return self._voice

    def stop(self) -> None:
        self._stop_requested = True

    def shutdown(self) -> None:
        self.stop()
        self._client = None
