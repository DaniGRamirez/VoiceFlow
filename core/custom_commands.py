"""
CustomCommandLoader - Carga comandos personalizados desde archivos JSON.

Busca archivos *.json en config/commands/ y los convierte en objetos Command
que se registran en el CommandRegistry junto con los comandos built-in.
"""

import glob
import json
import os
from typing import Optional, Callable

from core.commands import Command
from core.state import State
from core.action_executor import ActionExecutor


class CustomCommandLoader:
    """
    Carga comandos desde archivos JSON en config/commands/

    Formato de archivo JSON:
    {
        "version": "1.0",
        "commands": [
            {
                "name": "mi comando",
                "keywords": ["palabra1", "palabra2"],
                "aliases": ["variante1", "variante2"],  // opcional
                "description": "Descripción",           // opcional
                "states": ["idle"],                     // opcional, default: ["idle"]
                "sound": "ding",                        // opcional
                "actions": [
                    {"type": "hotkey", "keys": ["ctrl", "c"]}
                ]
            }
        ]
    }
    """

    # Mapeo de nombres de estado a enums
    STATE_MAP = {
        "idle": State.IDLE,
        "dictating": State.DICTATING,
        "processing": State.PROCESSING,
        "paused": State.PAUSED,
    }

    def __init__(self, commands_dir: str, allow_dangerous: bool = False,
                 sound_player: Optional[Callable] = None,
                 overlay: Optional[object] = None):
        """
        Args:
            commands_dir: Ruta a la carpeta con archivos JSON
            allow_dangerous: Si True, permite acciones shell/run/script
            sound_player: SoundPlayer para acciones de sonido
            overlay: Overlay para acciones de notificación
        """
        self.commands_dir = commands_dir
        self.executor = ActionExecutor(
            allow_dangerous=allow_dangerous,
            sound_player=sound_player,
            overlay=overlay
        )
        self._loaded_commands = []

    def load_all(self) -> list:
        """
        Carga todos los archivos JSON de la carpeta.

        Returns:
            Lista de objetos Command listos para registrar
        """
        commands, _, _ = self.load_all_validated()
        return commands

    def load_all_validated(self) -> tuple[list, list[str], list[str]]:
        """
        Carga y valida todos los archivos JSON de la carpeta.

        Returns:
            Tuple of (commands, errors, files_processed)
            - commands: List of Command objects
            - errors: List of error messages (file or command level)
            - files_processed: List of file paths that were processed
        """
        self._loaded_commands = []
        errors: list[str] = []
        files_processed: list[str] = []

        if not os.path.exists(self.commands_dir):
            errors.append(f"Carpeta no encontrada: {self.commands_dir}")
            return [], errors, []

        json_files = glob.glob(os.path.join(self.commands_dir, "*.json"))

        # Ignorar archivos que empiezan con _
        json_files = [f for f in json_files if not os.path.basename(f).startswith("_")]

        for filepath in json_files:
            files_processed.append(filepath)
            try:
                commands = self._load_file(filepath)
                self._loaded_commands.extend(commands)
            except json.JSONDecodeError as e:
                error_msg = f"{os.path.basename(filepath)}: JSON inválido - {e}"
                errors.append(error_msg)
                print(f"[Custom] {error_msg}")
            except Exception as e:
                error_msg = f"{os.path.basename(filepath)}: {e}"
                errors.append(error_msg)
                print(f"[Custom] Error cargando {filepath}: {e}")

        return self._loaded_commands, errors, files_processed

    def _load_file(self, filepath: str) -> list:
        """Carga un archivo JSON y retorna lista de Commands."""
        filename = os.path.basename(filepath)

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        commands = []
        cmd_defs = data.get("commands", [])

        for cmd_def in cmd_defs:
            # Validar campos requeridos
            if not self._validate(cmd_def, filepath):
                continue

            # Combinar keywords + aliases
            all_keywords = cmd_def["keywords"].copy()
            if "aliases" in cmd_def:
                all_keywords.extend(cmd_def["aliases"])

            # Parsear estados permitidos
            state_names = cmd_def.get("states", ["idle"])
            allowed_states = self._parse_states(state_names)

            # Crear la acción (closure con las acciones del comando)
            actions = cmd_def["actions"]
            cmd_name = cmd_def["name"]

            def make_action(acts, name, executor):
                """Factory para evitar problema de closure en loops."""
                def action_fn():
                    try:
                        success = executor.execute_pipeline(acts, name)
                        if not success and executor.overlay:
                            executor.overlay.show_text("Error ejecutando comando", is_command=False)
                        return success
                    except Exception as e:
                        error_msg = str(e)
                        print(f"[Custom] Error en '{name}': {error_msg}")
                        if executor.overlay:
                            # Mostrar error en overlay
                            executor.overlay.show_text(error_msg, is_command=False)
                        return False
                return action_fn

            cmd = Command(
                keywords=all_keywords,
                action=make_action(actions, cmd_name, self.executor),
                allowed_states=allowed_states,
                sound=cmd_def.get("sound")
            )
            commands.append(cmd)

        if commands:
            print(f"[Custom] Cargados {len(commands)} comandos de {filename}")

        return commands

    def _validate(self, cmd_def: dict, filepath: str) -> bool:
        """Valida que un comando tenga los campos requeridos."""
        required = ["name", "keywords", "actions"]

        for field in required:
            if field not in cmd_def:
                print(f"[Custom] Error en {filepath}: falta campo '{field}'")
                return False

        if not isinstance(cmd_def["keywords"], list):
            print(f"[Custom] Error en {filepath}: 'keywords' debe ser una lista")
            return False

        if len(cmd_def["keywords"]) == 0:
            print(f"[Custom] Error en {filepath}: 'keywords' no puede estar vacío")
            return False

        if not isinstance(cmd_def["actions"], list):
            print(f"[Custom] Error en {filepath}: 'actions' debe ser una lista")
            return False

        return True

    def _parse_states(self, state_names: list) -> list:
        """Convierte nombres de estado a enums State."""
        states = []
        for name in state_names:
            name_lower = name.lower()
            if name_lower in self.STATE_MAP:
                states.append(self.STATE_MAP[name_lower])
            else:
                print(f"[Custom] Estado desconocido: {name}, usando IDLE")
                states.append(State.IDLE)

        return states if states else [State.IDLE]

    def get_descriptions(self) -> dict:
        """
        Retorna descripciones de comandos custom para el popup de ayuda.

        Returns:
            Dict {keyword: description}
        """
        # Por ahora no implementado - se puede añadir si se necesita
        return {}
