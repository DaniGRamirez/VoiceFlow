"""
Motor de reconocimiento de wake-words usando openWakeWord.

Interfaz compatible con VoiceEngine para poder alternar fácilmente
entre Vosk (ASR completo) y openWakeWord (solo wake-words).
"""

import os
import queue
import sys
import threading
import time
import numpy as np
from typing import Callable, Optional, List

import sounddevice as sd

# Importar openwakeword
try:
    import openwakeword
    from openwakeword.model import Model as OWWModel
    OWW_AVAILABLE = True
except ImportError:
    OWW_AVAILABLE = False
    print("[OWW] openWakeWord no instalado. Ejecuta: pip install openwakeword")


def _loading_animation(stop_event, message):
    """Muestra animación de carga."""
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\r[OWW] {message} {chars[i % len(chars)]}")
        sys.stdout.flush()
        i += 1
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * 60 + "\r")
    sys.stdout.flush()


class OpenWakeWordEngine:
    """
    Motor de wake-words usando openWakeWord.

    Interfaz compatible con VoiceEngine:
    - __init__() con mismos parámetros
    - start() - loop bloqueante
    - stop() - detiene el loop
    - get_model_name() - retorna modelo activo
    """

    def __init__(self, model_path: str, on_result: Callable[[str], None],
                 on_mic_level: Optional[Callable[[float], None]] = None,
                 gain: float = 1.0, mic_threshold: float = 3000.0,
                 blocksize: int = 8000,
                 upgrade_model_path: Optional[str] = None,
                 # Parámetros específicos de OWW
                 oww_models: Optional[List[str]] = None,
                 oww_threshold: float = 0.5):
        """
        Inicializa el motor de wake-words.

        Args:
            model_path: Ignorado (compatibilidad con VoiceEngine). Usamos oww_models.
            on_result: Callback cuando se detecta un wake-word
            on_mic_level: Callback con nivel de micrófono (0-1)
            gain: Amplificación de audio
            mic_threshold: Umbral para normalizar nivel de mic
            blocksize: Tamaño de bloque de audio (muestras)
            upgrade_model_path: Ignorado (compatibilidad con VoiceEngine)
            oww_models: Lista de modelos OWW a cargar (None = todos)
            oww_threshold: Umbral de detección (0-1, default 0.5)
        """
        if not OWW_AVAILABLE:
            raise ImportError("openWakeWord no está instalado")

        self.on_result = on_result
        self.on_mic_level = on_mic_level
        self._queue = queue.Queue()
        self._running = False
        self._gain = gain
        self._mic_threshold = mic_threshold
        self._blocksize = blocksize
        self._threshold = oww_threshold

        # Descargar modelos si no existen
        stop_event = threading.Event()
        loader_thread = threading.Thread(
            target=_loading_animation,
            args=(stop_event, "Inicializando modelos...")
        )
        loader_thread.start()

        try:
            # Descargar modelos pre-entrenados si es necesario
            openwakeword.utils.download_models()

            # Cargar modelos (None = todos los disponibles)
            if oww_models:
                self.model = OWWModel(wakeword_models=oww_models)
                self._model_names = oww_models
            else:
                self.model = OWWModel()
                # Obtener nombres de modelos cargados
                self._model_names = list(self.model.models.keys())
        finally:
            stop_event.set()
            loader_thread.join()

        print(f"[OWW] Modelos cargados: {', '.join(self._model_names)}")
        print(f"[OWW] Umbral de detección: {oww_threshold}")
        print(f"[OWW] Ganancia: {gain}x, Umbral mic: {mic_threshold}, Blocksize: {blocksize}")

        # Para tracking de detecciones (evitar spam)
        self._last_detection = {}
        self._detection_cooldown = 1.0  # segundos entre detecciones del mismo wake-word

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback de audio de sounddevice."""
        if status:
            print(f"[OWW] Audio status: {status}")

        # Convertir a numpy
        audio_data = np.frombuffer(indata, dtype=np.int16).copy()

        # Aplicar ganancia si > 1.0
        if self._gain > 1.0:
            amplified = audio_data.astype(np.float32) * self._gain
            amplified = np.clip(amplified, -32768, 32767)
            audio_data = amplified.astype(np.int16)

        # Enviar a la cola de procesamiento
        self._queue.put(audio_data)

        # Calcular nivel de mic para feedback visual
        if self.on_mic_level:
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
            level = min(1.0, rms / self._mic_threshold)
            self.on_mic_level(level)

    def start(self):
        """Inicia el loop de detección (bloqueante)."""
        self._running = True

        # OWW espera frames de 80ms (1280 muestras a 16kHz)
        # Pero sounddevice usa blocksize configurable
        # Acumulamos audio hasta tener suficiente para OWW
        oww_frame_size = 1280  # 80ms a 16kHz
        audio_buffer = np.array([], dtype=np.int16)

        with sd.RawInputStream(
            samplerate=16000,
            blocksize=self._blocksize,
            dtype='int16',
            channels=1,
            callback=self._audio_callback
        ):
            while self._running:
                # Obtener audio de la cola
                try:
                    chunk = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # Acumular en buffer
                audio_buffer = np.concatenate([audio_buffer, chunk])

                # Procesar cuando tenemos suficiente audio
                while len(audio_buffer) >= oww_frame_size:
                    frame = audio_buffer[:oww_frame_size]
                    audio_buffer = audio_buffer[oww_frame_size:]

                    # Predecir con openWakeWord
                    prediction = self.model.predict(frame)

                    # Revisar cada modelo
                    current_time = time.time()
                    for model_name, score in prediction.items():
                        if score >= self._threshold:
                            # Verificar cooldown
                            last_time = self._last_detection.get(model_name, 0)
                            if current_time - last_time >= self._detection_cooldown:
                                self._last_detection[model_name] = current_time

                                # Limpiar nombre del modelo para el callback
                                # ej: "hey_jarvis" -> "hey jarvis"
                                wake_word = model_name.replace("_", " ")

                                print(f"[OWW] Detectado: '{wake_word}' ({score:.2f})")
                                self.on_result(wake_word)

    def stop(self):
        """Detiene el loop de detección."""
        self._running = False

    def get_model_name(self) -> str:
        """Retorna los nombres de modelos activos."""
        return "oww:" + ",".join(self._model_names[:3])  # Mostrar hasta 3
