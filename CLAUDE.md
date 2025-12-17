# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VoiceFlow is a voice-activated control system for Windows that enables hands-free interaction with VSCode and Claude chat. Uses Vosk for Spanish speech recognition and integrates with Wispr for dictation.

## Dependencies

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

## Project Structure

```
voiceflow/
├── main.py                 # Entry point
├── core/
│   ├── state.py            # State machine (IDLE, DICTATING, PROCESSING)
│   ├── commands.py         # Command registry and dispatch
│   ├── actions.py          # Actions (pyautogui, subprocess)
│   └── engine.py           # Vosk audio processing loop
├── ui/
│   └── overlay.py          # Floating indicator window (tkinter)
├── audio/
│   ├── feedback.py         # Sound player (pygame)
│   └── sounds/             # WAV files for feedback
├── config/
│   ├── settings.py         # Load/save configuration
│   └── default.json        # Default settings
├── models/                 # Vosk models (gitignored)
│   └── vosk-model-small-es-0.42/
└── legacy/                 # Old Porcupine-based scripts
```

## Architecture

### Flow
1. Vosk continuously listens for Spanish commands
2. `CommandRegistry` matches text to registered commands based on current state
3. `StateMachine` manages transitions: IDLE → DICTATING → IDLE
4. `Overlay` shows visual state (gray=idle, blue=dictating)
5. `SoundPlayer` provides audio feedback

### Voice Commands
- `claudia` → Focus VSCode, open chat, start Wispr dictation
- `listo` → Stop dictation, paste text (cleans "listo" from text)
- `cancela` → Stop dictation, delete all
- `enter` → Press Enter
- `seleccion` → Ctrl+A
- `eliminar` → Delete
- `opcion [uno/dos/tres...]` → Press number key

### Wispr Integration
- `keyDown('ctrl')` + `keyDown('win')` → Wispr starts listening
- `keyUp('win')` + `keyUp('ctrl')` → Wispr pastes transcription
- 0.5s delay after releasing keys for Wispr to paste

### Configuration
Edit `config.json` (created on first run) or modify `config/default.json`:
- `model_path`: Path to Vosk model
- `overlay.position`: Window position [x, y]
- `sounds.enabled`: Enable/disable audio feedback
- `hotkeys.vscode_chat`: Hotkey to open Claude chat
