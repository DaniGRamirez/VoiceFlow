"""
Claude Voice Trigger - CLAUDIA + JARVIS
==========================================
Usa dos instancias de Porcupine:
- Español: "Claudia" (activar)
- Inglés: "jarvis" (enviar)

pip install pvporcupine pvrecorder pyautogui
"""
import time
import os

# ============================================
# CONFIGURACIÓN
# ============================================
ACCESS_KEY = "TU_API_KEY_AQUI"  # Obtener en https://console.picovoice.ai/

# Archivos
CLAUDIA_PPN = r"C:\Users\danig\Downloads\voice\Claudia_es_windows_v4_0_0.ppn"
SPANISH_MODEL = r"C:\Users\danig\Downloads\voice\porcupine_params_es.pv"

SENSITIVITY = 0.7

# Estado global
wispr_active = False
running = True

# ============================================
# ACCIONES
# ============================================
def on_claudia():
    global wispr_active
    print("🎤 'Claudia' detectado!")
    
    import subprocess
    import pyautogui
    
    # Abrir Notepad
    subprocess.Popen(['notepad.exe'])
    time.sleep(0.5)
    
    # Mantener pulsado Ctrl+Win (Wispr escucha)
    pyautogui.keyDown('ctrl')
    pyautogui.keyDown('win')
    wispr_active = True
    
    print("✅ Wispr escuchando...")
    print("   Di 'jarvis' para enviar")

def on_jarvis():
    global wispr_active
    
    if not wispr_active:
        print("⚠️ Di 'Claudia' primero")
        return
    
    print("📤 'Jarvis' detectado! Enviando...")
    
    import pyautogui
    
    # Soltar Ctrl+Win (Wispr pega automáticamente)
    pyautogui.keyUp('win')
    pyautogui.keyUp('ctrl')
    
    wispr_active = False
    print("✅ Enviado!")

# ============================================
# MAIN
# ============================================
def main():
    global running
    
    print("=" * 50)
    print("Claude Voice Trigger")
    print("=" * 50)
    
    # Verificar archivos
    if not os.path.exists(CLAUDIA_PPN):
        print(f"❌ No se encuentra: {CLAUDIA_PPN}")
        return
    print(f"✅ Claudia.ppn OK")
    
    if not os.path.exists(SPANISH_MODEL):
        print(f"❌ No se encuentra: {SPANISH_MODEL}")
        return
    print(f"✅ Modelo español OK")
    
    import pvporcupine
    from pvrecorder import PvRecorder
    
    porcupine_es = None
    porcupine_en = None
    recorder = None
    
    try:
        # Porcupine ESPAÑOL para "Claudia"
        porcupine_es = pvporcupine.create(
            access_key=ACCESS_KEY,
            model_path=SPANISH_MODEL,
            keyword_paths=[CLAUDIA_PPN],
            sensitivities=[SENSITIVITY]
        )
        print("✅ Porcupine español (Claudia)")
        
        # Porcupine INGLÉS para "jarvis" (built-in, gratis)
        porcupine_en = pvporcupine.create(
            access_key=ACCESS_KEY,
            keywords=["jarvis"],
            sensitivities=[SENSITIVITY]
        )
        print("✅ Porcupine inglés (jarvis)")
        
        # Verificar que ambos tienen el mismo frame_length
        if porcupine_es.frame_length != porcupine_en.frame_length:
            print("⚠️ Frame lengths diferentes, usando el mayor")
        
        frame_length = max(porcupine_es.frame_length, porcupine_en.frame_length)
        
        # Recorder
        recorder = PvRecorder(
            device_index=-1,
            frame_length=frame_length
        )
        recorder.start()
        print("✅ Micrófono activo")
        
        print("\n" + "=" * 50)
        print("🎧 ESCUCHANDO...")
        print("   'Claudia' → Activa Notepad + Wispr")
        print("   'Jarvis'  → Envía")
        print("   Ctrl+C para salir")
        print("=" * 50 + "\n")
        
        while running:
            pcm = recorder.read()
            
            # Procesar español
            result_es = porcupine_es.process(pcm)
            if result_es >= 0:
                on_claudia()
            
            # Procesar inglés
            result_en = porcupine_en.process(pcm)
            if result_en >= 0:
                on_jarvis()
                
    except pvporcupine.PorcupineActivationError:
        print("❌ API KEY INVÁLIDA")
        
    except pvporcupine.PorcupineInvalidArgumentError as e:
        print(f"❌ Error: {e}")
        
    except KeyboardInterrupt:
        print("\n👋 Saliendo...")
        running = False
        
    finally:
        if recorder:
            recorder.delete()
        if porcupine_es:
            porcupine_es.delete()
        if porcupine_en:
            porcupine_en.delete()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
    
    input("\nPresiona Enter para cerrar...")