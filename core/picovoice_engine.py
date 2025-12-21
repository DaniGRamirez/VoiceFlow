"""
Motor híbrido: Picovoice Porcupine (wake-word) + Win+H (comando).

Flujo:
1. Porcupine detecta "Claudia" (o wake-word configurado)
2. Muestra overlay de captura con campo de texto
3. Activa Win+H que escribe en el campo
4. Captura el texto dictado y lo envía al callback
5. CommandRegistry parsea el comando

Ventajas:
- Wake-word custom "Claudia" entrenado en español
- Mejor precisión que openWakeWord para español
- Menor latencia (512 samples vs 1280)
- Comandos en español muy fiables (Win+H)
"""

import os
import sys
import threading
import time
import numpy as np
from typing import Callable, Optional

import pyautogui

from core.constants import (
    OVERLAY_READY_TIMEOUT,
    OVERLAY_READY_DELAY,
    WIN_H_ACTIVATION_DELAY,
    HOTKEY_RELEASE_DELAY,
    WAKE_COOLDOWN_PICOVOICE,
    STATUS_LOG_INTERVAL,
)

# Importar Picovoice Porcupine
try:
    import pvporcupine
    from pvrecorder import PvRecorder
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False
    print("[Picovoice] pvporcupine no instalado. Ejecuta: pip install pvporcupine pvrecorder")


class PicovoiceHybridEngine:
    """
    Motor híbrido: Porcupine para wake-word + Win+H para comandos.

    Estados:
    - IDLE: escuchando wake-word con Porcupine
    - AWAKE: capturando comando con Win+H
    - PAUSED: no escucha wake-words (ej: durante dictado)
    """

    # Estados internos
    STATE_IDLE = "idle"
    STATE_AWAKE = "awake"
    STATE_PAUSED = "paused"

    def __init__(self, model_path: str, on_result: Callable[[str], None],
                 on_mic_level: Optional[Callable[[float], None]] = None,
                 gain: float = 1.0, mic_threshold: float = 3000.0,
                 blocksize: int = 512,
                 upgrade_model_path: Optional[str] = None,
                 # Parámetros específicos de Picovoice
                 access_key: str = None,
                 keyword_path: str = None,
                 model_pv_path: str = None,
                 sensitivity: float = 0.7,
                 command_window: float = 5.0,
                 on_state_change: Optional[Callable[[str], None]] = None,
                 on_timeout: Optional[Callable[[], None]] = None,
                 capture_overlay=None):
        """
        Inicializa el motor híbrido Picovoice.

        Args:
            model_path: Ignorado (compatibilidad con otros engines)
            on_result: Callback con texto reconocido (comando)
            on_mic_level: Callback con nivel de micrófono (0-1)
            gain: Amplificación de audio (no usado con PvRecorder)
            mic_threshold: Umbral para normalizar nivel de mic
            blocksize: Ignorado (Porcupine usa frame_length fijo)
            upgrade_model_path: Ignorado (compatibilidad)
            access_key: API key de Picovoice Console (REQUERIDO)
            keyword_path: Ruta al archivo .ppn del wake-word
            model_pv_path: Ruta al archivo .pv de parámetros de idioma
            sensitivity: Sensibilidad de detección (0-1, mayor = más sensible)
            command_window: Segundos para capturar comando tras wake
            on_state_change: Callback cuando cambia estado interno
            on_timeout: Callback cuando hay timeout sin comando (para auto-ayuda)
            capture_overlay: Instancia de CaptureOverlay para capturar dictado
        """
        if not PORCUPINE_AVAILABLE:
            raise ImportError("pvporcupine no está instalado. Ejecuta: pip install pvporcupine pvrecorder")

        if not access_key:
            raise ValueError("access_key es requerido. Obtén uno gratis en https://console.picovoice.ai/")

        self.on_result = on_result
        self.on_mic_level = on_mic_level
        self.on_state_change = on_state_change
        self.on_timeout = on_timeout
        self._running = False
        self._mic_threshold = mic_threshold
        self._sensitivity = sensitivity
        self._command_window = command_window
        self._access_key = access_key

        # Estado interno
        self._state = self.STATE_IDLE

        # Resolver rutas de modelos
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        if keyword_path and not os.path.isabs(keyword_path):
            keyword_path = os.path.join(base_dir, keyword_path)

        if model_pv_path and not os.path.isabs(model_pv_path):
            model_pv_path = os.path.join(base_dir, model_pv_path)

        self._keyword_path = keyword_path
        self._model_pv_path = model_pv_path

        # Verificar que existen los archivos
        if keyword_path and not os.path.exists(keyword_path):
            raise FileNotFoundError(f"Modelo wake-word no encontrado: {keyword_path}")

        if model_pv_path and not os.path.exists(model_pv_path):
            raise FileNotFoundError(f"Modelo de idioma no encontrado: {model_pv_path}")

        # Extraer nombre del wake-word del archivo .ppn
        if keyword_path:
            self._wake_word = os.path.basename(keyword_path).split("_")[0].lower()
        else:
            self._wake_word = "unknown"

        # Cargar Porcupine
        print(f"[Picovoice] Cargando modelo '{self._wake_word}'...")

        try:
            # Crear instancia de Porcupine con modelo español
            porcupine_args = {
                "access_key": access_key,
                "keyword_paths": [keyword_path],
                "sensitivities": [sensitivity]
            }

            # Añadir modelo de idioma si se especifica
            if model_pv_path:
                porcupine_args["model_path"] = model_pv_path

            self._porcupine = pvporcupine.create(**porcupine_args)
            self._frame_length = self._porcupine.frame_length

        except pvporcupine.PorcupineActivationError as e:
            raise ValueError(f"API key inválida: {e}")

        except pvporcupine.PorcupineInvalidArgumentError as e:
            raise ValueError(f"Argumentos inválidos: {e}")

        print(f"[Picovoice] Wake-word: '{self._wake_word}' (sensibilidad: {sensitivity})")
        print(f"[Picovoice] Frame length: {self._frame_length} samples")
        print(f"[Picovoice] Ventana de comando: {command_window}s")

        # Cooldown para evitar detecciones repetidas
        self._last_wake_time = 0
        self._wake_cooldown = WAKE_COOLDOWN_PICOVOICE  # Segundos entre detecciones

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

        # Recorder (se crea en start())
        self._recorder = None

    def _set_state(self, new_state: str):
        """Cambia el estado interno y notifica."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            print(f"[Picovoice] Estado: {old_state} -> {new_state}")
            if self.on_state_change:
                self.on_state_change(new_state)

    def _on_overlay_ready(self):
        """Callback cuando el overlay está listo para recibir input."""
        print("[Picovoice] Overlay ready signal recibido")
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
        print(f"[Picovoice] Escuchando comando ({self._command_window}s)...")

        if self._capture_overlay is None:
            print("[Picovoice] ERROR: No hay capture_overlay configurado")
            return None

        # Reset eventos de captura
        self._capture_event.clear()
        self._ready_event.clear()
        self._captured_text = ""

        # Iniciar captura en el thread Qt
        try:
            self._capture_overlay.capture(self._on_capture_done, self._command_window)
        except Exception as e:
            print(f"[Picovoice] Error iniciando captura: {e}")
            return None

        # Esperar a que el overlay esté listo (máximo 1 segundo)
        print("[Picovoice] Esperando overlay ready...")
        if not self._ready_event.wait(timeout=OVERLAY_READY_TIMEOUT):
            print("[Picovoice] Timeout esperando overlay ready")
            return None

        # Pequeña pausa para asegurar que el overlay tiene foco
        time.sleep(OVERLAY_READY_DELAY)

        print("[Picovoice] Activando Win+H...")
        pyautogui.hotkey('win', 'h')

        # Esperar a que Win+H se active
        time.sleep(WIN_H_ACTIVATION_DELAY)

        # Esperar a que termine la captura
        if not self._capture_event.wait(timeout=self._command_window + 1):
            print("[Picovoice] Timeout esperando captura")
            return None

        # Cerrar Win+H panel
        time.sleep(HOTKEY_RELEASE_DELAY)
        pyautogui.press('escape')

        with self._capture_lock:
            texto = self._captured_text.strip()
        if texto:
            print(f"[Picovoice] Comando capturado: '{texto}'")
            return texto
        else:
            print("[Picovoice] No se capturó texto")
            return None

    def start(self):
        """Inicia el loop de detección (bloqueante)."""
        self._running = True
        self._frame_count = 0
        self._last_status_time = time.time()

        # Crear recorder con el frame_length de Porcupine
        self._recorder = PvRecorder(
            device_index=-1,
            frame_length=self._frame_length
        )
        self._recorder.start()
        print(f"[Picovoice] Micrófono activo (frame_length={self._frame_length})")

        try:
            while self._running:
                # Leer frame de audio
                pcm = self._recorder.read()
                self._frame_count += 1

                # Calcular nivel de mic para overlay
                if self.on_mic_level:
                    pcm_array = np.array(pcm, dtype=np.float32)
                    rms = np.sqrt(np.mean(pcm_array ** 2))
                    level = min(1.0, rms / self._mic_threshold)
                    self.on_mic_level(level)

                # En estado AWAKE o PAUSED, no procesamos wake-words
                if self._state != self.STATE_IDLE:
                    continue

                # Log de status periódico
                current_time = time.time()
                if current_time - self._last_status_time >= STATUS_LOG_INTERVAL:
                    print(f"[Picovoice] Status: {self._frame_count} frames, sensibilidad={self._sensitivity}")
                    self._last_status_time = current_time

                # Procesar frame con Porcupine
                result = self._porcupine.process(pcm)

                if result >= 0:
                    # Verificar cooldown
                    time_since_last = current_time - self._last_wake_time
                    if time_since_last < self._wake_cooldown:
                        print(f"[Picovoice] Cooldown activo ({time_since_last:.1f}s < {self._wake_cooldown}s), ignorando")
                        continue

                    self._last_wake_time = current_time
                    print(f"[Picovoice] === WAKE DETECTADO: '{self._wake_word}' ===")

                    # Cambiar a estado AWAKE
                    self._set_state(self.STATE_AWAKE)

                    # Capturar comando en un thread para no bloquear audio
                    def capture_and_process():
                        print("[Picovoice] Iniciando captura de comando...")
                        comando = self._capture_command_winh()
                        if comando:
                            print(f"[Picovoice] Comando capturado: '{comando}' -> enviando a on_result")
                            self.on_result(comando)
                        else:
                            print("[Picovoice] Timeout sin comando (captura vacía)")
                            if self.on_timeout:
                                self.on_timeout()

                        # Cooldown después de captura
                        self._last_wake_time = time.time()
                        print(f"[Picovoice] Cooldown iniciado (próxima detección en {self._wake_cooldown}s)")

                        # Volver a IDLE
                        self._set_state(self.STATE_IDLE)
                        print("[Picovoice] Listo para nueva detección")

                    capture_thread = threading.Thread(target=capture_and_process)
                    capture_thread.start()

        finally:
            if self._recorder:
                self._recorder.delete()
                self._recorder = None

    def stop(self):
        """Detiene el loop de detección."""
        self._running = False
        # Recorder ya se borra en el finally de start(), solo borrar porcupine
        if self._porcupine:
            self._porcupine.delete()
            self._porcupine = None

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
        return f"picovoice:{self._wake_word}"

    def get_state(self) -> str:
        """Retorna el estado actual."""
        return self._state
