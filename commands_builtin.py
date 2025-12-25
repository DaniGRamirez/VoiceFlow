"""
VoiceFlow Built-in Commands - Command registration.
"""

import os

from core.state import StateMachine, State
from core.commands import CommandRegistry, Command
from core.actions import Actions, NUMEROS
from config.settings import BASE_DIR
from config.aliases import (
    ENTER_ALIASES, ESCAPE_ALIASES, TAB_ALIASES,
    ARRIBA_ALIASES, ABAJO_ALIASES, IZQUIERDA_ALIASES, DERECHA_ALIASES,
    COPIAR_ALIASES, PEGAR_ALIASES, DESHACER_ALIASES, REHACER_ALIASES,
    GUARDAR_ALIASES, SELECCION_ALIASES, ELIMINAR_ALIASES, BORRAR_ALIASES, BORRA_TODO_ALIASES,
    INICIO_ALIASES, FIN_ALIASES,
    DICTADO_ALIASES, LISTO_ALIASES, CANCELA_ALIASES, ENVIAR_ALIASES,
    CODE_ALIASES, CODE_DICTADO_ALIASES,
    ACEPTAR_ALIASES, REPETIR_ALIASES, AYUDA_ALIASES,
    PAUSA_ALIASES, REANUDA_ALIASES, REINICIAR_ALIASES, RECARGAR_ALIASES
)

# Global reference to command watcher (set by main.py)
_command_watcher = None


def set_command_watcher(watcher):
    """Set the global command watcher reference."""
    global _command_watcher
    _command_watcher = watcher


def get_command_watcher():
    """Get the global command watcher reference."""
    return _command_watcher


def register_builtin_commands(
    registry: CommandRegistry,
    state_machine: StateMachine,
    actions: Actions,
    sounds,
    overlay
):
    """Register all built-in voice commands."""

    # Claude/VSCode commands
    registry.register(Command(
        keywords=CODE_ALIASES,
        action=actions.on_claudia,
        allowed_states=[State.IDLE],
        sound="ding"
    ))

    registry.register(Command(
        keywords=CODE_DICTADO_ALIASES,
        action=lambda: actions.on_claudia_dictado(state_machine),
        allowed_states=[State.IDLE],
        sound="ding"
    ))

    # Dictation commands
    registry.register(Command(
        keywords=DICTADO_ALIASES,
        action=lambda: (
            state_machine.transition(State.DICTATING),
            actions.on_dictado()
        ),
        allowed_states=[State.IDLE],
        sound="ding",
        next_state=State.DICTATING
    ))

    registry.register(Command(
        keywords=LISTO_ALIASES,
        action=lambda: (
            actions.on_listo(),
            state_machine.transition(State.IDLE)
        ),
        allowed_states=[State.DICTATING],
        sound="success",
        next_state=State.IDLE
    ))

    registry.register(Command(
        keywords=CANCELA_ALIASES,
        action=lambda: (
            actions.on_cancela(),
            state_machine.transition(State.IDLE)
        ),
        allowed_states=[State.DICTATING],
        sound="error",
        next_state=State.IDLE
    ))

    registry.register(Command(
        keywords=ENVIAR_ALIASES,
        action=lambda: actions.on_enviar(state_machine),
        allowed_states=[State.DICTATING],
        sound="success",
        next_state=State.IDLE
    ))

    # Navigation commands
    registry.register(Command(
        keywords=ENTER_ALIASES,
        action=actions.on_enter,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=ESCAPE_ALIASES,
        action=actions.on_escape,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=TAB_ALIASES,
        action=actions.on_tab,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=ACEPTAR_ALIASES,
        action=actions.on_enter,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    # Arrow keys
    registry.register(Command(
        keywords=ARRIBA_ALIASES,
        action=lambda: actions.on_flecha('up'),
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=ABAJO_ALIASES,
        action=lambda: actions.on_flecha('down'),
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=IZQUIERDA_ALIASES,
        action=lambda: actions.on_flecha('left'),
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=DERECHA_ALIASES,
        action=lambda: actions.on_flecha('right'),
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=INICIO_ALIASES,
        action=actions.on_inicio,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=FIN_ALIASES,
        action=actions.on_fin,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    # Edit commands
    registry.register(Command(
        keywords=SELECCION_ALIASES,
        action=actions.on_seleccion,
        allowed_states=[State.IDLE],
        sound="pop"
    ))

    registry.register(Command(
        keywords=ELIMINAR_ALIASES,
        action=actions.on_eliminar,
        allowed_states=[State.IDLE],
        sound="pop"
    ))

    registry.register(Command(
        keywords=BORRAR_ALIASES,
        action=actions.on_eliminar,
        allowed_states=[State.IDLE],
        sound="pop"
    ))

    registry.register(Command(
        keywords=BORRA_TODO_ALIASES,
        action=actions.on_borra_todo,
        allowed_states=[State.IDLE],
        sound="error"
    ))

    registry.register(Command(
        keywords=COPIAR_ALIASES,
        action=actions.on_copiar,
        allowed_states=[State.IDLE],
        sound="pop"
    ))

    registry.register(Command(
        keywords=PEGAR_ALIASES,
        action=actions.on_pegar,
        allowed_states=[State.IDLE],
        sound="pop"
    ))

    registry.register(Command(
        keywords=DESHACER_ALIASES,
        action=actions.on_deshacer,
        allowed_states=[State.IDLE],
        sound="pop"
    ))

    registry.register(Command(
        keywords=REHACER_ALIASES,
        action=actions.on_rehacer,
        allowed_states=[State.IDLE],
        sound="pop"
    ))

    registry.register(Command(
        keywords=GUARDAR_ALIASES,
        action=actions.on_guardar,
        allowed_states=[State.IDLE],
        sound="success"
    ))

    # Utility commands
    registry.register(Command(
        keywords=AYUDA_ALIASES,
        action=lambda: actions.on_ayuda(state_machine.state, registry, overlay),
        allowed_states=[State.IDLE, State.DICTATING],
        sound="ding"
    ))

    registry.register(Command(
        keywords=REPETIR_ALIASES,
        action=actions.on_repetir,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    # State commands
    registry.register(Command(
        keywords=PAUSA_ALIASES,
        action=lambda: (
            actions.on_pausa(),
            state_machine.transition(State.PAUSED)
        ),
        allowed_states=[State.IDLE],
        sound="ding",
        next_state=State.PAUSED
    ))

    registry.register(Command(
        keywords=REANUDA_ALIASES,
        action=lambda: (
            actions.on_reanuda(),
            state_machine.transition(State.IDLE)
        ),
        allowed_states=[State.PAUSED],
        sound="ding",
        next_state=State.IDLE
    ))

    registry.register(Command(
        keywords=REINICIAR_ALIASES,
        action=actions.on_reiniciar,
        allowed_states=[State.IDLE, State.PAUSED],
        sound="ding"
    ))

    # Reload commands
    def do_reload():
        watcher = get_command_watcher()
        if watcher:
            result = watcher.reload()
            if result.success:
                overlay.show_text(f"Recargados {result.commands_loaded} comandos", is_command=True)
            else:
                overlay.show_text(f"Error: {result.errors[0] if result.errors else 'unknown'}", is_command=False)
        else:
            overlay.show_text("Hot reload no disponible", is_command=False)

    registry.register(Command(
        keywords=RECARGAR_ALIASES,
        action=do_reload,
        allowed_states=[State.IDLE],
        sound=None  # Sound handled by watcher
    ))

    # Numeric options
    for palabra, numero in NUMEROS.items():
        registry.register(Command(
            keywords=[f"opcion {palabra}", palabra],
            action=lambda n=numero: actions.on_opcion(n),
            allowed_states=[State.IDLE],
            sound="click"
        ))


def load_custom_commands(
    registry: CommandRegistry,
    config: dict,
    sounds,
    overlay
) -> int:
    """
    Load custom commands from JSON files.

    Returns:
        Number of commands loaded
    """
    custom_config = config.get("custom_commands", {})
    if not custom_config.get("enabled", True):
        return 0

    from core.custom_commands import CustomCommandLoader

    commands_dir = os.path.join(BASE_DIR, "config", "commands")
    loader = CustomCommandLoader(
        commands_dir=commands_dir,
        allow_dangerous=custom_config.get("allow_dangerous_actions", False),
        sound_player=sounds,
        overlay=overlay
    )
    custom_commands = loader.load_all()
    for cmd in custom_commands:
        registry.register(cmd)

    if custom_commands:
        print(f"[Custom] Total: {len(custom_commands)} comandos personalizados")

    return len(custom_commands)


def setup_hint_callbacks(overlay, sounds, actions, state_machine):
    """Configure clickable hint callbacks on overlay."""

    def hint_listo():
        sounds.play("success")
        overlay.flash_success()
        actions.on_listo()
        state_machine.transition(State.IDLE)

    def hint_cancela():
        sounds.play("error")
        overlay.flash_error()
        actions.on_cancela()
        state_machine.transition(State.IDLE)

    def hint_reanuda():
        sounds.play("ding")
        overlay.flash_success()
        actions.on_reanuda()
        state_machine.transition(State.IDLE)

    overlay.set_hint_callbacks(hint_listo, hint_cancela)
    overlay.set_reanuda_callback(hint_reanuda)
