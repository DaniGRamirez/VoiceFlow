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

# === OVERLAY ANIMATION ===
# Duraciones de transiciones entre estados (segundos)
TRANSITION_COLLAPSE_DURATION = 0.1   # Colapso rapido al centro
TRANSITION_HOLD_DURATION = 0.3       # Pausa en el centro antes de expandir
TRANSITION_EXPAND_DURATION = 0.25    # Expansion despues del colapso

# Animacion de wake-word
WAKE_SHAKE_DURATION = 0.3  # Duracion de la sacudida al detectar wake-word

# Barras (audio visualizer)
BAR_COUNT = 11          # Numero de barras (impar para simetria)
BAR_WIDTH = 3           # Ancho de cada barra en px
BAR_GAP = 2             # Espacio entre barras
BAR_CORNER_RADIUS = 1.5 # Radio de esquinas redondeadas
