"""
VoiceFlow - Control por voz para VSCode
"""

import os
import sys
import threading

from core.engine import VoiceEngine
from core.state import StateMachine, State
from core.commands import CommandRegistry, Command
from core.actions import Actions, NUMEROS
from ui.overlay import Overlay
from audio.feedback import SoundPlayer
from config.settings import load_config, BASE_DIR


DEBUG_MODE = "--debug" in sys.argv or "-d" in sys.argv

# Mostrar ayuda si se solicita
if "--help" in sys.argv or "-h" in sys.argv:
    print("""
VoiceFlow - Control por voz para VSCode

Uso: python main.py [opciones]

Opciones:
  -d, --debug              Modo debug (sin reconocimiento de voz)
  -m, --model MODEL        Modelo Vosk a usar
  -D, --dictation MODE     Modo de dictado: wispr o winh
  -h, --help               Muestra esta ayuda

Modelos disponibles:
  small, s                 vosk-model-small-es-0.42 (rápido, menos preciso)
  large, l                 vosk-model-es-0.42 (lento, más preciso)
  <nombre>                 Nombre completo de carpeta en models/

Modos de dictado:
  wispr                    Usa Wispr (Ctrl+Win) - requiere Wispr instalado
  winh                     Usa dictado de Windows (Win+H)

Ejemplos:
  python main.py                       # Wispr + modelo large
  python main.py -m small              # Wispr + modelo pequeño
  python main.py -D winh               # Win+H + modelo large
  python main.py -D winh -m small      # Win+H + modelo pequeño
  python main.py -d                    # Modo debug
""")
    sys.exit(0)

# Modelos disponibles (aliases)
MODEL_ALIASES = {
    "small": "vosk-model-small-es-0.42",
    "large": "vosk-model-es-0.42",
    "s": "vosk-model-small-es-0.42",
    "l": "vosk-model-es-0.42",
}


def get_model_path() -> str:
    """Obtiene la ruta del modelo desde argumentos o config"""
    # Buscar --model o -m en argumentos
    for i, arg in enumerate(sys.argv):
        if arg in ("--model", "-m") and i + 1 < len(sys.argv):
            model_arg = sys.argv[i + 1]
            # Si es un alias, convertir a nombre completo
            if model_arg in MODEL_ALIASES:
                model_name = MODEL_ALIASES[model_arg]
            else:
                model_name = model_arg
            return os.path.join(BASE_DIR, "models", model_name)

    # Si no hay argumento, usar config
    config = load_config()
    return config.get("model_path", os.path.join(BASE_DIR, "models", "vosk-model-es-0.42"))


def get_dictation_mode() -> str:
    """Obtiene el modo de dictado desde argumentos o config"""
    # Buscar --dictation o -D en argumentos
    for i, arg in enumerate(sys.argv):
        if arg in ("--dictation", "-D") and i + 1 < len(sys.argv):
            mode = sys.argv[i + 1].lower()
            if mode in ("wispr", "winh"):
                return mode
            print(f"[WARN] Modo de dictado '{mode}' no reconocido, usando 'wispr'")
            return "wispr"

    # Si no hay argumento, usar config
    config = load_config()
    return config.get("dictation_mode", "wispr")


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

    dictation_mode = get_dictation_mode()
    actions = Actions(config, debug_mode=DEBUG_MODE, dictation_mode=dictation_mode)

    # Registrar comandos
    registry = CommandRegistry()

    registry.register(Command(
        keywords=["claudia"],
        action=actions.on_claudia,
        allowed_states=[State.IDLE],
        sound="ding"
    ))

    registry.register(Command(
        keywords=["claudia dictado", "claudia dictar"],
        action=lambda: actions.on_claudia_dictado(state_machine),
        allowed_states=[State.IDLE],
        sound="ding"
    ))

    registry.register(Command(
        keywords=["dictado"],
        action=lambda: (
            state_machine.transition(State.DICTATING),
            actions.on_dictado()
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
        keywords=["enviar", "envía", "envia"],
        action=lambda: actions.on_enviar(state_machine),
        allowed_states=[State.DICTATING],
        sound="success"
    ))

    # Configurar callbacks de hints para botones clickeables
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

    overlay.set_hint_callbacks(hint_listo, hint_cancela)

    registry.register(Command(
        keywords=["enter", "intro"],
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

    registry.register(Command(
        keywords=["borra todo", "borrar todo"],
        action=actions.on_borra_todo,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["ayuda"],
        action=lambda: actions.on_ayuda(state_machine.state, registry),
        allowed_states=[State.IDLE, State.DICTATING],
        sound="click"
    ))

    registry.register(Command(
        keywords=["escape", "escapar"],
        action=actions.on_escape,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["tab", "tabulador"],
        action=actions.on_tab,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["aceptar"],
        action=actions.on_enter,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["copiar"],
        action=actions.on_copiar,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["pegar"],
        action=actions.on_pegar,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["deshacer"],
        action=actions.on_deshacer,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["rehacer"],
        action=actions.on_rehacer,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["guardar"],
        action=actions.on_guardar,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["arriba"],
        action=lambda: actions.on_flecha('up'),
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["abajo"],
        action=lambda: actions.on_flecha('down'),
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["izquierda"],
        action=lambda: actions.on_flecha('left'),
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["derecha"],
        action=lambda: actions.on_flecha('right'),
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["inicio"],
        action=actions.on_inicio,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["fin"],
        action=actions.on_fin,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=["repetir", "otra vez", "repite"],
        action=actions.on_repetir,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    # Registrar opciones numericas (con y sin prefijo "opcion")
    for palabra, numero in NUMEROS.items():
        registry.register(Command(
            keywords=[f"opcion {palabra}", palabra],
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
                overlay.flash_unknown()

    print("=" * 50)
    if DEBUG_MODE:
        print("VoiceFlow - MODO DEBUG")
    else:
        print("VoiceFlow - Activo")
        model_path = get_model_path()
        model_name = os.path.basename(model_path)
        print(f"Modelo: {model_name}")
    dictation_label = "Wispr" if dictation_mode == "wispr" else "Win+H"
    print(f"Dictado: {dictation_label}")
    print("=" * 50)
    print("Comandos:")
    print("  'claudia'   -> VSCode + Chat")
    print(f"  'dictado'   -> Activa {dictation_label}")
    print("  'listo'     -> Termina dictado")
    print("  'cancela'   -> Cancela dictado")
    print("  'enter'     -> Pulsa Enter")
    print("  'seleccion' -> Ctrl+A")
    print("  'eliminar'  -> Delete")
    print("  'borra todo'-> Ctrl+A + Delete")
    print("  'opcion X'  -> Pulsa numero")
    print("  'ayuda'     -> Muestra comandos")
    if DEBUG_MODE:
        print("  'exit'      -> Salir")
    print("=" * 50)

    engine = None

    if not DEBUG_MODE:
        # Callback para nivel de microfono
        def on_mic_level(level: float):
            overlay.set_mic_level(level)

        # Iniciar motor de voz en thread separado
        engine = VoiceEngine(
            model_path=get_model_path(),
            on_result=on_speech,
            on_mic_level=on_mic_level
        )
        voice_thread = threading.Thread(target=engine.start, daemon=True)
        voice_thread.start()

    # Loop principal de UI
    try:
        if DEBUG_MODE:
            # Modo debug: leer comandos del teclado
            def debug_input():
                while True:
                    try:
                        text = input("> ").strip()
                        if text.lower() == "exit":
                            overlay.quit()
                            break
                        if text:
                            on_speech(text)
                    except EOFError:
                        break

            input_thread = threading.Thread(target=debug_input, daemon=True)
            input_thread.start()

        while True:
            overlay.update()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        # SIEMPRE liberar teclas al salir
        actions.release_keys()
        if engine:
            engine.stop()
        overlay.quit()


if __name__ == "__main__":
    main()
