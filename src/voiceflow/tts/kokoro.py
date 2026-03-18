"""Kokoro TTS — local neural voice synthesis."""
from __future__ import annotations

import os
import tempfile
from voiceflow.tts.base import TTSEngine


class KokoroEngine(TTSEngine):
    """Local TTS using Kokoro (82M param model).

    Requires: pip install kokoro soundfile
    Requires: espeak-ng installed on system
    """

    def __init__(self, lang: str = "es", voice: str = "ef_dora"):
        self._lang = lang
        self._voice = voice
        self._pipeline = None
        self._stop_requested = False

    def initialize(self) -> None:
        """Load Kokoro pipeline (downloads model on first use)."""
        from kokoro import KPipeline

        # Map language codes: kokoro uses single char codes
        lang_map = {"es": "e", "en": "a", "fr": "f", "ja": "j", "ko": "k", "zh": "z"}
        lang_code = lang_map.get(self._lang, self._lang)

        self._pipeline = KPipeline(lang_code=lang_code)
        print(f"[Kokoro] Pipeline cargado (lang={lang_code}, voice={self._voice})")

    def speak(self, text: str) -> None:
        """Generate audio and play it."""
        if not self._pipeline:
            self.initialize()

        self._stop_requested = False

        import soundfile as sf

        # Generate audio chunks
        for i, (gs, ps, audio) in enumerate(self._pipeline(text, voice=self._voice)):
            if self._stop_requested:
                break

            # Write to temp file and play via winsound (available on Windows)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                tmp_path = f.name

            try:
                sf.write(tmp_path, audio, 24000)
                # Play synchronously via winsound
                import winsound
                if not self._stop_requested:
                    winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def stop(self) -> None:
        """Request stop of current speech."""
        self._stop_requested = True
        # Stop any playing winsound
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    def shutdown(self) -> None:
        self.stop()
        self._pipeline = None
