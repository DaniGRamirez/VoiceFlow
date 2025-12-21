import atexit
import re
import signal
import subprocess
import sys
import time

import pyautogui
import pyperclip

# Importar aliases para limpiar comandos del texto dictado
from config.aliases import (
    LISTO_ALIASES, CANCELA_ALIASES, ENVIAR_ALIASES, AYUDA_ALIASES
)

# Wake-words que pueden aparecer al inicio del comando y deben eliminarse
WAKE_WORDS = {"alexa", "hey jarvis", "jarvis", "oye", "hola"}

# Comandos que pueden aparecer al final del dictado y deben eliminarse
COMANDOS_DICTADO = set()
for aliases in [LISTO_ALIASES, CANCELA_ALIASES, ENVIAR_ALIASES, AYUDA_ALIASES]:
    COMANDOS_DICTADO.update(alias.lower() for alias in aliases)

# Añadir wake-words también a comandos (pueden aparecer al final)
COMANDOS_DICTADO.update(WAKE_WORDS)


def _limpiar_comandos_finales(texto: str, num_palabras: int = 5) -> str:
    """
    Elimina comandos de VoiceFlow y wake-words del texto dictado.

    - Wake-words al inicio (ej: "alexa listo" -> "listo")
    - Comandos al final (ej: "hola mundo listo" -> "hola mundo")

    Args:
        texto: El texto dictado
        num_palabras: Número de palabras finales a revisar

    Returns:
        Texto limpio sin comandos ni wake-words
    """
    if not texto:
        return texto

    # Separar en palabras
    palabras = texto.split()
    if not palabras:
        return texto

    # 1. Limpiar wake-words al INICIO
    while palabras:
        palabra_limpia = re.sub(r'[.,!?;:]', '', palabras[0].lower())
        if palabra_limpia in WAKE_WORDS:
            palabras.pop(0)
        else:
            break

    if not palabras:
        return ""

    # 2. Limpiar comandos al FINAL (últimas N palabras)
    inicio_revision = max(0, len(palabras) - num_palabras)
    palabras_finales = palabras[inicio_revision:]
    palabras_limpias = []

    for palabra in palabras_finales:
        # Limpiar puntuación para comparar
        palabra_limpia = re.sub(r'[.,!?;:]', '', palabra.lower())
        if palabra_limpia not in COMANDOS_DICTADO:
            palabras_limpias.append(palabra)

    # Reconstruir texto
    texto_limpio = ' '.join(palabras[:inicio_revision] + palabras_limpias)

    # Limpiar puntos finales que quedan huérfanos
    texto_limpio = re.sub(r'\s*[.,]+\s*$', '', texto_limpio).strip()

    return texto_limpio


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

# Instancia global para cleanup
_actions_instance = None


def _emergency_release():
    """Libera teclas al salir del programa"""
    if _actions_instance and _actions_instance._wispr_active:
        print("\n[SAFETY] Liberando teclas Ctrl+Win...")
        try:
            pyautogui.keyUp('win')
            pyautogui.keyUp('ctrl')
        except:
            pass


def _signal_handler(signum, frame):
    """Handler para señales de terminacion"""
    _emergency_release()
    sys.exit(0)


# Registrar handlers de señales
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)
if sys.platform == 'win32':
    signal.signal(signal.SIGBREAK, _signal_handler)


class Actions:
    def __init__(self, config: dict, debug_mode: bool = False, dictation_mode: str = "wispr"):
        global _actions_instance
        self.config = config
        self.debug_mode = debug_mode
        self.dictation_mode = dictation_mode  # "wispr" o "winh"
        self._wispr_active = False
        self._winh_active = False
        _actions_instance = self

        # Timings configurables
        timing = config.get("timing", {})
        self._vscode_focus_delay = timing.get("vscode_focus_delay", 0.3)
        self._chat_open_delay = timing.get("chat_open_delay", 0.5)
        self._dictation_release_delay = timing.get("dictation_release_delay", 0.5)
        self._clipboard_delay = timing.get("clipboard_delay", 0.1)
        self._key_delay = timing.get("key_delay", 0.1)

        # Ultima accion para comando "repetir"
        self._last_action = None

        # Registrar cleanup al salir
        atexit.register(_emergency_release)

    def _focus_vscode(self):
        """Enfoca la ventana de VSCode usando PowerShell"""
        ps_command = '''
$hwnd = (Get-Process | Where-Object { $_.MainWindowTitle -like "*Visual Studio Code*" } | Select-Object -First 1).MainWindowHandle
if ($hwnd) {
    Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class Win { [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd); }'
    [Win]::SetForegroundWindow($hwnd)
}
'''
        subprocess.run(['powershell', '-Command', ps_command], capture_output=True)

    def on_claudia(self):
        """Activa VSCode + Chat (sin Wispr)"""
        if self.debug_mode:
            print("[DEBUG] on_claudia: VSCode + Chat")
            return

        # Enfocar VSCode
        self._focus_vscode()
        time.sleep(self._vscode_focus_delay)

        # Abrir chat (hotkey configurable)
        hotkey = self.config.get("hotkeys", {}).get("vscode_chat", "ctrl+alt+shift+g")
        keys = hotkey.split("+")
        pyautogui.hotkey(*keys)

    def on_claudia_dictado(self, state_machine):
        """Activa VSCode + Chat + Dictado automaticamente"""
        from core.state import State

        if self.debug_mode:
            print("[DEBUG] on_claudia_dictado: VSCode + Chat + Dictado")
            state_machine.transition(State.DICTATING)
            return

        # Enfocar VSCode
        self._focus_vscode()
        time.sleep(self._vscode_focus_delay)

        # Abrir chat (hotkey configurable)
        hotkey = self.config.get("hotkeys", {}).get("vscode_chat", "ctrl+alt+shift+g")
        keys = hotkey.split("+")
        pyautogui.hotkey(*keys)

        # Esperar a que se abra el chat y activar dictado
        time.sleep(self._chat_open_delay)
        state_machine.transition(State.DICTATING)
        self.on_dictado()

    def on_dictado(self):
        """Activa dictado segun el modo configurado"""
        if self.dictation_mode == "winh":
            self._on_dictado_winh()
        else:
            self._on_dictado_wispr()

    def _on_dictado_wispr(self):
        """Activa Wispr (Ctrl+Win down)"""
        if self._wispr_active:
            return  # Ya esta activo

        if self.debug_mode:
            print("[DEBUG] on_dictado: Wispr activado (simulado)")
            self._wispr_active = True
            return

        # Limpiar portapapeles para evitar que Wispr concatene con texto anterior
        try:
            pyperclip.copy("")
        except Exception:
            pass

        pyautogui.keyDown('ctrl')
        pyautogui.keyDown('win')
        self._wispr_active = True

    def _on_dictado_winh(self):
        """Activa dictado de Windows (Win+H)"""
        if self._winh_active:
            return  # Ya esta activo

        if self.debug_mode:
            print("[DEBUG] on_dictado: Win+H activado (simulado)")
            self._winh_active = True
            return

        pyautogui.hotkey('win', 'h')
        self._winh_active = True

    def on_listo(self):
        """Termina dictado segun el modo configurado"""
        if self.dictation_mode == "winh":
            self._on_listo_winh()
        else:
            self._on_listo_wispr()

    def _on_listo_wispr(self):
        """Suelta Wispr y limpia el texto"""
        if not self._wispr_active:
            return

        if self.debug_mode:
            print("[DEBUG] on_listo: Wispr desactivado (simulado)")
            self._wispr_active = False
            return

        # Soltar Ctrl+Win (Wispr pega automaticamente)
        pyautogui.keyUp('win')
        pyautogui.keyUp('ctrl')
        time.sleep(self._dictation_release_delay)

        # Seleccionar y copiar texto actual
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(self._clipboard_delay)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(self._clipboard_delay)

        texto = pyperclip.paste()

        # Limpiar comandos de las últimas 5 palabras
        texto_limpio = _limpiar_comandos_finales(texto, num_palabras=5)

        # Capitalizar primera letra si hay texto
        if texto_limpio:
            texto_limpio = texto_limpio[0].upper() + texto_limpio[1:] if len(texto_limpio) > 1 else texto_limpio.upper()

        pyperclip.copy(texto_limpio)
        pyautogui.hotkey('ctrl', 'v')
        self._wispr_active = False

    def _on_listo_winh(self):
        """Termina dictado Win+H y limpia comandos del texto"""
        if not self._winh_active:
            return

        if self.debug_mode:
            print("[DEBUG] on_listo: Win+H desactivado (simulado)")
            self._winh_active = False
            return

        # Detener dictado de Windows
        pyautogui.press('escape')
        time.sleep(self._dictation_release_delay)

        # Seleccionar y copiar texto actual
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(self._clipboard_delay)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(self._clipboard_delay)

        texto = pyperclip.paste()

        # Limpiar comandos de las últimas 5 palabras
        texto_limpio = _limpiar_comandos_finales(texto, num_palabras=5)

        # Capitalizar primera letra si hay texto
        if texto_limpio:
            texto_limpio = texto_limpio[0].upper() + texto_limpio[1:] if len(texto_limpio) > 1 else texto_limpio.upper()

        pyperclip.copy(texto_limpio)
        pyautogui.hotkey('ctrl', 'v')
        self._winh_active = False

    def on_cancela(self):
        """Cancela dictado segun el modo configurado"""
        if self.dictation_mode == "winh":
            self._on_cancela_winh()
        else:
            self._on_cancela_wispr()

    def _on_cancela_wispr(self):
        """Suelta Wispr y borra todo"""
        if not self._wispr_active:
            return

        if self.debug_mode:
            print("[DEBUG] on_cancela: Wispr cancelado (simulado)")
            self._wispr_active = False
            return

        # Soltar Ctrl+Win
        pyautogui.keyUp('win')
        pyautogui.keyUp('ctrl')
        time.sleep(self._dictation_release_delay)

        # Seleccionar todo y borrar
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(self._key_delay)
        pyautogui.press('delete')
        self._wispr_active = False

    def _on_cancela_winh(self):
        """Cancela dictado Win+H y borra"""
        if not self._winh_active:
            return

        if self.debug_mode:
            print("[DEBUG] on_cancela: Win+H cancelado (simulado)")
            self._winh_active = False
            return

        # Detener dictado de Windows
        pyautogui.press('escape')
        time.sleep(self._key_delay)

        # Seleccionar todo y borrar
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(self._key_delay)
        pyautogui.press('delete')
        self._winh_active = False

    def on_enter(self):
        """Pulsa Enter"""
        pyautogui.press('enter')
        self._last_action = self.on_enter

    def on_seleccion(self):
        """Ctrl+A"""
        pyautogui.hotkey('ctrl', 'a')
        self._last_action = self.on_seleccion

    def on_eliminar(self):
        """Pulsa Delete"""
        pyautogui.press('delete')
        self._last_action = self.on_eliminar

    def on_borra_todo(self):
        """Selecciona todo y borra (Ctrl+A + Delete)"""
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(self._key_delay)
        pyautogui.press('delete')
        self._last_action = self.on_borra_todo

    def on_ayuda(self, state, registry, overlay=None):
        """Muestra comandos disponibles en el estado actual"""
        from core.state import State

        # Descripciones de comandos (user-friendly)
        descriptions = {
            "claudia": "Abre chat de Claude en VSCode",
            "claudia dictado": "Abre Claude y empieza a dictar",
            "dictado": "Empieza a dictar texto",
            "listo": "Termina y envía el dictado",
            "cancela": "Cancela sin enviar",
            "enviar": "Envía el mensaje",
            "enter": "Confirma / nueva línea",
            "seleccion": "Selecciona todo el texto",
            "eliminar": "Borra lo seleccionado",
            "borra todo": "Borra todo el texto",
            "escape": "Cierra o cancela",
            "tab": "Salta al siguiente campo",
            "aceptar": "Acepta la opción",
            "copiar": "Copia al portapapeles",
            "pegar": "Pega del portapapeles",
            "deshacer": "Deshace el último cambio",
            "rehacer": "Rehace lo deshecho",
            "guardar": "Guarda el archivo",
            "arriba": "Mueve hacia arriba",
            "abajo": "Mueve hacia abajo",
            "izquierda": "Mueve a la izquierda",
            "derecha": "Mueve a la derecha",
            "inicio": "Va al principio",
            "fin": "Va al final",
            "repetir": "Repite el último comando",
            "ayuda": "Muestra esta ayuda",
            "pausa": "Pausa el reconocimiento",
            "reanuda": "Reanuda el reconocimiento",
            "reiniciar": "Reinicia VoiceFlow",
        }

        # Recopilar comandos disponibles
        commands = []
        seen = set()
        for cmd in registry._commands:
            if state in cmd.allowed_states:
                keyword = cmd.keywords[0]
                if keyword not in seen:
                    seen.add(keyword)
                    desc = descriptions.get(keyword, "")
                    commands.append((keyword, desc))

        # Mostrar en overlay si está disponible
        if overlay:
            overlay.show_help(commands)
        else:
            # Fallback a consola
            state_names = {
                State.IDLE: "IDLE",
                State.DICTATING: "DICTANDO",
                State.PROCESSING: "PROCESANDO"
            }
            print(f"\n{'=' * 40}")
            print(f"  Comandos disponibles ({state_names.get(state, 'UNKNOWN')})")
            print(f"{'=' * 40}")
            for kw, desc in commands:
                print(f"  '{kw}' - {desc}")
            print(f"{'=' * 40}\n")

    def on_opcion(self, numero: int):
        """Pulsa un numero"""
        pyautogui.press(str(numero))

    def on_escape(self):
        """Pulsa Escape"""
        pyautogui.press('escape')
        self._last_action = self.on_escape

    def on_tab(self):
        """Pulsa Tab"""
        pyautogui.press('tab')
        self._last_action = self.on_tab

    def on_copiar(self):
        """Ctrl+C"""
        pyautogui.hotkey('ctrl', 'c')
        self._last_action = self.on_copiar

    def on_pegar(self):
        """Ctrl+V"""
        pyautogui.hotkey('ctrl', 'v')
        self._last_action = self.on_pegar

    def on_deshacer(self):
        """Ctrl+Z"""
        pyautogui.hotkey('ctrl', 'z')
        self._last_action = self.on_deshacer

    def on_rehacer(self):
        """Ctrl+Y"""
        pyautogui.hotkey('ctrl', 'y')
        self._last_action = self.on_rehacer

    def on_guardar(self):
        """Ctrl+S"""
        pyautogui.hotkey('ctrl', 's')
        self._last_action = self.on_guardar

    def on_flecha(self, direccion: str):
        """Pulsa una flecha de direccion"""
        pyautogui.press(direccion)
        self._last_action = lambda: self.on_flecha(direccion)

    def on_inicio(self):
        """Pulsa Home"""
        pyautogui.press('home')
        self._last_action = self.on_inicio

    def on_fin(self):
        """Pulsa End"""
        pyautogui.press('end')
        self._last_action = self.on_fin

    def on_repetir(self):
        """Repite la ultima accion"""
        if self._last_action:
            self._last_action()
        else:
            print("[INFO] No hay acción anterior para repetir")

    def on_pausa(self):
        """Pausa el reconocimiento de comandos"""
        if self.debug_mode:
            print("[DEBUG] on_pausa: Sistema pausado")

    def on_reanuda(self):
        """Reanuda el reconocimiento de comandos"""
        if self.debug_mode:
            print("[DEBUG] on_reanuda: Sistema reanudado")

    def on_enviar(self, state_machine):
        """Termina dictado y pulsa Enter (listo + enter)"""
        from core.state import State

        # Primero terminar dictado
        self.on_listo()
        state_machine.transition(State.IDLE)

        # Luego pulsar enter
        time.sleep(self._key_delay)
        pyautogui.press('enter')

    def release_keys(self):
        """Libera todas las teclas - llamar en caso de emergencia"""
        if self._wispr_active:
            pyautogui.keyUp('win')
            pyautogui.keyUp('ctrl')
            self._wispr_active = False
            print("[SAFETY] Teclas Wispr liberadas")
        if self._winh_active:
            pyautogui.press('escape')
            self._winh_active = False
            print("[SAFETY] Win+H cerrado")

    def on_reiniciar(self):
        """Reinicia la aplicación"""
        import os
        print("[INFO] Reiniciando VoiceFlow...")
        self.release_keys()
        # Lanzar nuevo proceso y salir del actual
        python = sys.executable
        script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        # Pasar los mismos argumentos
        args = [python, script] + sys.argv[1:]
        subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0)
        # Salir del proceso actual
        os._exit(0)

    # ========== NOTIFICACIONES DE CLAUDE CODE ==========

    def execute_notification_intent(self, action: dict) -> bool:
        """
        Ejecuta una acción de notificación en VS Code.

        El sistema se adapta a cualquier tipo de notificación:
        la notificación define sus propias acciones con hotkeys,
        y este método ejecuta el hotkey correspondiente.

        Args:
            action: Dict con:
                - id: Identificador de la acción (ej: "accept", "cancel", "option_1")
                - hotkey: Tecla o combinación a presionar (ej: "enter", "escape", "ctrl+enter")
                - label: Etiqueta de la acción (para logging)

        Returns:
            True si se ejecutó correctamente
        """
        action_id = action.get("id", "unknown")
        hotkey = action.get("hotkey", "enter")
        label = action.get("label", action_id)

        print(f"[Actions] Ejecutando intent: {label} (hotkey: {hotkey})")

        try:
            # 1. Enfocar VS Code
            self._focus_vscode()
            time.sleep(0.2)

            # 2. Ejecutar hotkey
            if "+" in hotkey:
                # Combinación de teclas (ej: "ctrl+enter", "alt+1")
                keys = hotkey.split("+")
                pyautogui.hotkey(*keys)
            else:
                # Tecla simple (ej: "enter", "escape", "1", "2", "tab")
                pyautogui.press(hotkey)

            print(f"[Actions] Intent ejecutado: {label}")
            return True

        except Exception as e:
            print(f"[Actions] Error ejecutando intent {label}: {e}")
            return False
