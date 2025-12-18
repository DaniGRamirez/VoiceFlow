import atexit
import signal
import subprocess
import sys
import time

import pyautogui
import pyperclip


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

        # Limpiar "listo" del texto
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(self._clipboard_delay)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(self._clipboard_delay)

        texto = pyperclip.paste()
        texto_limpio = texto.lower().replace("listo", "").replace(".", "").strip()
        if texto_limpio:
            texto_limpio = texto_limpio[0].upper() + texto_limpio[1:] if len(texto_limpio) > 1 else texto_limpio.upper()

        pyperclip.copy(texto_limpio)
        pyautogui.hotkey('ctrl', 'v')
        self._wispr_active = False

    def _on_listo_winh(self):
        """Termina dictado Win+H"""
        if not self._winh_active:
            return

        if self.debug_mode:
            print("[DEBUG] on_listo: Win+H desactivado (simulado)")
            self._winh_active = False
            return

        # Detener dictado de Windows (Escape o Win+H de nuevo)
        pyautogui.press('escape')
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

    def on_ayuda(self, state, registry):
        """Muestra comandos disponibles en el estado actual"""
        from core.state import State

        state_names = {
            State.IDLE: "IDLE",
            State.DICTATING: "DICTANDO",
            State.PROCESSING: "PROCESANDO"
        }

        print(f"\n{'=' * 40}")
        print(f"  Comandos disponibles ({state_names.get(state, 'UNKNOWN')})")
        print(f"{'=' * 40}")

        for cmd in registry._commands:
            if state in cmd.allowed_states:
                keywords = ", ".join(cmd.keywords)
                print(f"  '{keywords}'")

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
