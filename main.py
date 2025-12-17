"""
VoiceFlow - Control por voz para VSCode
"""

import threading

from core.engine import VoiceEngine
from core.state import StateMachine, State
from core.commands import CommandRegistry, Command
from core.actions import Actions, NUMEROS
from ui.overlay import Overlay
from audio.feedback import SoundPlayer
from config.settings import load_config


def main():
    # Cargar configuracion
    config = load_config()

    # Inicializar componentes
    state_machine = StateMachine()

    overlay_config = config.get("overlay", {})
    overlay = Overlay(
        size=overlay_config.get("size", 40),
        position=tuple(overlay_config.get("position", [1850, 50])),
        opacity=overlay_config.get("opacity", 0.9)
    )

    sounds_config = config.get("sounds", {})
    sounds = SoundPlayer(
        sounds_dir="audio/sounds",
        enabled=sounds_config.get("enabled", True),
        volume=sounds_config.get("volume", 0.5)
    )

    actions = Actions(config)

    # Registrar comandos
    registry = CommandRegistry()

    registry.register(Command(
        keywords=["claudia"],
        action=lambda: (
            state_machine.transition(State.DICTATING),
            actions.on_claudia()
        ),
        allowed_states=[State.IDLE],
        sound="ding"
    ))

    registry.register(Command(
        keywords=["listo", "lista"],
        action=lambda: (
            actions.on_listo(),
            state_machine.transition(State.IDLE)
        ),
        allowed_states=[State.DICTATING],
        sound="success"
    ))

    registry.register(Command(
        keywords=["cancela", "cancelar"],
        action=lambda: (
            actions.on_cancela(),
            state_machine.transition(State.IDLE)
        ),
        allowed_states=[State.DICTATING],
        sound="error"
    ))

    registry.register(Command(
        keywords=["enter"],
        action=actions.on_enter,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["seleccion"],
        action=actions.on_seleccion,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["eliminar"],
        action=actions.on_eliminar,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    # Registrar opciones numericas
    for palabra, numero in NUMEROS.items():
        registry.register(Command(
            keywords=[f"opcion {palabra}"],
            action=lambda n=numero: actions.on_opcion(n),
            allowed_states=[State.IDLE],
            sound="click"
        ))

    # Conectar estado a UI
    def on_state_change(old: State, new: State):
        overlay.set_state(new)

    state_machine.on_change(on_state_change)

    # Callback cuando Vosk reconoce algo
    def on_speech(text: str):
        print(f"  {text}")

        cmd = registry.find(text, state_machine.state)
        if cmd:
            print(f"   -> {cmd.keywords[0]}")
            if cmd.sound:
                sounds.play(cmd.sound)
            overlay.flash_success()
            cmd.action()
        else:
            if state_machine.state == State.IDLE:
                print(f"   (ignorado)")

    # Iniciar motor de voz en thread separado
    engine = VoiceEngine(
        model_path=config.get("model_path", "models/vosk-model-small-es-0.42"),
        on_result=on_speech
    )

    voice_thread = threading.Thread(target=engine.start, daemon=True)
    voice_thread.start()

    print("=" * 50)
    print("VoiceFlow - Activo")
    print("=" * 50)
    print("Comandos:")
    print("  'claudia'   -> VSCode + Chat + Wispr")
    print("  'listo'     -> Pega texto")
    print("  'cancela'   -> Borra texto")
    print("  'enter'     -> Pulsa Enter")
    print("  'seleccion' -> Ctrl+A")
    print("  'eliminar'  -> Delete")
    print("  'opcion X'  -> Pulsa numero")
    print("=" * 50)

    # Loop principal de UI
    try:
        while True:
            overlay.update()
    except KeyboardInterrupt:
        engine.stop()
        overlay.quit()


if __name__ == "__main__":
    main()
