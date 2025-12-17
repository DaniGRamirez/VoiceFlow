"""
Claude Voice Trigger - VERSIÓN COMPLETA
========================================
Múltiples wake words para diferentes acciones:
- "jarvis" → Abre VSCode + Chat + Win+H
- "computer" → Enviar (Enter)
- "terminator" → Aceptar (y + Enter)
- "bumblebee" → Rechazar (n + Enter)

SETUP:
1. pip install pvporcupine pvrecorder pyautogui
2. API key gratis: https://console.picovoice.ai/
3. python claude_trigger_full.py
"""

import pvporcupine
from pvrecorder import PvRecorder
import pyautogui
import time

# ============================================
# CONFIGURACIÓN
# ============================================

ACCESS_KEY = "TU_API_KEY_AQUI"

# Mapeo: wake_word → acción
COMMANDS = {
    "jarvis": "activate",      # Activa Claude
    "computer": "send",        # Envía mensaje
    "terminator": "accept",    # Acepta acción
    "bumblebee": "reject",     # Rechaza acción
}

SENSITIVITY = 0.7

# ============================================
# ACCIONES
# ============================================

def action_activate():
    """Abre VSCode, chat, y Win+H"""
    print("🚀 Activando Claude...")
    pyautogui.hotkey('alt', 'tab')
    time.sleep(0.3)
    pyautogui.hotkey('ctrl', 'l')
    time.sleep(0.4)
    pyautogui.hotkey('win', 'h')
    print("✅ Dicta tu prompt!")

def action_send():
    """Pulsa Enter para enviar"""
    print("📤 Enviando...")
    pyautogui.press('enter')

def action_accept():
    """Acepta la acción de Claude"""
    print("✅ Aceptando...")
    pyautogui.press('y')
    time.sleep(0.05)
    pyautogui.press('enter')

def action_reject():
    """Rechaza la acción de Claude"""
    print("❌ Rechazando...")
    pyautogui.press('n')
    time.sleep(0.05)
    pyautogui.press('enter')

# Mapeo de acciones
ACTIONS = {
    "activate": action_activate,
    "send": action_send,
    "accept": action_accept,
    "reject": action_reject,
}

# ============================================
# MOTOR
# ============================================

def main():
    porcupine = None
    recorder = None
    
    keywords = list(COMMANDS.keys())
    sensitivities = [SENSITIVITY] * len(keywords)
    
    try:
        porcupine = pvporcupine.create(
            access_key=ACCESS_KEY,
            keywords=keywords,
            sensitivities=sensitivities
        )
        
        recorder = PvRecorder(
            device_index=-1,
            frame_length=porcupine.frame_length
        )
        recorder.start()
        
        print("=" * 50)
        print("🎧 Claude Voice Trigger - ACTIVO")
        print("=" * 50)
        print("Comandos disponibles:")
        for word, action in COMMANDS.items():
            print(f"  '{word}' → {action}")
        print("=" * 50)
        print("Presiona Ctrl+C para salir")
        print()
        
        while True:
            pcm = recorder.read()
            keyword_index = porcupine.process(pcm)
            
            if keyword_index >= 0:
                detected_word = keywords[keyword_index]
                action_name = COMMANDS[detected_word]
                print(f"\n🎤 Detectado: '{detected_word}'")
                ACTIONS[action_name]()
                
    except KeyboardInterrupt:
        print("\n👋 Saliendo...")
        
    finally:
        if recorder:
            recorder.delete()
        if porcupine:
            porcupine.delete()

if __name__ == "__main__":
    main()
