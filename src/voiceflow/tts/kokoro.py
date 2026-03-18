"""Kokoro TTS — local neural voice synthesis via ONNX runtime.

Uses kokoro-onnx (no PyTorch, no spacy). Lightweight and fast.

Requires:
  pip install kokoro-onnx soundfile
  Download models to ~/.voiceflow/models/:
    kokoro-v1.0.onnx (~330MB)
    voices-v1.0.bin (~5MB)
  From: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
"""
from __future__ import annotations

import os
import tempfile

from voiceflow.config import VF_HOME
from voiceflow.tts.base import TTSEngine

MODELS_DIR = VF_HOME / "models"
DEFAULT_MODEL = MODELS_DIR / "kokoro-v1.0.onnx"
DEFAULT_VOICES = MODELS_DIR / "voices-v1.0.bin"

# Available voices: https://github.com/thewh1teagle/kokoro-onnx#voices
# Spanish voices start with "es_" prefix
VOICE_ALIASES = {
    "dora": "ef_dora",
    "sara": "ef_sara",
    "default": "af_heart",
}


class KokoroEngine(TTSEngine):
    """Local TTS using Kokoro ONNX (~82M params, ~330MB model)."""

    def __init__(self, lang: str = "es", voice: str = "af_heart"):
        self._lang = lang
        self._voice = VOICE_ALIASES.get(voice, voice)
        self._kokoro = None
        self._stop_requested = False

    def initialize(self) -> None:
        """Load Kokoro ONNX model."""
        from kokoro_onnx import Kokoro

        model_path = str(DEFAULT_MODEL)
        voices_path = str(DEFAULT_VOICES)

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Modelo Kokoro no encontrado en {model_path}\n"
                f"Descarga desde: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0\n"
                f"  kokoro-v1.0.onnx → {model_path}\n"
                f"  voices-v1.0.bin → {voices_path}"
            )

        self._kokoro = Kokoro(model_path, voices_path)
        print(f"[Kokoro] Modelo ONNX cargado (voice={self._voice})")

    def speak(self, text: str) -> None:
        """Generate audio and play via winsound."""
        if not self._kokoro:
            self.initialize()

        self._stop_requested = False

        import soundfile as sf

        # Generate audio (kokoro-onnx returns samples + sample_rate)
        samples, sample_rate = self._kokoro.create(
            text, voice=self._voice, speed=1.0, lang=self._lang
        )

        if self._stop_requested:
            return

        # Write to temp wav and play
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            tmp_path = f.name

        try:
            sf.write(tmp_path, samples, sample_rate)
            if not self._stop_requested:
                import winsound
                winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def stop(self) -> None:
        self._stop_requested = True
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    def shutdown(self) -> None:
        self.stop()
        self._kokoro = None
