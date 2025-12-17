# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VoiceFlow is a voice-activated trigger system for Windows that enables hands-free control of VSCode and Claude chat. It uses wake word detection to activate various actions like opening the Claude chat, dictating via speech-to-text, and sending messages.

## Dependencies

```bash
pip install pvporcupine pvrecorder pyautogui
# For Vosk alternative:
pip install vosk sounddevice pyautogui pyperclip
```

## Running the Scripts

```bash
# Simple wake word trigger (English only, uses "jarvis")
python porcupine_claude_trigger/porcupine_simple/claude_trigger.py

# VSCode integration with "Claudia" (Spanish) + "Jarvis/Alexa" (English)
python claude_trigger_vscode.py

# Dual language trigger with Notepad
python claude_trigger_dual.py

# Vosk-based voice control (full command recognition)
python vosk/vosk_simple.py
```

## Architecture

### Two Voice Recognition Approaches

1. **Porcupine (pvporcupine)** - Wake word detection only
   - Requires API key from https://console.picovoice.ai/
   - Built-in words: jarvis, computer, alexa, terminator, bumblebee, etc.
   - Custom wake words via `.ppn` files (e.g., `Claudia_es_windows_v4_0_0.ppn`)
   - Spanish support requires `porcupine_params_es.pv` model file

2. **Vosk** - Full speech recognition
   - Requires downloaded language model (`vosk-model-small-es-0.42`)
   - Recognizes any spoken words, not just wake words
   - Better for complex command parsing

### Key Scripts

- **claude_trigger_vscode.py**: Main production script. Uses dual Porcupine instances (Spanish + English) to trigger VSCode chat with Wispr dictation integration.
- **claude_trigger_dual.py**: Similar but opens Notepad instead of VSCode.
- **vosk_simple.py**: Alternative using Vosk for command recognition with more commands (listo, cancela, enter, selección, opción N).

### Integration Flow

1. Wake word detected → Focus VSCode via PowerShell
2. Open Claude chat (Ctrl+Alt+Shift+G hotkey)
3. Hold Ctrl+Win to activate Wispr dictation
4. Second wake word releases keys, optionally presses Enter

### Configuration

Each script has a configuration section at the top with:
- `ACCESS_KEY`: Picovoice API key
- `CLAUDIA_PPN` / `SPANISH_MODEL`: Paths to Spanish wake word files
- `SENSITIVITY`: Detection threshold (0.5-0.9, lower = fewer false positives)

### External Files Required

- `Claudia_es_windows_v4_0_0.ppn`: Custom Spanish wake word model
- `porcupine_params_es.pv`: Spanish language model for Porcupine
- Vosk model folder for vosk_simple.py
