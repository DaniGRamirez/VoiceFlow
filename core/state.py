from enum import Enum, auto
from typing import Callable


class State(Enum):
    IDLE = auto()          # Escuchando comandos globales
    DICTATING = auto()     # Modo Claudia activo, esperando listo/cancela
    PROCESSING = auto()    # Ejecutando accion


class StateMachine:
    def __init__(self):
        self._state = State.IDLE
        self._listeners: list[Callable[[State, State], None]] = []

    @property
    def state(self) -> State:
        return self._state

    def transition(self, new_state: State):
        old_state = self._state
        self._state = new_state
        for listener in self._listeners:
            listener(old_state, new_state)

    def on_change(self, callback: Callable[[State, State], None]):
        self._listeners.append(callback)
