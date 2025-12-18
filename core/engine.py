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
                 on_mic_level: Optional[Callable[[float], None]] = None,
                 gain: float = 1.0, mic_threshold: float = 3000.0,
                 blocksize: int = 8000,
                 upgrade_model_path: Optional[str] = None):
        """
        Inicializa el motor de voz.

        Args:
            model_path: Ruta al modelo inicial (normalmente el pequeño)
            upgrade_model_path: Ruta al modelo grande para cargar en background
        """
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
        self._gain = gain
        self._mic_threshold = mic_threshold
        self._blocksize = blocksize

        # Lock para swap atómico del recognizer
        self._recognizer_lock = threading.Lock()
        self._upgrade_thread = None
        self._current_model_name = model_name

        print(f"[Vosk] Ganancia: {gain}x, Umbral mic: {mic_threshold}, Blocksize: {blocksize} ({blocksize/16000*1000:.0f}ms)")

        # Si hay modelo de upgrade, cargarlo en background
        if upgrade_model_path and os.path.exists(upgrade_model_path):
            upgrade_name = os.path.basename(upgrade_model_path)
            if upgrade_name != model_name:
                self._start_upgrade(upgrade_model_path)

    def _start_upgrade(self, upgrade_model_path: str):
        """Inicia la carga del modelo grande en background."""
        self._upgrade_thread = threading.Thread(
            target=self._load_upgrade_model,
            args=(upgrade_model_path,),
            daemon=True
        )
        self._upgrade_thread.start()

    def _load_upgrade_model(self, model_path: str):
        """Carga el modelo grande en background y hace swap."""
        model_name = os.path.basename(model_path)
        print(f"[Vosk] Cargando modelo '{model_name}' en background...")

        start_time = time.time()
        try:
            # Cargar modelo grande (esto tarda ~10-15s)
            large_model = Model(model_path)
            large_recognizer = KaldiRecognizer(large_model, 16000)

            # Swap atómico
            with self._recognizer_lock:
                old_model = self.model
                self.model = large_model
                self.recognizer = large_recognizer
                self._current_model_name = model_name

            elapsed = time.time() - start_time
            print(f"[Vosk] Upgrade a '{model_name}' completado ({elapsed:.1f}s)")

            # Liberar modelo viejo (el GC lo limpiará)
            del old_model

        except Exception as e:
            print(f"[Vosk] Error en upgrade: {e}")

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio status: {status}")

        # Convertir a numpy para procesar
        audio_data = np.frombuffer(indata, dtype=np.int16).copy()

        # Aplicar ganancia si > 1.0
        if self._gain > 1.0:
            # Amplificar y clipear para evitar overflow
            amplified = audio_data.astype(np.float32) * self._gain
            amplified = np.clip(amplified, -32768, 32767)
            audio_data = amplified.astype(np.int16)

        # Enviar audio amplificado a Vosk
        self._queue.put(bytes(audio_data))

        # Calcular nivel de audio para feedback visual
        if self.on_mic_level:
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
            # Normalizar a 0-1 usando umbral configurable
            level = min(1.0, rms / self._mic_threshold)
            self.on_mic_level(level)

    def start(self):
        self._running = True
        with sd.RawInputStream(
            samplerate=16000,
            blocksize=self._blocksize,
            dtype='int16',
            channels=1,
            callback=self._audio_callback
        ):
            while self._running:
                data = self._queue.get()
                # Usar lock para acceso seguro al recognizer durante swap
                with self._recognizer_lock:
                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        text = result.get("text", "").strip()
                        if text:
                            self.on_result(text)

    def stop(self):
        self._running = False

    def get_model_name(self) -> str:
        """Retorna el nombre del modelo actualmente en uso."""
        return self._current_model_name
