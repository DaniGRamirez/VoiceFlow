"""
ActionExecutor - Ejecuta pipelines de acciones declarativas.

Convierte definiciones JSON en acciones reales usando pyautogui, subprocess, etc.
Soporta interpolación de variables y permisos para acciones peligrosas.
"""

import json
import os
import shlex
import subprocess
import time
import webbrowser
from datetime import datetime, date
from typing import Optional, Callable

import pyautogui
import pyperclip

from config.settings import BASE_DIR

# Import lazy para evitar error si playwright no está instalado
BrowserActionExecutor = None


def _get_browser_executor():
    """Lazy import del BrowserActionExecutor."""
    global BrowserActionExecutor
    if BrowserActionExecutor is None:
        try:
            from core.browser import BrowserActionExecutor as BAE
            BrowserActionExecutor = BAE
        except ImportError:
            print("[ActionExecutor] Módulo browser no disponible")
            return None
    return BrowserActionExecutor


class ActionExecutor:
    """
    Ejecuta pipelines de acciones declarativas con logs y timeouts.

    Acciones Tier 1 (seguras):
        key, hotkey, type, wait, open, clipboard, sound, notify

    Acciones Tier 2 (requieren permiso):
        shell, run, script
    """

    # Acciones que requieren permiso especial
    DANGEROUS_ACTIONS = {"shell", "run", "script"}

    def __init__(self, allow_dangerous: bool = False,
                 sound_player: Optional[Callable] = None,
                 overlay: Optional[object] = None):
        """
        Args:
            allow_dangerous: Si True, permite shell/run/script
            sound_player: Función para reproducir sonidos (sound_player.play)
            overlay: Overlay para mostrar notificaciones
        """
        self.allow_dangerous = allow_dangerous
        self.sound_player = sound_player
        self.overlay = overlay

    def execute_pipeline(self, actions: list, command_name: str = "custom") -> bool:
        """
        Ejecuta lista de acciones en orden.

        Args:
            actions: Lista de dicts con definición de acciones
            command_name: Nombre del comando (para logs)

        Returns:
            True si todas las acciones se ejecutaron OK
        """
        for i, action in enumerate(actions):
            action_type = action.get("type", "unknown")
            try:
                print(f"[Custom] {command_name} - paso {i+1}: {action_type}")
                self._execute_one(action)
            except PermissionError as e:
                print(f"[Custom] PERMISO DENEGADO en paso {i+1}: {e}")
                return False
            except subprocess.TimeoutExpired:
                print(f"[Custom] TIMEOUT en paso {i+1}: {action_type}")
                return False
            except Exception as e:
                print(f"[Custom] ERROR en paso {i+1}: {e}")
                return False
        return True

    def _execute_one(self, action: dict):
        """Ejecuta una sola acción."""
        action_type = action.get("type")

        # Verificar permisos para acciones peligrosas
        if action_type in self.DANGEROUS_ACTIONS and not self.allow_dangerous:
            raise PermissionError(
                f"Acción '{action_type}' requiere allow_dangerous_actions=true en config"
            )

        # Interpolar variables en campos de texto
        action = self._interpolate_vars(action)

        # Ejecutar según tipo
        if action_type == "key":
            pyautogui.press(action["key"])

        elif action_type == "hotkey":
            pyautogui.hotkey(*action["keys"])

        elif action_type == "type":
            # interval para que no sea demasiado rápido
            pyautogui.write(action["text"], interval=0.02)

        elif action_type == "wait":
            time.sleep(action.get("seconds", 0.5))

        elif action_type == "open":
            webbrowser.open(action["path"])

        elif action_type == "clipboard":
            pyperclip.copy(action["text"])

        elif action_type == "sound":
            if self.sound_player:
                self.sound_player.play(action.get("name", "ding"))

        elif action_type == "notify":
            if self.overlay:
                self.overlay.show_text(action.get("text", ""), is_command=True)

        elif action_type == "shell":
            timeout = action.get("timeout", 10)
            cmd = action["cmd"]
            # Usar shlex.split para evitar shell injection (solo en comandos simples)
            # Si el comando requiere shell features (pipes, redirects), usar cmd /c
            if any(c in cmd for c in ['|', '>', '<', '&&', '||']):
                # Comando con shell features - ejecutar via cmd
                cmd_parts = ["cmd", "/c", cmd]
            else:
                # Comando simple - parsear argumentos de forma segura
                cmd_parts = shlex.split(cmd, posix=False)  # posix=False para Windows

            result = subprocess.run(
                cmd_parts,
                shell=False,
                capture_output=True,
                timeout=timeout,
                text=True
            )
            if result.returncode != 0:
                print(f"[Shell] stderr: {result.stderr}")
            if result.stdout:
                print(f"[Shell] stdout: {result.stdout}")

        elif action_type == "run":
            args = action.get("args", [])
            program = action["program"]
            subprocess.Popen([program] + args, shell=False)

        elif action_type == "script":
            # Out-of-process para seguridad
            timeout = action.get("timeout", 30)
            script_path = action["path"]
            use_terminal = action.get("terminal", False)

            if use_terminal:
                # Abrir en terminal separada (Windows)
                # Convertir a ruta absoluta
                if not os.path.isabs(script_path):
                    script_path = os.path.join(BASE_DIR, script_path)
                print(f"[Script] Abriendo terminal: {script_path}")
                subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", "python", script_path])
            else:
                result = subprocess.run(
                    ["python", script_path],
                    timeout=timeout,
                    capture_output=True,
                    text=True
                )
                if result.stdout:
                    print(result.stdout.rstrip())
                if result.stderr:
                    print(f"[Script] stderr: {result.stderr}")

        elif action_type == "prompt":
            # Carga plantilla JSON y sustituye {user_msg} con clipboard
            template_path = action["template"]
            if not os.path.isabs(template_path):
                template_path = os.path.join(BASE_DIR, template_path)

            with open(template_path, 'r', encoding='utf-8') as f:
                template = json.load(f)

            # Obtener el prompt
            prompt_text = template.get("prompt", "")
            user_content = pyperclip.paste() or ""

            # Detectar si el clipboard ya contiene este prompt (evitar anidamiento)
            # Buscamos el marcador que separa el template del user_msg
            user_msg_marker = "{user_msg}"
            if user_msg_marker in prompt_text:
                # Obtener la parte del template ANTES del {user_msg}
                template_prefix = prompt_text.split(user_msg_marker)[0]

                # Si el clipboard empieza con el template, extraer solo el user_msg original
                if template_prefix and user_content.startswith(template_prefix[:50]):
                    # Extraer el texto después del marcador del template
                    # El user_msg está después de la última línea del template
                    template_suffix_marker = prompt_text.split(user_msg_marker)[0].rstrip()
                    if template_suffix_marker in user_content:
                        # Encontrar dónde termina el template y empieza el user_msg
                        idx = user_content.find(template_suffix_marker) + len(template_suffix_marker)
                        user_content = user_content[idx:].strip()
                        print(f"[Prompt] Detectado prompt anidado, extrayendo user_msg original...")

            print(f"[Prompt] Clipboard input ({len(user_content)} chars): {user_content[:80]}...")
            final_prompt = prompt_text.replace("{user_msg}", user_content)

            # Copiar al portapapeles
            pyperclip.copy(final_prompt)
            print(f"[Prompt] Template '{template.get('name', 'unknown')}' -> clipboard ({len(final_prompt)} chars)")

        elif action_type == "browser":
            # Acciones de navegador via Playwright CDP
            BAE = _get_browser_executor()
            if BAE is None:
                raise RuntimeError("Playwright no instalado. Ejecuta: pip install playwright && playwright install chromium")
            executor = BAE()
            browser_actions = action.get("actions", [])
            if not executor.execute(browser_actions, command_name="browser"):
                # Usar mensaje de error específico si existe
                error_msg = executor.last_error or "Falló la ejecución de acciones browser"
                raise RuntimeError(error_msg)

        elif action_type == "tts":
            # Text-to-Speech via provider web
            from config.tts import get_provider
            BAE = _get_browser_executor()
            if BAE is None:
                raise RuntimeError("Playwright no instalado para TTS")

            provider_name = action.get("provider", None)
            tts_action = action.get("tts_action", "speak")  # speak, pause, resume, stop

            provider = get_provider(provider_name)
            if not provider:
                raise ValueError(f"Provider TTS no encontrado: {provider_name}")

            browser_actions = provider["actions"].get(tts_action, [])
            if not browser_actions:
                raise ValueError(f"Acción '{tts_action}' no disponible en provider {provider['name']}")

            print(f"[TTS] {provider['name']} -> {tts_action}")
            executor = BAE()
            if not executor.execute(browser_actions, command_name=f"tts-{tts_action}"):
                raise RuntimeError(f"Falló TTS {tts_action}")

        else:
            raise ValueError(f"Acción desconocida: {action_type}")

    def _interpolate_vars(self, action: dict) -> dict:
        """
        Reemplaza variables en campos de texto.

        Variables soportadas:
            {clipboard} - Contenido del portapapeles
            {date} - Fecha actual (YYYY-MM-DD)
            {time} - Hora actual (HH:MM)
        """
        variables = {
            "clipboard": pyperclip.paste() or "",
            "date": date.today().isoformat(),
            "time": datetime.now().strftime("%H:%M"),
        }

        result = action.copy()
        for key, value in result.items():
            if isinstance(value, str):
                for var_name, var_value in variables.items():
                    value = value.replace(f"{{{var_name}}}", str(var_value))
                result[key] = value
        return result
