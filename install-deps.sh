#!/bin/bash
# install-deps.sh — Inject all optional deps into pipx venv
set -e
echo "Inyectando dependencias opcionales en pipx venv..."
python -m pipx inject voiceflow \
    PyQt6 pyautogui pyperclip pygetwindow python-dotenv \
    numpy pvporcupine pvrecorder fastapi uvicorn
echo ""
echo "Verificando con vf doctor..."
vf doctor
