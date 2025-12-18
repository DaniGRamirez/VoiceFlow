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
from config.aliases import (
    ENTER_ALIASES, ESCAPE_ALIASES, TAB_ALIASES,
    ARRIBA_ALIASES, ABAJO_ALIASES, IZQUIERDA_ALIASES, DERECHA_ALIASES,
    COPIAR_ALIASES, PEGAR_ALIASES, DESHACER_ALIASES, REHACER_ALIASES,
    GUARDAR_ALIASES, SELECCION_ALIASES, ELIMINAR_ALIASES, BORRA_TODO_ALIASES,
    INICIO_ALIASES, FIN_ALIASES,
    DICTADO_ALIASES, LISTO_ALIASES, CANCELA_ALIASES, ENVIAR_ALIASES,
    CLAUDIA_ALIASES, CLAUDIA_DICTADO_ALIASES,
    ACEPTAR_ALIASES, REPETIR_ALIASES, AYUDA_ALIASES,
    PAUSA_ALIASES, REANUDA_ALIASES, REINICIAR_ALIASES
)
from core.logger import get_logger


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


def get_model_paths() -> tuple:
    """
    Obtiene las rutas de los modelos.

    Returns:
        (initial_model_path, upgrade_model_path)
        - Si el usuario especifica un modelo, se usa ese sin upgrade
        - Si no, se usa small primero y large como upgrade
    """
    small_path = os.path.join(BASE_DIR, "models", "vosk-model-small-es-0.42")
    large_path = os.path.join(BASE_DIR, "models", "vosk-model-es-0.42")

    # Buscar --model o -m en argumentos
    for i, arg in enumerate(sys.argv):
        if arg in ("--model", "-m") and i + 1 < len(sys.argv):
            model_arg = sys.argv[i + 1]
            # Si es un alias, convertir a nombre completo
            if model_arg in MODEL_ALIASES:
                model_name = MODEL_ALIASES[model_arg]
            else:
                model_name = model_arg
            # Si el usuario especifica modelo, no hacer upgrade
            return (os.path.join(BASE_DIR, "models", model_name), None)

    # Sin argumento: usar small primero, upgrade a large
    # Verificar que ambos modelos existen
    if os.path.exists(small_path) and os.path.exists(large_path):
        return (small_path, large_path)
    elif os.path.exists(large_path):
        return (large_path, None)
    elif os.path.exists(small_path):
        return (small_path, None)
    else:
        # Fallback a config
        config = load_config()
        return (config.get("model_path", large_path), None)


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
        sounds_dir=os.path.join(BASE_DIR, "audio", "sounds"),
        enabled=sounds_config.get("enabled", True),
        volume=sounds_config.get("volume", 0.5)
    )

    dictation_mode = get_dictation_mode()
    actions = Actions(config, debug_mode=DEBUG_MODE, dictation_mode=dictation_mode)

    # Registrar comandos
    registry = CommandRegistry()

    registry.register(Command(
        keywords=CLAUDIA_ALIASES,
        action=actions.on_claudia,
        allowed_states=[State.IDLE],
        sound="ding"
    ))

    registry.register(Command(
        keywords=CLAUDIA_DICTADO_ALIASES,
        action=lambda: actions.on_claudia_dictado(state_machine),
        allowed_states=[State.IDLE],
        sound="ding"
    ))

    registry.register(Command(
        keywords=DICTADO_ALIASES,
        action=lambda: (
            state_machine.transition(State.DICTATING),
            actions.on_dictado()
        ),
        allowed_states=[State.IDLE],
        sound="ding"
    ))

    registry.register(Command(
        keywords=LISTO_ALIASES,
        action=lambda: (
            actions.on_listo(),
            state_machine.transition(State.IDLE)
        ),
        allowed_states=[State.DICTATING],
        sound="success"
    ))

    registry.register(Command(
        keywords=CANCELA_ALIASES,
        action=lambda: (
            actions.on_cancela(),
            state_machine.transition(State.IDLE)
        ),
        allowed_states=[State.DICTATING],
        sound="error"
    ))

    registry.register(Command(
        keywords=ENVIAR_ALIASES,
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

    def hint_reanuda():
        sounds.play("ding")
        overlay.flash_success()
        actions.on_reanuda()
        state_machine.transition(State.IDLE)

    overlay.set_hint_callbacks(hint_listo, hint_cancela)
    overlay.set_reanuda_callback(hint_reanuda)

    registry.register(Command(
        keywords=ENTER_ALIASES,
        action=actions.on_enter,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=SELECCION_ALIASES,
        action=actions.on_seleccion,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=ELIMINAR_ALIASES,
        action=actions.on_eliminar,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=BORRA_TODO_ALIASES,
        action=actions.on_borra_todo,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=AYUDA_ALIASES,
        action=lambda: actions.on_ayuda(state_machine.state, registry, overlay),
        allowed_states=[State.IDLE, State.DICTATING],
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

    registry.register(Command(
        keywords=COPIAR_ALIASES,
        action=actions.on_copiar,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=PEGAR_ALIASES,
        action=actions.on_pegar,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=DESHACER_ALIASES,
        action=actions.on_deshacer,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=REHACER_ALIASES,
        action=actions.on_rehacer,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=GUARDAR_ALIASES,
        action=actions.on_guardar,
        allowed_states=[State.IDLE],
        sound="click"
    ))

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

    registry.register(Command(
        keywords=REPETIR_ALIASES,
        action=actions.on_repetir,
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=PAUSA_ALIASES,
        action=lambda: (
            actions.on_pausa(),
            state_machine.transition(State.PAUSED)
        ),
        allowed_states=[State.IDLE],
        sound="click"
    ))

    registry.register(Command(
        keywords=REANUDA_ALIASES,
        action=lambda: (
            actions.on_reanuda(),
            state_machine.transition(State.IDLE)
        ),
        allowed_states=[State.PAUSED],
        sound="ding"
    ))

    registry.register(Command(
        keywords=REINICIAR_ALIASES,
        action=actions.on_reiniciar,
        allowed_states=[State.IDLE, State.PAUSED],
        sound="ding"
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

    # Logger para estadísticas
    logger = get_logger()

    # Callback cuando Vosk reconoce algo
    def on_speech(text: str):
        print(f"  {text}")

        cmd = registry.find(text, state_machine.state)
        if cmd:
            print(f"   -> {cmd.keywords[0]}")
            if cmd.sound:
                sounds.play(cmd.sound)
            overlay.flash_success()
            overlay.show_text(cmd.keywords[0], is_command=True)  # Spore de comando
            logger.log_command(cmd.keywords[0], text)  # Registrar comando
            cmd.action()
        else:
            if state_machine.state == State.IDLE:
                print(f"   (ignorado)")
                overlay.flash_unknown()
                logger.log_ignored(text)  # Registrar texto ignorado
            # Mostrar texto reconocido como spore efímero
            if text:
                overlay.show_text(text, is_command=False)

    # Obtener rutas de modelos (inicial + upgrade)
    initial_model, upgrade_model = get_model_paths()

    print("=" * 50)
    if DEBUG_MODE:
        print("VoiceFlow - MODO DEBUG")
    else:
        print("VoiceFlow - Activo")
        model_name = os.path.basename(initial_model)
        print(f"Modelo inicial: {model_name}")
        if upgrade_model:
            upgrade_name = os.path.basename(upgrade_model)
            print(f"Upgrade pendiente: {upgrade_name}")
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

        # Configuración de audio
        audio_config = config.get("audio", {})
        audio_gain = audio_config.get("gain", 2.0)
        mic_threshold = audio_config.get("mic_threshold", 1500)
        blocksize = audio_config.get("blocksize", 4000)

        # Iniciar motor de voz en thread separado
        engine = VoiceEngine(
            model_path=initial_model,
            on_result=on_speech,
            on_mic_level=on_mic_level,
            gain=audio_gain,
            mic_threshold=mic_threshold,
            blocksize=blocksize,
            upgrade_model_path=upgrade_model
        )

        # Conectar logger con engine para registrar modelo usado
        logger.set_model_callback(engine.get_model_name)

        voice_thread = threading.Thread(target=engine.start, daemon=True)
        voice_thread.start()

    # Loop principal de UI (PyQt6)
    try:
        if DEBUG_MODE:
            # Modo debug: leer comandos del teclado en thread separado
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

        # PyQt6 usa app.exec() para el loop de eventos
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.exec()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        # Guardar log de sesión
        print(logger.get_session_summary())
        logger.save()

        # SIEMPRE liberar teclas al salir
        actions.release_keys()
        if engine:
            engine.stop()
        overlay.quit()


if __name__ == "__main__":
    main()
