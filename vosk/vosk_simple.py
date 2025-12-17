"""
Vosk + Wispr - Voice Control para VSCode
=========================================
Vosk detecta comandos, Wispr transcribe.

Flujo:
- "Claudia" → VSCode + Chat + Wispr escucha (Ctrl+Win down)
- [Dictas con Wispr...]
- "Listo" → Suelta Wispr (pega automáticamente)
- "Cancela" → Suelta Wispr + Ctrl+A + Delete (borra todo)

Comandos globales:
- "Enter" → Pulsa Enter
- "Selección" → Ctrl+A
- "Opción uno/dos/tres..." → Pulsa 1/2/3...

SETUP:
pip install vosk sounddevice pyautogui
"""

import json
import queue
import subprocess
import time
import sounddevice as sd
import pyautogui
from vosk import Model, KaldiRecognizer

# ============================================
# CONFIGURACIÓN
# ============================================

MODEL_PATH = "vosk-model-small-es-0.42"

# ============================================
# ESTADO
# ============================================

modo_claudia = False  # True = esperando "listo" o "cancela"
q = queue.Queue()

# ============================================
# ACCIONES
# ============================================

def on_claudia():
    global modo_claudia
    
    print("\n🎤 'Claudia' detectado!")
    
    # Enfocar VSCode
    ps_command = '''
$hwnd = (Get-Process | Where-Object { $_.MainWindowTitle -like "*Visual Studio Code*" } | Select-Object -First 1).MainWindowHandle
if ($hwnd) {
    Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class Win { [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); }'
    [Win]::SetForegroundWindow($hwnd)
}
'''
    subprocess.run(['powershell', '-Command', ps_command], capture_output=True)
    time.sleep(0.3)
    
    # Abrir chat (tu hotkey)
    pyautogui.hotkey('ctrl', 'alt', 'shift', 'g')
    time.sleep(0.3)
    
    # Mantener pulsado Ctrl+Win (Wispr escucha)
    pyautogui.keyDown('ctrl')
    pyautogui.keyDown('win')
    
    modo_claudia = True
    
    print("✅ VSCode + Chat + Wispr activo")
    print("🎙️ Dictando... di 'listo' para pegar o 'cancela' para borrar\n")

def on_listo():
    global modo_claudia
    
    if not modo_claudia:
        return
    
    print("\n✅ 'Listo' detectado!")
    
    # Soltar Ctrl+Win (Wispr pega automáticamente)
    pyautogui.keyUp('win')
    pyautogui.keyUp('ctrl')
    time.sleep(0.5)  # Esperar a que Wispr pegue
    
    # Seleccionar todo, copiar, limpiar, pegar
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyautogui.hotkey('ctrl', 'c')
    time.sleep(0.1)
    
    import pyperclip
    texto = pyperclip.paste()
    # Limpiar "listo" y variantes
    texto_limpio = texto.lower().replace("listo", "").replace(".", "").strip()
    # Capitalizar primera letra si hay texto
    if texto_limpio:
        texto_limpio = texto_limpio[0].upper() + texto_limpio[1:] if len(texto_limpio) > 1 else texto_limpio.upper()
    
    pyperclip.copy(texto_limpio)
    pyautogui.hotkey('ctrl', 'v')
    
    modo_claudia = False
    print(f"📝 Texto: {texto_limpio}\n")

def on_cancela():
    global modo_claudia
    
    if not modo_claudia:
        return
    
    print("\n❌ 'Cancela' detectado!")
    
    # Soltar Ctrl+Win (Wispr pega)
    pyautogui.keyUp('win')
    pyautogui.keyUp('ctrl')
    time.sleep(0.5)  # Esperar a que Wispr pegue
    
    # Seleccionar todo y borrar
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyautogui.press('delete')
    
    modo_claudia = False
    print("🗑️ Texto borrado.\n")

def on_enter():
    print("\n⏎ 'Enter' detectado!")
    pyautogui.press('enter')
    print("✅ Enter pulsado\n")

def on_seleccion():
    print("\n📋 'Selección' detectado!")
    pyautogui.hotkey('ctrl', 'a')
    print("✅ Ctrl+A\n")

def on_eliminar():
    print("\n🗑️ 'Eliminar' detectado!")
    pyautogui.press('delete')
    print("✅ Delete pulsado\n")

def on_opcion(numero):
    print(f"\n🔢 'Opción {numero}' detectado!")
    pyautogui.press(str(numero))
    print(f"✅ Pulsado {numero}\n")

# ============================================
# NÚMEROS
# ============================================

NUMEROS = {
    "uno": 1, "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "cero": 0,
}

# ============================================
# AUDIO CALLBACK
# ============================================

def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"⚠️ {status}")
    q.put(bytes(indata))

# ============================================
# MAIN
# ============================================

def main():
    global modo_claudia
    
    print("=" * 50)
    print("🎤 Vosk + Wispr - Voice Control")
    print("=" * 50)
    
    # Cargar modelo
    print(f"Cargando modelo: {MODEL_PATH}...")
    try:
        model = Model(MODEL_PATH)
    except Exception as e:
        print(f"\n❌ No se encuentra el modelo: {MODEL_PATH}")
        return
    
    print("✅ Modelo cargado\n")
    
    # Configurar
    samplerate = 16000
    recognizer = KaldiRecognizer(model, samplerate)
    
    print("🎯 Comandos:")
    print("   'Claudia'     → VSCode + Chat + Wispr")
    print("   'Listo'       → Pega texto (en modo Claudia)")
    print("   'Cancela'     → Borra texto (en modo Claudia)")
    print("   'Enter'       → Pulsa Enter")
    print("   'Selección'   → Ctrl+A")
    print("   'Eliminar'    → Delete")
    print("   'Opción X'    → Pulsa número X")
    print("\n   Ctrl+C para salir")
    print("=" * 50)
    print("\n🎧 Escuchando...\n")
    
    with sd.RawInputStream(
        samplerate=samplerate,
        blocksize=8000,
        dtype='int16',
        channels=1,
        callback=audio_callback
    ):
        while True:
            data = q.get()
            
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").lower().strip()
                
                if not text:
                    continue
                
                # Mostrar lo reconocido
                if modo_claudia:
                    print(f"   🔍 (escuchado: {text})")
                else:
                    print(f"💬 {text}")
                
                # === MODO CLAUDIA: solo escucha listo/cancela ===
                if modo_claudia:
                    if "listo" in text:
                        on_listo()
                    elif "cancela" in text:
                        on_cancela()
                    # Ignorar todo lo demás en modo Claudia
                    continue
                
                # === MODO NORMAL ===
                
                # Claudia - activar
                if "claudia" in text:
                    on_claudia()
                    continue
                
                # Enter
                if text == "enter" or text == "énter":
                    on_enter()
                    continue
                
                # Selección
                if "selección" in text or "seleccion" in text:
                    on_seleccion()
                    continue
                
                # Eliminar
                if "eliminar" in text:
                    on_eliminar()
                    continue
                
                # Opción + número
                if "opción" in text or "opcion" in text:
                    for palabra, num in NUMEROS.items():
                        if palabra in text:
                            on_opcion(num)
                            break
                    continue

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Saliendo...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()