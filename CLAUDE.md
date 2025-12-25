# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VoiceFlow es un sistema de control por voz para Windows que permite interacción hands-free con VSCode y Claude chat. Usa Picovoice Porcupine para wake-word detection y Win+H de Windows para dictado.

## Quick Start

```bash
pip install -r requirements.txt
pip install -r requirements-picovoice.txt
python main.py
```

**Argumentos CLI:**
```bash
python main.py -e picovoice   # Motor recomendado (wake-word + Win+H)
python main.py -e vosk        # ASR continuo (sin wake-word)
python main.py -d             # Modo debug (sin reconocimiento)
```

## Architecture

### Data Flow

```
Picovoice Engine → CaptureOverlay → CommandRegistry → Actions
     ↓ wake-word        ↓ Win+H         ↓ match        ↓ execute
   "Claudia"         texto real      Command        pyautogui
```

### Component Interaction

```
main.py (entry point)
    ├── cli.py                                 # Argument parsing
    ├── bootstrap.py                           # Component initialization
    │   ├── create_core_components()           # State, Overlay, Sounds, Actions
    │   ├── create_notification_system()       # Panel, Manager, Server
    │   └── create_engine()                    # Picovoice/Vosk engine
    ├── commands_builtin.py                    # Command registration
    ├── StateMachine (core/state.py)           # IDLE, DICTATING, PAUSED
    ├── CommandRegistry (core/commands.py)     # Dispatch commands by state
    ├── Actions (core/actions.py)              # pyautogui automation
    ├── Overlay (ui/overlay.py)                # Visual feedback (PyQt6)
    │   ├── OverlayRenderer (mixins)           # Drawing bars/circles
    │   ├── OverlayAnimator                    # Transitions
    │   └── OverlayDebug                       # Keyboard controls
    ├── NotificationPanel (ui/)                # Claude Code notifications
    ├── EventServer (core/event_server.py)     # FastAPI HTTP server (with rate limiting)
    ├── NotificationManager (core/)            # Orchestrates notifications
    └── PicovoiceEngine (core/)                # Wake-word detection (with auto-reconnect)
```

### State Machine

```
State.IDLE       → Listening for wake-word (white bars animation)
State.DICTATING  → Recording dictation (red pulsing circle)
State.PAUSED     → Dictation paused (yellow circle)
```

### Transition System

All visual transitions follow: **collapse → hold → expand**
- `collapse_duration`: 0.1s
- `hold_duration`: 0.3s (white pulsing dot)
- `expand_duration`: 0.25s (with bounce)

## Key Subsystems

### Command System

Commands are registered in `commands_builtin.py`:

```python
registry.register(Command(
    keywords=LISTO_ALIASES,          # Trigger words (from config/aliases.py)
    action=actions.on_listo,         # Handler function
    allowed_states=[State.DICTATING],
    sound="success",
    next_state=State.IDLE            # For command chaining
))
```

**Adding a new command:**
1. Define aliases in `config/aliases.py`
2. Create handler in `core/actions.py`
3. Register in `commands_builtin.py`

### Custom Commands (JSON)

Load commands from `config/commands/*.json`:

```json
{
  "version": "1.0",
  "commands": [{
    "name": "mi comando",
    "keywords": ["palabra1", "palabra2"],
    "states": ["idle"],
    "actions": [
      {"type": "hotkey", "keys": ["ctrl", "c"]}
    ]
  }]
}
```

Action types: `hotkey`, `key`, `type`, `shell`, `sleep`, `notify`

### Notification System

Receives Claude Code permission requests via HTTP:

```
Claude Code Hook → POST /api/notification → NotificationPanel → User clicks
                                                    ↓
                                            EventServer executes hotkey
```

**Key endpoints (EventServer on port 8765):**
- `POST /api/notification` - Create notification
- `POST /api/intent` - Execute action (requires auth if remote)
- `POST /api/accept` - Accept/Enter shortcut
- `POST /api/reject` - Reject/Escape shortcut
- `POST /api/command` - Execute voice command via HTTP
- `GET /health` - Basic health check
- `GET /health/deep` - Detailed health with memory/components (requires auth)

### Remote Control (Tailscale)

When `tailscale.enabled=true` in config:
- Server binds to `0.0.0.0` instead of localhost
- Bearer token required for all remote requests
- Pushover notifications sent to iPhone
- iOS Shortcuts can call `/api/accept`, `/api/reject`

### Transcript Watcher

Monitors Claude Code transcript files to auto-dismiss notifications when tools complete in VSCode.

## Configuration

### Environment Variables (Recommended for secrets)

Create a `.env` file (see `.env.example`):

```env
PICOVOICE_ACCESS_KEY=your_picovoice_access_key
VOICEFLOW_BEARER_TOKEN=your_secure_bearer_token
PUSHOVER_USER_KEY=your_pushover_user_key
PUSHOVER_API_TOKEN=your_pushover_api_token
```

Environment variables override `config.json` values.

### config.json

`config.json` (created automatically):

```json
{
  "engine": "picovoice",
  "picovoice": {
    "sensitivity": 0.7,
    "command_window": 5.0
  },
  "notifications": {
    "enabled": true,
    "server": {"port": 8765}
  },
  "tailscale": {
    "enabled": false,
    "bind_address": "0.0.0.0"
  },
  "pushover": {
    "enabled": false
  }
}
```

## Debug Controls

When overlay has focus, use these keys:

| Key | Action |
|-----|--------|
| 1 | Activate listening mode |
| 2 | Deactivate listening mode |
| 3 | IDLE → DICTATING |
| 4 | DICTATING → IDLE |
| 5 | Shake animation |
| 8 | DICTATING → PAUSED |
| 9 | PAUSED → DICTATING |
| 0 | Reset to IDLE |
| Space | Silent input (type commands) |

Right-click overlay for debug menu.

## Usage Logging

`logs/usage.json` tracks:
- Commands executed per session
- Ignored text (useful for adding new aliases)
- Session duration

Analyze `ignored` entries to find common misrecognitions and add aliases.

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point, orchestrates startup and UI loop |
| `cli.py` | CLI argument parsing (argparse) |
| `bootstrap.py` | Component initialization and wiring |
| `commands_builtin.py` | Built-in command registration |
| `core/picovoice_engine.py` | Wake-word detection + Win+H capture |
| `core/commands.py` | CommandRegistry, Command class, chain matching |
| `core/actions.py` | All automation actions (pyautogui) |
| `core/action_executor.py` | Executes JSON action pipelines |
| `core/event_server.py` | FastAPI server for notifications (with rate limiting) |
| `core/notification_manager.py` | Orchestrates notification lifecycle |
| `ui/overlay.py` | Main visual overlay widget |
| `ui/capture_overlay.py` | Text field for Win+H capture |
| `config/aliases.py` | All command synonyms |
| `config/settings.py` | Config loading with env var support and validation |
| `tests/` | pytest test suite |
