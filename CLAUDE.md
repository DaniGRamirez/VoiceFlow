# CLAUDE.md

Guía para Claude Code cuando trabaja con este repositorio.

## Project Overview

VoiceFlow es un sistema de control por voz para Windows que permite interacción hands-free con VSCode y Claude chat. Usa Picovoice Porcupine para wake-word detection y Win+H de Windows para dictado.

## Quick Start

```bash
pip install -r requirements.txt
pip install -r requirements-picovoice.txt
python main.py
```

## Project Structure

```
voiceflow/
├── main.py                 # Entry point, CLI args, command registration
├── core/
│   ├── state.py            # State machine (IDLE, DICTATING, PROCESSING, PAUSED)
│   ├── commands.py         # Command registry and dispatch
│   ├── actions.py          # Actions (pyautogui, subprocess, clipboard)
│   ├── engine.py           # Motor Vosk (ASR continuo)
│   ├── hybrid_engine.py    # Motor híbrido (OWW + Win+H)
│   ├── oww_engine.py       # Motor OpenWakeWord
│   ├── picovoice_engine.py # Motor Picovoice Porcupine (RECOMENDADO)
│   └── logger.py           # Sistema de logging de uso
├── ui/
│   ├── overlay.py          # Overlay visual animado (PyQt6)
│   ├── capture_overlay.py  # Campo de texto para capturar Win+H
│   └── easing.py           # Funciones de animación
├── audio/
│   ├── feedback.py         # Sound player (pygame)
│   └── sounds/             # WAV files (ding, success, error, click, pop)
├── config/
│   ├── settings.py         # Load/save configuration
│   ├── aliases.py          # Sinónimos de comandos
│   └── default.json        # Default settings
├── models/                 # Modelos de voz (gitignored)
│   ├── vosk-model-small-es-0.42/
│   ├── vosk-model-es-0.42/
│   ├── Claudia_es_windows_v4_0_0.ppn  # Wake-word Picovoice
│   └── porcupine_params_es.pv         # Parámetros español
├── logs/
│   └── usage.json          # Estadísticas de uso
└── legacy/                 # Scripts antiguos (Porcupine standalone)
```

## Motores de Reconocimiento

### Picovoice Porcupine (Recomendado)

```bash
python main.py -e picovoice
```

- Wake-word "Claudia" entrenado en español
- Requiere API key gratuita de [console.picovoice.ai](https://console.picovoice.ai/)
- Flujo: Wake-word → Overlay de captura → Win+H → Comando
- Mejor precisión y menor latencia (512 samples vs 1280)

**Archivos clave:**
- `core/picovoice_engine.py` - Motor principal
- `models/Claudia_es_windows_v4_0_0.ppn` - Modelo wake-word
- `ui/capture_overlay.py` - Campo de texto para Win+H

### Vosk (ASR Continuo)

```bash
python main.py -e vosk
```

- Reconocimiento continuo de voz
- Sin wake-word (escucha siempre)
- Modelos locales (small: 45MB, large: 1.1GB)
- Hot-swap de modelos: inicia con small, carga large en background

**Archivos clave:**
- `core/engine.py` - Motor Vosk con threading
- `models/vosk-model-*` - Modelos de idioma

### Hybrid/OWW (Legacy)

```bash
python main.py -e hybrid
```

- OpenWakeWord para wake-word (modelos en inglés)
- Win+H para comandos
- Menos preciso en español

## Arquitectura de Animaciones

### Estados del Sistema

```
State.IDLE       → Barras blancas animadas (wave ping-pong)
State.DICTATING  → Círculo rojo pulsante
State.PAUSED     → Círculo amarillo/dorado
State.PROCESSING → (Sin usar actualmente)
```

### Sistema de Transiciones

Todas las transiciones siguen el patrón: **collapse → hold → expand**

```python
class Transition:
    """Gestiona transición entre estados visuales."""

    def __init__(self, from_visual: str, to_visual: str, to_state: State):
        self.from_visual = from_visual  # "bars" | "circle"
        self.to_visual = to_visual
        self.to_state = to_state
        self.phase = "collapse"  # "collapse" | "hold" | "expand"

        # Duraciones
        self.collapse_duration = 0.1   # Colapso rápido
        self.hold_duration = 0.3       # Pausa en el centro
        self.expand_duration = 0.25    # Expansión con rebote
```

### Elementos Visuales

1. **Barras (IDLE)**: 11 barras blancas con animación de onda
2. **Punto (transición)**: Punto blanco pulsante durante hold
3. **Círculo (DICTATING/PAUSED)**: Rojo o amarillo según estado

**Archivo clave:** `ui/overlay.py` (~1000 líneas)

### Modo Listening

Cuando se detecta wake-word:
- Sacudida breve del overlay
- Barras se despliegan con animación de pulsación
- Transición bars → bars con colapso y expansión

## Sistema de Comandos

### Registrar un Comando

```python
# En main.py
registry.register(Command(
    keywords=LISTO_ALIASES,          # Lista de palabras que activan
    action=actions.on_listo,         # Función a ejecutar
    valid_states=[State.DICTATING],  # Estados donde es válido
    sound="success"                   # Sonido de feedback
))
```

### Aliases

Los aliases están en `config/aliases.py`:

```python
LISTO_ALIASES = ["listo", "lista", "listos", "ok", "okay"]
CLAUDIA_ALIASES = ["claudia", "novia", "claudio", "hey jarvis"]
```

### Añadir Nuevo Comando

1. Define aliases en `config/aliases.py`
2. Crea la función en `core/actions.py`
3. Registra en `main.py` con `registry.register()`

## Sistema de Logging

Ubicación: `logs/usage.json`

```json
{
  "sessions": [{
    "start": "2025-12-18T10:25:53",
    "end": "2025-12-18T10:27:53",
    "duration_seconds": 120.0,
    "commands": [{
      "time": "2025-12-18T10:26:18",
      "command": "claudia",
      "recognized": "claudia"
    }],
    "ignored": [{
      "time": "2025-12-18T10:26:09",
      "text": "clave"
    }]
  }]
}
```

**Uso:** Analizar `ignored` para añadir nuevos aliases cuando hay patrones de reconocimiento erróneo.

## Configuración

Archivo: `config.json` (se crea automáticamente)

```json
{
  "engine": "picovoice",
  "dictation_mode": "winh",
  "picovoice": {
    "access_key": "...",
    "sensitivity": 0.7,
    "command_window": 5.0
  },
  "overlay": {
    "size": 40,
    "position": [100, 100]
  },
  "timing": {
    "vscode_focus_delay": 0.3,
    "chat_open_delay": 0.5
  }
}
```

## Flujo de Datos

```
                    ┌─────────────────────┐
                    │   Picovoice Engine  │
                    │  (wake-word loop)   │
                    └──────────┬──────────┘
                               │ "Claudia" detectado
                               ▼
                    ┌─────────────────────┐
                    │   CaptureOverlay    │
                    │  (campo de texto)   │
                    └──────────┬──────────┘
                               │ Win+H escribe aquí
                               ▼
                    ┌─────────────────────┐
                    │   CommandRegistry   │
                    │  (match & dispatch) │
                    └──────────┬──────────┘
                               │ Comando encontrado
                               ▼
                    ┌─────────────────────┐
                    │      Actions        │
                    │ (pyautogui, etc.)   │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │  Overlay │    │  Sounds  │    │  Logger  │
        │ (visual) │    │ (audio)  │    │  (stats) │
        └──────────┘    └──────────┘    └──────────┘
```

## Testing Manual

El overlay tiene teclas de debug (cuando tiene foco):

| Tecla | Acción |
|-------|--------|
| 1 | Activar listening mode |
| 2 | Desactivar listening mode |
| 3 | IDLE → DICTATING |
| 4 | DICTATING → IDLE |
| 5 | Sacudida |
| 6 | Simular mic alto |
| 7 | Simular mic silencio |
| 8 | DICTATING → PAUSED |
| 9 | PAUSED → DICTATING |
| 0 | Reset a IDLE |

También hay menú de debug en click derecho del overlay.

## Dependencias Principales

| Paquete | Uso |
|---------|-----|
| PyQt6 | UI del overlay |
| pvporcupine | Wake-word detection |
| pvrecorder | Captura de audio para Picovoice |
| vosk | ASR alternativo |
| pyautogui | Automatización de teclado/mouse |
| pygame | Reproducción de sonidos |
| sounddevice | Captura de audio para Vosk |
