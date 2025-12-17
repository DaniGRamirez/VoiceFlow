import json
import queue
from typing import Callable

import sounddevice as sd
from vosk import Model, KaldiRecognizer


class VoiceEngine:
    def __init__(self, model_path: str, on_result: Callable[[str], None]):
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, 16000)
        self.on_result = on_result
        self._queue = queue.Queue()
        self._running = False

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio status: {status}")
        self._queue.put(bytes(indata))

    def start(self):
        self._running = True
        with sd.RawInputStream(
            samplerate=16000,
            blocksize=8000,
            dtype='int16',
            channels=1,
            callback=self._audio_callback
        ):
            while self._running:
                data = self._queue.get()
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        self.on_result(text)

    def stop(self):
        self._running = False
