"""
Motor híbrido: openWakeWord para wake + Win+H para comandos.

Flujo:
1. OWW detecta "alexa" (o wake-word configurado)
2. Muestra overlay de captura con campo de texto
3. Activa Win+H que escribe en el campo
4. Captura el texto dictado y lo envía al callback
5. CommandRegistry parsea el comando

Ventajas:
- Wake-word muy fiable (OWW en inglés funciona perfecto)
- Comandos en español muy fiables (Win+H)
- No necesita entrenar modelos custom
"""

import queue
import sys
import threading
import time
import numpy as np
from typing import Callable, Optional, List

import sounddevice as sd
import pyautogui

from core.constants import (
    OVERLAY_READY_TIMEOUT,
    OVERLAY_READY_DELAY,
    WIN_H_ACTIVATION_DELAY,
    HOTKEY_RELEASE_DELAY,
    WAKE_COOLDOWN_HYBRID,
    AUDIO_POLL_INTERVAL,
)

# Para captura de dictado con overlay
from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
from PyQt6.QtWidgets import QApplication

# Importar openwakeword
try:
    import openwakeword
    from openwakeword.model import Model as OWWModel
    OWW_AVAILABLE = True
except ImportError:
    OWW_AVAILABLE = False
    print("[Hybrid] openWakeWord no instalado. Ejecuta: pip install openwakeword")


def _loading_animation(stop_event, message):
    """Muestra animación de carga."""
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\r[Hybrid] {message} {chars[i % len(chars)]}")
        sys.stdout.flush()
        i += 1
        time.sleep(AUDIO_POLL_INTERVAL)
    sys.stdout.write("\r" + " " * 60 + "\r")
    sys.stdout.flush()


class HybridEngine:
    """
    Motor híbrido: OWW para wake-word + Win+H para comandos.

    Estados:
    - IDLE: escuchando wake-word con OWW
    - AWAKE: capturando comando con Win+H
    """

    # Estados internos
    STATE_IDLE = "idle"
    STATE_AWAKE = "awake"
    STATE_PAUSED = "paused"  # No escucha wake-words (ej: durante dictado)

    def __init__(self, model_path: str, on_result: Callable[[str], None],
                 on_mic_level: Optional[Callable[[float], None]] = None,
                 gain: float = 1.0, mic_threshold: float = 3000.0,
                 blocksize: int = 8000,
                 upgrade_model_path: Optional[str] = None,
                 # Parámetros específicos del híbrido
                 wake_word: str = "alexa",
                 oww_threshold: float = 0.5,
                 command_window: float = 3.0,  # Default from config
                 on_state_change: Optional[Callable[[str], None]] = None,
                 on_timeout: Optional[Callable[[], None]] = None,
                 capture_overlay=None):
        """
        Inicializa el motor híbrido.

        Args:
            model_path: Ignorado (compatibilidad)
            on_result: Callback con texto reconocido (comando o wake-word)
            on_mic_level: Callback con nivel de micrófono (0-1)
            gain: Amplificación de audio
            mic_threshold: Umbral para normalizar nivel de mic
            blocksize: Tamaño de bloque de audio
            upgrade_model_path: Ignorado (compatibilidad)
            wake_word: Wake-word a detectar (default: "alexa")
            oww_threshold: Umbral de detección OWW (0-1)
            command_window: Segundos para capturar comando tras wake
            on_state_change: Callback cuando cambia estado interno
            on_timeout: Callback cuando hay timeout sin comando (para auto-ayuda)
            capture_overlay: Instancia de CaptureOverlay para capturar dictado
        """
        if not OWW_AVAILABLE:
            raise ImportError("openWakeWord no está instalado")

        self.on_result = on_result
        self.on_mic_level = on_mic_level
        self.on_state_change = on_state_change
        self.on_timeout = on_timeout
        self._queue = queue.Queue()
        self._running = False
        self._gain = gain
        self._mic_threshold = mic_threshold
        self._blocksize = blocksize
        self._threshold = oww_threshold
        self._wake_word = wake_word
        self._command_window = command_window

        # Estado interno
        self._state = self.STATE_IDLE
        self._awake_start = 0

        # Cargar modelo OWW
        stop_event = threading.Event()
        loader_thread = threading.Thread(
            target=_loading_animation,
            args=(stop_event, f"Cargando modelo '{wake_word}'...")
        )
        loader_thread.start()

        try:
            openwakeword.utils.download_models()
            # Cargar solo el modelo del wake-word especificado
            self.model = OWWModel(wakeword_models=[wake_word])
            self._model_names = [wake_word]
        finally:
            stop_event.set()
            loader_thread.join()

        print(f"[Hybrid] Wake-word: '{wake_word}' (umbral: {oww_threshold})")
        print(f"[Hybrid] Ventana de comando: {command_window}s")
        print(f"[Hybrid] Ganancia: {gain}x, Umbral mic: {mic_threshold}")

        # Cooldown para evitar detecciones repetidas
        self._last_wake_time = 0
        self._wake_cooldown = WAKE_COOLDOWN_HYBRID  # Segundos entre detecciones

        # Overlay de captura (se pasa desde main.py)
        self._capture_overlay = capture_overlay

        # Events para sincronización de captura
        self._capture_event = threading.Event()
        self._ready_event = threading.Event()
        self._captured_text = ""
        self._capture_lock = threading.Lock()  # Protege _captured_text

        # Conectar signal de ready del overlay
        if capture_overlay:
            capture_overlay.ready_signal.connect(self._on_overlay_ready)

    def _set_state(self, new_state: str):
        """Cambia el estado interno y notifica."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            print(f"[Hybrid] Estado: {old_state} -> {new_state}")
            if self.on_state_change:
                self.on_state_change(new_state)

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback de audio de sounddevice."""
        try:
            if status:
                print(f"[Hybrid] Audio status: {status}")

            audio_data = np.frombuffer(indata, dtype=np.int16).copy()

            if self._gain > 1.0:
                amplified = audio_data.astype(np.float32) * self._gain
                amplified = np.clip(amplified, -32768, 32767)
                audio_data = amplified.astype(np.int16)

            self._queue.put(audio_data)

            if self.on_mic_level:
                rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
                level = min(1.0, rms / self._mic_threshold)
                self.on_mic_level(level)
        except Exception as e:
            print(f"[Hybrid] Error en audio callback: {e}")

    def _on_overlay_ready(self):
        """Callback cuando el overlay está listo para recibir input."""
        print("[Hybrid] Overlay ready signal recibido")
        self._ready_event.set()

    def _on_capture_done(self, text: str):
        """Callback cuando el overlay termina de capturar."""
        with self._capture_lock:
            self._captured_text = text
        self._capture_event.set()

    def _capture_command_winh(self) -> Optional[str]:
        """
        Captura un comando usando Win+H con overlay de captura.

        Flujo:
        1. Muestra overlay con campo de texto (en thread Qt)
        2. Activa Win+H que escribe en el campo
        3. Espera timeout
        4. Extrae texto del campo

        Returns:
            Texto capturado o None si no se capturó nada
        """
        print(f"[Hybrid] Escuchando comando ({self._command_window}s)...")

        if self._capture_overlay is None:
            print("[Hybrid] ERROR: No hay capture_overlay configurado")
            return None

        # Reset eventos de captura
        self._capture_event.clear()
        self._ready_event.clear()
        self._captured_text = ""

        # Iniciar captura en el thread Qt
        # El overlay se mostrará y tomará foco
        try:
            self._capture_overlay.capture(self._on_capture_done, self._command_window)
        except Exception as e:
            print(f"[Hybrid] Error iniciando captura: {e}")
            return None

        # Esperar a que el overlay esté listo (máximo 2 segundos)
        print("[Hybrid] Esperando overlay ready...")
        if not self._ready_event.wait(timeout=OVERLAY_READY_TIMEOUT * 2):
            print("[Hybrid] Timeout esperando overlay ready")
            return None

        # Pequeña pausa para asegurar que el overlay tiene foco
        time.sleep(OVERLAY_READY_DELAY)

        print("[Hybrid] Activando Win+H...")
        # Activar Win+H - escribirá en el campo del overlay
        pyautogui.hotkey('win', 'h')

        # Esperar a que Win+H se active
        time.sleep(WIN_H_ACTIVATION_DELAY)

        # Esperar a que termine la captura (timeout + un poco más)
        if not self._capture_event.wait(timeout=self._command_window + 2):
            print("[Hybrid] Timeout esperando captura")
            return None

        # Cerrar Win+H panel
        time.sleep(HOTKEY_RELEASE_DELAY)
        pyautogui.press('escape')

        with self._capture_lock:
            texto = self._captured_text.strip()
        if texto:
            print(f"[Hybrid] Comando capturado: '{texto}'")
            return texto
        else:
            print("[Hybrid] No se capturó texto")
            return None

    def start(self):
        """Inicia el loop de detección (bloqueante)."""
        self._running = True
        oww_frame_size = 1280  # 80ms a 16kHz
        audio_buffer = np.array([], dtype=np.int16)
        self._frame_count = 0  # Contador de frames procesados
        self._last_status_time = time.time()  # Para log de status periódico

        with sd.RawInputStream(
            samplerate=16000,
            blocksize=self._blocksize,
            dtype='int16',
            channels=1,
            callback=self._audio_callback
        ):
            while self._running:
                try:
                    chunk = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # En estado AWAKE, descartar audio y limpiar buffer
                if self._state == self.STATE_AWAKE:
                    # Limpiar buffer para evitar audio viejo al volver a IDLE
                    old_size = len(audio_buffer)
                    audio_buffer = np.array([], dtype=np.int16)
                    # Vaciar la cola de audio
                    queue_cleared = 0
                    while not self._queue.empty():
                        try:
                            self._queue.get_nowait()
                            queue_cleared += 1
                        except queue.Empty:
                            break
                    if old_size > 0 or queue_cleared > 0:
                        print(f"[Hybrid] AWAKE: limpiando buffer ({old_size} samples) y cola ({queue_cleared} chunks)")
                    continue

                # En IDLE, detectamos wake-word
                audio_buffer = np.concatenate([audio_buffer, chunk])

                # Log de frames procesados (cada ~1 segundo para no saturar)
                frames_processed = 0
                while len(audio_buffer) >= oww_frame_size and self._state == self.STATE_IDLE:
                    frame = audio_buffer[:oww_frame_size]
                    audio_buffer = audio_buffer[oww_frame_size:]
                    frames_processed += 1
                    self._frame_count += 1

                    prediction = self.model.predict(frame)
                    current_time = time.time()

                    # Log de status cada 5 segundos
                    if current_time - self._last_status_time >= 5.0:
                        print(f"[Hybrid] Status: {self._frame_count} frames, umbral={self._threshold}, gain={self._gain}")
                        self._last_status_time = current_time

                    for model_name, score in prediction.items():
                        # Log de CUALQUIER score > 0 para ver todos los intentos
                        if score > 0.01:
                            if score >= self._threshold:
                                print(f"[Hybrid] ★★★ '{model_name}': {score:.3f} ★★★ DETECTADO")
                            elif score >= 0.3:
                                print(f"[Hybrid] ★★ '{model_name}': {score:.3f} (cerca)")
                            elif score >= 0.1:
                                print(f"[Hybrid] ★ '{model_name}': {score:.3f} (bajo)")
                            else:
                                print(f"[Hybrid] · '{model_name}': {score:.3f} (mínimo)")

                        if score >= self._threshold:
                            # Verificar cooldown
                            time_since_last = current_time - self._last_wake_time
                            if time_since_last < self._wake_cooldown:
                                print(f"[Hybrid] Cooldown activo ({time_since_last:.1f}s < {self._wake_cooldown}s), ignorando")
                                continue

                            self._last_wake_time = current_time
                            wake_word = model_name.replace("_", " ")
                            print(f"[Hybrid] === WAKE DETECTADO: '{wake_word}' ({score:.2f}) ===")

                            # Cambiar a estado AWAKE
                            self._set_state(self.STATE_AWAKE)

                            # Capturar comando en un thread para no bloquear audio
                            def capture_and_process():
                                print("[Hybrid] Iniciando captura de comando...")
                                comando = self._capture_command_winh()
                                if comando:
                                    # Enviar comando al callback
                                    print(f"[Hybrid] Comando capturado: '{comando}' -> enviando a on_result")
                                    self.on_result(comando)
                                else:
                                    # Si no se capturó nada, volver a IDLE
                                    print("[Hybrid] Timeout sin comando (captura vacía)")
                                    if self.on_timeout:
                                        self.on_timeout()

                                # Cooldown SIEMPRE después de captura (con o sin texto)
                                # Esto evita falsos positivos por audio residual
                                self._last_wake_time = time.time()
                                print(f"[Hybrid] Cooldown iniciado (próxima detección en {self._wake_cooldown}s)")

                                # Volver a IDLE
                                self._set_state(self.STATE_IDLE)
                                print("[Hybrid] Listo para nueva detección")

                            capture_thread = threading.Thread(target=capture_and_process)
                            capture_thread.start()

    def stop(self):
        """Detiene el loop de detección."""
        self._running = False

    def pause(self):
        """Pausa la detección de wake-words (ej: durante dictado)."""
        if self._state == self.STATE_IDLE:
            self._set_state(self.STATE_PAUSED)

    def resume(self):
        """Reanuda la detección de wake-words."""
        if self._state == self.STATE_PAUSED:
            self._set_state(self.STATE_IDLE)

    def get_model_name(self) -> str:
        """Retorna el modelo activo."""
        return f"hybrid:{self._wake_word}"

    def get_state(self) -> str:
        """Retorna el estado actual."""
        return self._state
