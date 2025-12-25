from dataclasses import dataclass, field
from typing import Callable, Optional
import threading

from core.state import State


@dataclass
class Command:
    keywords: list[str]           # ["listo", "lista"]
    action: Callable[[], None]    # Funcion a ejecutar
    allowed_states: list[State] = field(default_factory=lambda: [State.IDLE])
    sound: Optional[str] = None   # Sonido al ejecutar
    next_state: Optional[State] = None  # Estado resultante (para encadenamiento)


class CommandRegistry:
    """
    Registry for voice commands with thread-safe hot reload support.

    Commands are tagged with a source (e.g., "builtin", "custom") to allow
    selective unregistration during hot reload.
    """

    def __init__(self):
        self._commands: list[Command] = []
        self._command_sources: dict[int, str] = {}  # id(cmd) -> source
        self._lock = threading.RLock()

    def register(self, command: Command, source: str = "builtin") -> None:
        """Register a command with source tracking."""
        with self._lock:
            self._commands.append(command)
            self._command_sources[id(command)] = source

    def unregister_by_source(self, source: str) -> int:
        """
        Remove all commands from a specific source.

        Returns:
            Number of commands removed
        """
        with self._lock:
            to_remove = [
                cmd for cmd in self._commands
                if self._command_sources.get(id(cmd)) == source
            ]
            for cmd in to_remove:
                self._commands.remove(cmd)
                del self._command_sources[id(cmd)]
            return len(to_remove)

    def register_batch(self, commands: list[Command], source: str) -> int:
        """
        Atomically register multiple commands with the same source.

        Returns:
            Number of commands registered
        """
        with self._lock:
            for cmd in commands:
                self._commands.append(cmd)
                self._command_sources[id(cmd)] = source
            return len(commands)

    def get_commands_by_source(self, source: str) -> list[Command]:
        """Get all commands from a specific source."""
        with self._lock:
            return [
                cmd for cmd in self._commands
                if self._command_sources.get(id(cmd)) == source
            ]

    def get_source_counts(self) -> dict[str, int]:
        """Get count of commands by source."""
        with self._lock:
            counts: dict[str, int] = {}
            for cmd in self._commands:
                source = self._command_sources.get(id(cmd), "unknown")
                counts[source] = counts.get(source, 0) + 1
            return counts

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

        with self._lock:
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

    def find_chain(self, text: str, current_state: State) -> list[Command]:
        """
        Detecta múltiples comandos en una frase.

        Estrategia:
        1. Primero buscar match exacto completo (prioridad a aliases compuestos)
        2. Si no hay match exacto, tokenizar y buscar comandos individuales
        3. Validar que la secuencia sea ejecutable (estados compatibles)

        Args:
            text: Texto reconocido por voz
            current_state: Estado actual del sistema

        Returns:
            Lista ordenada de comandos a ejecutar (puede estar vacía)
        """
        text_lower = text.lower().strip()

        # 1. Match exacto completo primero (aliases compuestos tienen prioridad)
        exact = self.find(text, current_state)
        if exact and any(text_lower == kw for kw in exact.keywords):
            return [exact]

        # 2. Tokenizar y buscar comandos individuales
        words = text_lower.split()
        commands: list[Command] = []
        i = 0
        state = current_state

        with self._lock:
            while i < len(words):
                # Intentar match del substring más largo posible
                best_cmd: Optional[Command] = None
                best_len = 0

                for j in range(len(words), i, -1):
                    phrase = " ".join(words[i:j])
                    cmd = self._find_in_state(phrase, state)
                    if cmd:
                        best_cmd = cmd
                        best_len = j - i
                        break

                if best_cmd:
                    commands.append(best_cmd)
                    # Actualizar estado para validar siguiente comando
                    state = self._next_state(best_cmd, state)
                    i += best_len
                else:
                    i += 1  # Saltar palabra no reconocida

        return commands

    def _find_in_state(self, text: str, state: State) -> Optional[Command]:
        """
        Busca un comando que coincida exactamente con el texto en un estado dado.

        A diferencia de find(), solo busca match exacto (keyword == text).
        Note: Caller must hold the lock or call from within locked context.
        """
        text_lower = text.lower().strip()

        for cmd in self._commands:
            if state not in cmd.allowed_states:
                continue

            for keyword in cmd.keywords:
                if text_lower == keyword:
                    return cmd

        return None

    def _next_state(self, cmd: Command, current: State) -> State:
        """
        Determina el estado resultante después de ejecutar un comando.

        Si el comando tiene next_state definido, lo usa.
        Si no, asume que mantiene el estado actual.
        """
        if cmd.next_state is not None:
            return cmd.next_state
        return current
