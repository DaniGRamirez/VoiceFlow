"""
ActionExecutor - Ejecuta pipelines de acciones declarativas.

Convierte definiciones JSON en acciones reales usando pyautogui, subprocess, etc.
Soporta interpolación de variables, permisos para acciones peligrosas,
y un sistema de contexto para comunicación entre acciones en un pipeline.
"""

import json
import os
import re
import shlex
import subprocess
import time
import webbrowser
from datetime import datetime, date
from typing import Optional, Callable, Any

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
        set, transform, condition (nuevas acciones de contexto)

    Acciones Tier 2 (requieren permiso):
        shell, run, script

    Sistema de Contexto:
        Las acciones pueden comunicarse a través de un contexto compartido.
        - Cualquier acción puede leer variables con {variable_name}
        - Acciones con "output" guardan su resultado en el contexto
        - Variables predefinidas: clipboard, date, time, timestamp
    """

    # Acciones que requieren permiso especial
    DANGEROUS_ACTIONS = {"shell", "run", "script"}

    # Operaciones disponibles para transform
    TRANSFORM_OPERATIONS = {
        "upper": lambda s: s.upper(),
        "lower": lambda s: s.lower(),
        "trim": lambda s: s.strip(),
        "title": lambda s: s.title(),
        "reverse": lambda s: s[::-1],
        "length": lambda s: str(len(s)),
        "lines": lambda s: str(s.count('\n') + 1),
        "words": lambda s: str(len(s.split())),
    }

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

    def execute_pipeline(self, actions: list, command_name: str = "custom",
                         initial_context: Optional[dict] = None) -> bool:
        """
        Ejecuta lista de acciones en orden con contexto compartido.

        Args:
            actions: Lista de dicts con definición de acciones
            command_name: Nombre del comando (para logs)
            initial_context: Contexto inicial opcional (para tests o encadenamiento)

        Returns:
            True si todas las acciones se ejecutaron OK
        """
        # Inicializar contexto con variables predefinidas
        context = self._create_initial_context(initial_context)

        for i, action in enumerate(actions):
            action_type = action.get("type", "unknown")
            try:
                print(f"[Custom] {command_name} - paso {i+1}: {action_type}")

                # Interpolar variables del contexto
                interpolated_action = self._interpolate_vars(action, context)

                # Ejecutar acción y obtener resultado
                result = self._execute_one(interpolated_action, context)

                # Si la acción define "output", guardar resultado en contexto
                output_var = action.get("output")
                if output_var and result is not None:
                    context[output_var] = str(result)
                    print(f"[Context] {output_var} = {str(result)[:50]}...")

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

    def _create_initial_context(self, initial: Optional[dict] = None) -> dict:
        """Crea el contexto inicial con variables predefinidas."""
        context = {
            "clipboard": pyperclip.paste() or "",
            "date": date.today().isoformat(),
            "time": datetime.now().strftime("%H:%M"),
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        }
        if initial:
            context.update(initial)
        return context

    def get_context(self) -> dict:
        """Retorna una copia del contexto actual (para debugging)."""
        return self._create_initial_context()

    def _execute_one(self, action: dict, context: dict) -> Optional[Any]:
        """
        Ejecuta una sola acción.

        Args:
            action: Definición de la acción (ya interpolada)
            context: Contexto compartido del pipeline

        Returns:
            Resultado de la acción (para guardar en context si hay "output")
        """
        action_type = action.get("type")

        # Verificar permisos para acciones peligrosas
        if action_type in self.DANGEROUS_ACTIONS and not self.allow_dangerous:
            raise PermissionError(
                f"Acción '{action_type}' requiere allow_dangerous_actions=true en config"
            )

        # ========== NUEVAS ACCIONES DE CONTEXTO ==========

        if action_type == "set":
            # Guardar valor en contexto
            var_name = action.get("var")
            value = action.get("value", "")
            if var_name:
                context[var_name] = value
            return value

        elif action_type == "transform":
            # Transformar texto
            return self._execute_transform(action, context)

        elif action_type == "condition":
            # Ejecución condicional
            return self._execute_condition(action, context)

        elif action_type == "capture_clipboard":
            # Capturar clipboard actual (útil después de Ctrl+C)
            return pyperclip.paste() or ""

        elif action_type == "log":
            # Debug: mostrar valor en consola
            message = action.get("message", "")
            print(f"[Log] {message}")
            return message

        # ========== ACCIONES EXISTENTES ==========

        elif action_type == "key":
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

            # Convertir a ruta absoluta y validar path traversal
            if not os.path.isabs(script_path):
                script_path = os.path.join(BASE_DIR, script_path)
            script_path = os.path.realpath(script_path)
            base_dir_real = os.path.realpath(BASE_DIR)
            if not script_path.startswith(base_dir_real):
                raise ValueError(f"Path traversal detectado en script: {action['path']}")

            if use_terminal:
                # Abrir en terminal separada (Windows)
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

            # Validar path traversal
            template_path = os.path.realpath(template_path)
            base_dir_real = os.path.realpath(BASE_DIR)
            if not template_path.startswith(base_dir_real):
                raise ValueError(f"Path traversal detectado en template: {action['template']}")

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

        return None  # Acciones sin output explícito

    def _interpolate_vars(self, action: dict, context: dict) -> dict:
        """
        Reemplaza variables en campos de texto usando el contexto.

        Variables soportadas:
            {variable_name} - Cualquier variable del contexto
            Variables predefinidas: clipboard, date, time, timestamp
        """
        result = action.copy()
        for key, value in result.items():
            if isinstance(value, str):
                # Reemplazar todas las variables del contexto
                for var_name, var_value in context.items():
                    value = value.replace(f"{{{var_name}}}", str(var_value))
                result[key] = value
            elif isinstance(value, list):
                # También interpolar en listas (para "keys" en hotkey, etc.)
                result[key] = [
                    self._interpolate_string(item, context) if isinstance(item, str) else item
                    for item in value
                ]
        return result

    def _interpolate_string(self, text: str, context: dict) -> str:
        """Interpola variables en un string individual."""
        for var_name, var_value in context.items():
            text = text.replace(f"{{{var_name}}}", str(var_value))
        return text

    def _execute_transform(self, action: dict, context: dict) -> str:
        """
        Ejecuta una transformación de texto.

        Soporta:
            - Operaciones simples: upper, lower, trim, title, reverse, length
            - Operaciones con parámetros: replace:old:new, prefix:text, suffix:text
            - Operaciones regex: regex:pattern:replacement
        """
        input_text = action.get("input", "")
        operation = action.get("operation", "")

        # Operaciones simples (sin parámetros)
        if operation in self.TRANSFORM_OPERATIONS:
            return self.TRANSFORM_OPERATIONS[operation](input_text)

        # Operaciones con parámetros (formato: operation:param1:param2)
        if ":" in operation:
            parts = operation.split(":", 2)
            op_name = parts[0]

            if op_name == "replace" and len(parts) >= 3:
                old_text = parts[1]
                new_text = parts[2] if len(parts) > 2 else ""
                return input_text.replace(old_text, new_text)

            elif op_name == "prefix" and len(parts) >= 2:
                return parts[1] + input_text

            elif op_name == "suffix" and len(parts) >= 2:
                return input_text + parts[1]

            elif op_name == "slice" and len(parts) >= 2:
                # slice:start:end (como Python slicing)
                try:
                    start = int(parts[1]) if parts[1] else None
                    end = int(parts[2]) if len(parts) > 2 and parts[2] else None
                    return input_text[start:end]
                except ValueError:
                    return input_text

            elif op_name == "regex" and len(parts) >= 3:
                # regex:pattern:replacement
                pattern = parts[1]
                replacement = parts[2]
                try:
                    return re.sub(pattern, replacement, input_text)
                except re.error as e:
                    print(f"[Transform] Error en regex: {e}")
                    return input_text

            elif op_name == "split" and len(parts) >= 2:
                # split:delimiter:index - dividir y tomar elemento
                delimiter = parts[1]
                index = int(parts[2]) if len(parts) > 2 else 0
                split_parts = input_text.split(delimiter)
                if 0 <= index < len(split_parts):
                    return split_parts[index]
                return ""

            elif op_name == "join" and len(parts) >= 2:
                # join:delimiter - unir líneas con delimiter
                delimiter = parts[1]
                lines = input_text.splitlines()
                return delimiter.join(lines)

        print(f"[Transform] Operación desconocida: {operation}")
        return input_text

    def _execute_condition(self, action: dict, context: dict) -> Optional[str]:
        """
        Ejecuta acciones condicionales.

        Formato:
            {
                "type": "condition",
                "if": "{variable}",           # Variable a evaluar
                "equals": "valor",            # Comparar con valor (opcional)
                "contains": "texto",          # Contiene texto (opcional)
                "not_empty": true,            # No está vacío (opcional)
                "then": [...acciones...],     # Si cumple condición
                "else": [...acciones...]      # Si no cumple (opcional)
            }
        """
        var_value = action.get("if", "")

        # Evaluar condición
        condition_met = False

        if "equals" in action:
            condition_met = var_value == action["equals"]
        elif "contains" in action:
            condition_met = action["contains"] in var_value
        elif "not_empty" in action:
            condition_met = bool(var_value.strip()) == action["not_empty"]
        elif "starts_with" in action:
            condition_met = var_value.startswith(action["starts_with"])
        elif "ends_with" in action:
            condition_met = var_value.endswith(action["ends_with"])
        else:
            # Por defecto, evaluar como booleano (truthy/falsy)
            condition_met = bool(var_value.strip())

        # Ejecutar rama correspondiente
        if condition_met:
            actions_to_run = action.get("then", [])
        else:
            actions_to_run = action.get("else", [])

        if actions_to_run:
            # Ejecutar sub-pipeline
            for sub_action in actions_to_run:
                interpolated = self._interpolate_vars(sub_action, context)
                result = self._execute_one(interpolated, context)
                output_var = sub_action.get("output")
                if output_var and result is not None:
                    context[output_var] = str(result)

        return str(condition_met).lower()  # "true" o "false"
