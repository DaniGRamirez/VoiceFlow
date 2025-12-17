import subprocess
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


class Actions:
    def __init__(self, config: dict):
        self.config = config
        self._wispr_active = False

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
        """Activa VSCode + Chat + Wispr"""
        # Enfocar VSCode
        self._focus_vscode()
        time.sleep(0.3)

        # Abrir chat (hotkey configurable)
        hotkey = self.config.get("hotkeys", {}).get("vscode_chat", "ctrl+alt+shift+g")
        keys = hotkey.split("+")
        pyautogui.hotkey(*keys)
        time.sleep(0.3)

        # Wispr escucha (mantener Ctrl+Win)
        pyautogui.keyDown('ctrl')
        pyautogui.keyDown('win')
        self._wispr_active = True

    def on_listo(self):
        """Suelta Wispr y limpia el texto"""
        if not self._wispr_active:
            return

        # Soltar Ctrl+Win (Wispr pega automaticamente)
        pyautogui.keyUp('win')
        pyautogui.keyUp('ctrl')
        time.sleep(0.5)

        # Limpiar "listo" del texto
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.1)

        texto = pyperclip.paste()
        texto_limpio = texto.lower().replace("listo", "").replace(".", "").strip()
        if texto_limpio:
            texto_limpio = texto_limpio[0].upper() + texto_limpio[1:] if len(texto_limpio) > 1 else texto_limpio.upper()

        pyperclip.copy(texto_limpio)
        pyautogui.hotkey('ctrl', 'v')
        self._wispr_active = False

    def on_cancela(self):
        """Suelta Wispr y borra todo"""
        if not self._wispr_active:
            return

        # Soltar Ctrl+Win
        pyautogui.keyUp('win')
        pyautogui.keyUp('ctrl')
        time.sleep(0.5)

        # Seleccionar todo y borrar
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.press('delete')
        self._wispr_active = False

    def on_enter(self):
        """Pulsa Enter"""
        pyautogui.press('enter')

    def on_seleccion(self):
        """Ctrl+A"""
        pyautogui.hotkey('ctrl', 'a')

    def on_eliminar(self):
        """Pulsa Delete"""
        pyautogui.press('delete')

    def on_opcion(self, numero: int):
        """Pulsa un numero"""
        pyautogui.press(str(numero))
