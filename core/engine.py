import json
import os
import queue
import sys
import threading
import time
import numpy as np
from typing import Callable, Optional

import sounddevice as sd
from vosk import Model, KaldiRecognizer


def _loading_animation(stop_event, model_name):
    """Muestra animacion de carga mientras se carga el modelo"""
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\r[Vosk] Cargando {model_name}... {chars[i % len(chars)]}")
        sys.stdout.flush()
        i += 1
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * 60 + "\r")  # Limpiar linea
    sys.stdout.flush()


class VoiceEngine:
    def __init__(self, model_path: str, on_result: Callable[[str], None],
                 on_mic_level: Optional[Callable[[float], None]] = None):
        # Verificar que el modelo existe
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Modelo Vosk no encontrado: {model_path}")

        model_name = os.path.basename(model_path)

        # Animacion de carga en thread separado
        stop_event = threading.Event()
        loader_thread = threading.Thread(target=_loading_animation, args=(stop_event, model_name))
        loader_thread.start()

        try:
            self.model = Model(model_path)
        finally:
            stop_event.set()
            loader_thread.join()

        print(f"[Vosk] Modelo '{model_name}' cargado correctamente")

        self.recognizer = KaldiRecognizer(self.model, 16000)
        self.on_result = on_result
        self.on_mic_level = on_mic_level
        self._queue = queue.Queue()
        self._running = False

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio status: {status}")
        self._queue.put(bytes(indata))

        # Calcular nivel de audio para feedback visual
        if self.on_mic_level:
            audio_data = np.frombuffer(indata, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
            # Normalizar a 0-1 (ajustar 3000 segun sensibilidad deseada)
            level = min(1.0, rms / 3000.0)
            self.on_mic_level(level)

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
