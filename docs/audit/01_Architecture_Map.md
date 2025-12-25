# VoiceFlow - Architecture Map

## Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AUDIO INPUT                                 │
│                           (Micrófono Windows)                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ENGINE LAYER (Selectable)                        │
├─────────────────┬─────────────────┬─────────────────┬───────────────────┤
│   Picovoice     │      Vosk       │  OpenWakeWord   │     Hybrid        │
│   Porcupine     │   (Continuo)    │  (Alternativo)  │   (OWW + Win+H)   │
│  (Wake-word)    │                 │                 │                   │
│   "Claudia"     │                 │                 │                   │
└────────┬────────┴────────┬────────┴────────┬────────┴─────────┬─────────┘
         │                 │                 │                  │
         ▼                 ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         CAPTURE LAYER                                    │
│  ┌──────────────────┐    ┌──────────────────┐                           │
│  │  CaptureOverlay  │    │   Win+H Dictation │                          │
│  │  (Campo texto)   │◄───│   (Sistema)       │                          │
│  └────────┬─────────┘    └──────────────────┘                           │
└───────────┼─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         STATE MACHINE                                    │
│  ┌──────────┐    ┌────────────┐    ┌──────────┐    ┌──────────────┐    │
│  │   IDLE   │───▶│  DICTATING │───▶│ PAUSED   │───▶│ PROCESSING   │    │
│  │(Esperando)│   │ (Grabando) │    │(Pausado) │    │ (Ejecutando) │    │
│  └──────────┘    └────────────┘    └──────────┘    └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      COMMAND REGISTRY                                    │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐        │
│  │  Built-in      │    │  Custom JSON   │    │   Aliases      │        │
│  │  (~30 cmds)    │    │ (config/cmds/) │    │ (aliases.py)   │        │
│  └───────┬────────┘    └───────┬────────┘    └───────┬────────┘        │
│          └─────────────────────┴─────────────────────┘                  │
│                                │                                         │
│                    find_chain(texto, estado)                            │
└─────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       EXECUTION LAYER                                    │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐        │
│  │    Actions     │    │ ActionExecutor │    │   Browser      │        │
│  │  (pyautogui)   │    │  (JSON cmds)   │    │  (Playwright)  │        │
│  │ - hotkeys      │    │ - hotkey       │    │ - click        │        │
│  │ - type         │    │ - type         │    │ - navigate     │        │
│  │ - clipboard    │    │ - shell        │    │ - screenshot   │        │
│  └────────────────┘    └────────────────┘    └────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    NOTIFICATION SYSTEM                                   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    EventServer (FastAPI :8765)                   │   │
│  │  POST /api/notification  - Crear notificación                   │   │
│  │  POST /api/intent        - Ejecutar intent                      │   │
│  │  POST /api/accept        - Shortcut aceptar                     │   │
│  │  POST /api/reject        - Shortcut rechazar                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│              ┌───────────────┼───────────────┐                         │
│              ▼               ▼               ▼                         │
│  ┌──────────────────┐ ┌────────────┐ ┌────────────────┐               │
│  │NotificationManager│ │  Pushover  │ │TranscriptWatcher│              │
│  │ - deduplicación  │ │(Push iOS)  │ │(Auto-dismiss)  │               │
│  │ - burst grouping │ │            │ │                │               │
│  └────────┬─────────┘ └────────────┘ └────────────────┘               │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                  │
│  │NotificationPanel │                                                  │
│  │   (PyQt6 UI)     │                                                  │
│  └──────────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          UI LAYER (PyQt6)                                │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐        │
│  │    Overlay     │    │OverlayRenderer │    │  OverlayDebug  │        │
│  │ (Always on top)│    │  (Shapes)      │    │  (Keyboard)    │        │
│  │ - Estados      │    │ - Barras       │    │  - Teclas 1-9  │        │
│  │ - Animaciones  │    │ - Círculos     │    │  - Space input │        │
│  │ - Transiciones │    │ - Óvalos       │    │                │        │
│  └────────────────┘    └────────────────┘    └────────────────┘        │
│                                                                          │
│  ┌────────────────┐    ┌────────────────┐                              │
│  │OverlayAnimator │    │    Easing      │                              │
│  │ - Spore system │    │ (Interpolation)│                              │
│  │ - Transitions  │    │                │                              │
│  └────────────────┘    └────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────┘
```

## Descripción de Capas

### Engine Layer
| Módulo | Responsabilidad | Input | Output | Dependencias |
|--------|-----------------|-------|--------|--------------|
| `picovoice_engine.py` | Wake-word + Win+H | Audio PCM | Texto comando | pvporcupine, pvrecorder |
| `engine.py` | ASR continuo Vosk | Audio PCM | Texto continuo | vosk, sounddevice |
| `oww_engine.py` | Wake-word OpenWakeWord | Audio PCM | Trigger evento | openwakeword |
| `hybrid_engine.py` | Combina OWW + comandos | Audio PCM | Texto comando | oww, capture |

### State Machine
| Estado | Visual | Transiciones |
|--------|--------|--------------|
| IDLE | Óvalo blanco animado | → DICTATING (wake-word) |
| DICTATING | Círculo rojo pulsante | → PAUSED, → IDLE (listo) |
| PAUSED | Círculo amarillo | → DICTATING (reanuda) |
| PROCESSING | Contracción | → IDLE |

### Command Registry
| Responsabilidad | Método | Descripción |
|-----------------|--------|-------------|
| Registro | `register(Command)` | Añade comando al registry |
| Búsqueda | `find_chain(texto, estado)` | Encuentra comandos que matchean |
| Matching | `_matches()` | Fuzzy match con aliases |
| Encadenamiento | `chain_match()` | "arriba listo" = 2 comandos |

### Execution Layer
| Componente | Acciones | Ejemplo |
|------------|----------|---------|
| Actions | hotkey, type, click | `actions.on_enter()` |
| ActionExecutor | JSON pipeline | `{"type": "hotkey", "keys": ["ctrl", "c"]}` |
| BrowserActions | Playwright | `browser.click_element()` |

### Notification System
| Componente | Responsabilidad |
|------------|-----------------|
| EventServer | Recibe requests HTTP, autentica Tailscale |
| NotificationManager | Deduplicación, burst grouping, orquestación |
| NotificationPanel | UI flotante PyQt6 |
| TranscriptWatcher | Monitor Claude Code, auto-dismiss |
| PushoverClient | Push notifications a iPhone |

## Flujo de Datos Principal

```
Micrófono → Picovoice (wake-word) → Win+H → CaptureOverlay → texto
                                                    │
                                                    ▼
StateMachine.set_state(DICTATING) ← ──────── "Claudia"
                                                    │
                                                    ▼
CommandRegistry.find_chain("enter listo", DICTATING)
                                                    │
                                                    ▼
[Command(ENTER), Command(LISTO)] ← ──────── matches
                                                    │
                                                    ▼
Actions.on_enter() → pyautogui.press('enter')
Actions.on_listo() → finalizar dictado
                                                    │
                                                    ▼
StateMachine.set_state(IDLE)
Overlay.transition(IDLE)
SoundPlayer.play("success")
```

## Violaciones de Separación de Responsabilidades

| Archivo | Problema | Impacto |
|---------|----------|---------|
| `main.py` | 600+ líneas, wiring + lógica | Difícil testing |
| `overlay.py` | 854 líneas, múltiples concerns | Ya parcialmente refactorizado a mixins |
| `event_server.py` | Auth + routing + business logic | Difícil de testear |
| `actions.py` | Mezcla pyautogui + lógica de estado | Acoplamiento |

## Decisiones Arquitectónicas Implícitas

1. **Motores intercambiables** - Strategy pattern para ASR engines
2. **Callbacks para eventos** - Observer pattern entre componentes
3. **Signals PyQt6** - Thread-safe communication UI
4. **JSON para comandos custom** - Extensibilidad sin código
5. **HTTP para notificaciones** - Desacoplamiento de Claude Code hooks
6. **Estado centralizado** - StateMachine como single source of truth
