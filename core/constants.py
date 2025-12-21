"""
Constantes de timing para los motores de voz.

Centraliza los valores de delay/timeout usados en los engines
para facilitar ajustes y evitar magic numbers dispersos.
"""

# === OVERLAY TIMING ===
OVERLAY_READY_TIMEOUT = 1.0  # Segundos esperando a que overlay esté listo
OVERLAY_READY_DELAY = 0.2    # Delay después de overlay ready antes de hotkey

# === WIN+H DICTATION ===
WIN_H_ACTIVATION_DELAY = 0.3  # Delay después de activar Win+H
HOTKEY_RELEASE_DELAY = 0.2    # Delay después de cerrar Win+H con Escape

# === WAKE WORD ===
WAKE_COOLDOWN_PICOVOICE = 1.0  # Segundos entre detecciones de wake word (Picovoice)
WAKE_COOLDOWN_HYBRID = 1.5     # Segundos entre detecciones de wake word (Hybrid/OWW)

# === AUDIO ===
AUDIO_POLL_INTERVAL = 0.1  # Intervalo de espera en loops de audio
STATUS_LOG_INTERVAL = 5.0  # Segundos entre logs de status

# === MISC ===
HOTKEY_POST_DELAY = 0.2  # Delay genérico después de ejecutar hotkeys
