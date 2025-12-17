"""
Claude Voice Trigger
====================
pip install pvporcupine pvrecorder pyautogui
"""

import pvporcupine
from pvrecorder import PvRecorder
import pyautogui
import subprocess
import time

# ============================================
# CONFIGURACIÓN
# ============================================

ACCESS_KEY = "TU_API_KEY_AQUI"  # Obtener en https://console.picovoice.ai/
WAKE_WORD = "jarvis"
SENSITIVITY = 0.7

# ============================================
# ACCIÓN AL DETECTAR WAKE WORD
# ============================================

def focus_vscode():
    """Enfoca la ventana de VSCode usando PowerShell"""
    ps_command = '''
    $hwnd = (Get-Process | Where-Object { $_.MainWindowTitle -like "*Visual Studio Code*" } | Select-Object -First 1).MainWindowHandle
    if ($hwnd) {
        Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class Win { [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); }'
        [Win]::SetForegroundWindow($hwnd)
    }
    '''
    subprocess.run(['powershell', '-Command', ps_command], capture_output=True)

def on_wake_word_detected():
    print("🎤 Wake word detectado! Activando Claude...")
    
    # 1. Enfocar VSCode
    focus_vscode()
    time.sleep(0.5)
    
    # 2. Abrir el chat (Ctrl+L)
    pyautogui.hotkey('ctrl', 'alt', 'shift', 'g')
    time.sleep(0.3)
    
    # 3. Activar dictado de Windows (Win+H)
    pyautogui.hotkey('ctrl', 'alt','e')
    
    print("✅ Listo! Dicta tu prompt...")

# ============================================
# MOTOR
# ============================================

def main():
    porcupine = None
    recorder = None
    
    try:
        porcupine = pvporcupine.create(
            access_key=ACCESS_KEY,
            keywords=[WAKE_WORD],
            sensitivities=[SENSITIVITY]
        )
        
        recorder = PvRecorder(
            device_index=-1,
            frame_length=porcupine.frame_length
        )
        recorder.start()
        
        print("=" * 50)
        print(f"🎧 Escuchando: '{WAKE_WORD}'")
        print("   Ctrl+C para salir")
        print("=" * 50)
        
        while True:
            pcm = recorder.read()
            keyword_index = porcupine.process(pcm)
            
            if keyword_index >= 0:
                on_wake_word_detected()
                
    except KeyboardInterrupt:
        print("\n👋 Saliendo...")
        
    finally:
        if recorder:
            recorder.delete()
        if porcupine:
            porcupine.delete()

if __name__ == "__main__":
    main()