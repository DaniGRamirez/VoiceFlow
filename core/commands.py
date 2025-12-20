from dataclasses import dataclass
from typing import Callable, Optional

from core.state import State


@dataclass
class Command:
    keywords: list[str]           # ["listo", "lista"]
    action: Callable[[], None]    # Funcion a ejecutar
    allowed_states: list[State]   # En que estados funciona
    sound: Optional[str] = None   # Sonido al ejecutar


class CommandRegistry:
    def __init__(self):
        self._commands: list[Command] = []

    def register(self, command: Command):
        self._commands.append(command)

    def find(self, text: str, current_state: State) -> Optional[Command]:
        """
        Busca el comando que mejor matchea el texto.

        Estrategia de matching (en orden de prioridad):
        1. Match exacto: el texto ES el keyword
        2. Match por longitud: el keyword más largo que esté contenido en el texto

        Esto resuelve colisiones como:
        - "borra todo" vs "borra" → gana "borra todo" (más largo)
        - "test terminal" vs "test" → gana "test terminal" (más largo)
        """
        text_lower = text.lower().strip()

        best_match: Optional[Command] = None
        best_keyword_len = 0

        for cmd in self._commands:
            if current_state not in cmd.allowed_states:
                continue

            for keyword in cmd.keywords:
                # Verificar si el keyword está contenido en el texto
                if keyword not in text_lower:
                    continue

                # Match exacto tiene máxima prioridad
                if text_lower == keyword:
                    return cmd

                # Si no es exacto, preferir keyword más largo
                if len(keyword) > best_keyword_len:
                    best_keyword_len = len(keyword)
                    best_match = cmd

        return best_match
