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
        text_lower = text.lower()
        for cmd in self._commands:
            if current_state not in cmd.allowed_states:
                continue
            for keyword in cmd.keywords:
                if keyword in text_lower:
                    return cmd
        return None
