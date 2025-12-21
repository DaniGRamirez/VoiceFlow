"""
VoiceFlow - Control por voz para VSCode
"""

import os
import sys
import threading

from core.state import StateMachine, State
from core.commands import CommandRegistry, Command
from core.actions import Actions, NUMEROS
from ui.overlay import Overlay
from ui.notification_panel import NotificationPanel
from audio.feedback import SoundPlayer
from config.settings import load_config, BASE_DIR
from config.aliases import (
    ENTER_ALIASES, ESCAPE_ALIASES, TAB_ALIASES,
    ARRIBA_ALIASES, ABAJO_ALIASES, IZQUIERDA_ALIASES, DERECHA_ALIASES,
    COPIAR_ALIASES, PEGAR_ALIASES, DESHACER_ALIASES, REHACER_ALIASES,
    GUARDAR_ALIASES, SELECCION_ALIASES, ELIMINAR_ALIASES, BORRAR_ALIASES, BORRA_TODO_ALIASES,
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
  -e, --engine ENGINE      Motor: vosk o openwakeword (oww)
  -m, --model MODEL        Modelo Vosk a usar
  -D, --dictation MODE     Modo de dictado: wispr o winh
  -h, --help               Muestra esta ayuda

Motores de reconocimiento:
  vosk                     ASR completo (reconoce cualquier palabra)
  openwakeword, oww        Solo wake-words (más eficiente, modelos inglés)
  hybrid, mix              OWW wake + Win+H comandos (recomendado)

Modelos Vosk disponibles:
  small, s                 vosk-model-small-es-0.42 (rápido, menos preciso)
  large, l                 vosk-model-es-0.42 (lento, más preciso)
  <nombre>                 Nombre completo de carpeta en models/

Modos de dictado:
  wispr                    Usa Wispr (Ctrl+Win) - requiere Wispr instalado
  winh                     Usa dictado de Windows (Win+H)

Ejemplos:
  python main.py                       # Vosk + modelo large
  python main.py -m small              # Vosk + modelo pequeño
  python main.py -e oww                # openWakeWord (probar)
  python main.py -e hybrid             # Híbrido: alexa + Win+H (recomendado)
  python main.py -D winh               # Win+H + modelo large
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
            print(f"[WARN] Modo de dictado '{mode}' no reconocido, usando 'winh'")
            return "winh"

    # Si no hay argumento, usar config
    config = load_config()
    return config.get("dictation_mode", "winh")


def get_engine_type() -> str:
    """Obtiene el tipo de motor desde argumentos o config"""
    # Aliases
    oww_aliases = ("openwakeword", "oww", "wakeword")
    hybrid_aliases = ("hybrid", "mix", "mixto")
    picovoice_aliases = ("picovoice", "pv", "porcupine")

    # Buscar --engine o -e en argumentos
    for i, arg in enumerate(sys.argv):
        if arg in ("--engine", "-e") and i + 1 < len(sys.argv):
            engine = sys.argv[i + 1].lower()
            if engine in oww_aliases:
                return "openwakeword"
            if engine in hybrid_aliases:
                return "hybrid"
            if engine in picovoice_aliases:
                return "picovoice"
            if engine == "vosk":
                return "vosk"
            print(f"[WARN] Motor '{engine}' no reconocido, usando 'vosk'")
            return "vosk"

    # Si no hay argumento, usar config
    config = load_config()
    return config.get("engine", "vosk")


def main():
    # Cargar configuracion
    config = load_config()

    # Inicializar componentes
    state_machine = StateMachine()

    overlay_config = config.get("overlay", {})
    overlay = Overlay(
        size=overlay_config.get("size", 40),
        position=tuple(overlay_config.get("position", [1850, 50])),
        opacity=overlay_config.get("opacity", 0.9),
        auto_help=overlay_config.get("auto_help", True)
    )

    sounds_config = config.get("sounds", {})
    sounds = SoundPlayer(
        sounds_dir=os.path.join(BASE_DIR, "audio", "sounds"),
        enabled=sounds_config.get("enabled", True),
        volume=sounds_config.get("volume", 0.5)
    )

    dictation_mode = get_dictation_mode()
    actions = Actions(config, debug_mode=DEBUG_MODE, dictation_mode=dictation_mode)

    # ========== SISTEMA DE NOTIFICACIONES ==========
    notification_panel = None
    notification_manager = None
    event_server = None

    notifications_config = config.get("notifications", {})
    if notifications_config.get("enabled", True):
        try:
            from core.event_server import EventServer, FASTAPI_AVAILABLE
            from core.notification_manager import NotificationManager

            if FASTAPI_AVAILABLE:
                # Crear panel de notificaciones
                panel_config = notifications_config.get("panel", {})
                notification_panel = NotificationPanel(
                    overlay_widget=overlay,
                    margin_top=panel_config.get("margin_top", 80),
                    max_visible=panel_config.get("max_visible", 3)
                )
                notification_panel.show()

                # Crear manager
                notification_manager = NotificationManager(
                    panel=notification_panel,
                    execute_callback=actions.execute_notification_intent,
                    sounds=sounds
                )

                # Crear servidor de eventos
                server_config = notifications_config.get("server", {})
                event_server = EventServer(
                    host=server_config.get("host", "localhost"),
                    port=server_config.get("port", 8765),
                    on_notification=notification_manager.on_notification,
                    on_intent=notification_manager.on_intent
                )
                event_server.start()

                print(f"[Notifications] Servidor activo en http://localhost:{server_config.get('port', 8765)}")
            else:
                print("[Notifications] FastAPI no instalado, notificaciones deshabilitadas")
        except ImportError as e:
            print(f"[Notifications] No disponible: {e}")
        except Exception as e:
            print(f"[Notifications] Error inicializando: {e}")

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
        action=actions.on_eliminar,  # Misma acción que eliminar
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
        keywords=AYUDA_ALIASES,
        action=lambda: actions.on_ayuda(state_machine.state, registry, overlay),
        allowed_states=[State.IDLE, State.DICTATING],
        sound="ding"
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
        sound="ding"
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

    # Cargar comandos custom desde config/commands/*.json
    custom_config = config.get("custom_commands", {})
    if custom_config.get("enabled", True):
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

    # Conectar estado a UI
    def on_state_change(old: State, new: State):
        overlay.set_state(new)

    state_machine.on_change(on_state_change)

    # Logger para estadísticas
    logger = get_logger()

    # Obtener tipo de motor y rutas de modelos
    engine_type = get_engine_type()

    # Flag para saber si el motor usa wake-word (Picovoice/Hybrid)
    is_wake_word_engine = engine_type in ("picovoice", "hybrid")

    # Función para mostrar auto-ayuda (si está habilitada)
    def show_auto_help():
        """Muestra ayuda automática si la opción está activada."""
        if overlay._auto_help:
            actions.on_ayuda(state_machine.state, registry, overlay)

    # Callback cuando el motor reconoce algo
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
                # Mostrar auto-ayuda si es motor wake-word y hay comando inválido
                if is_wake_word_engine and text:
                    show_auto_help()
            # Mostrar texto reconocido como spore efímero
            if text:
                overlay.show_text(text, is_command=False)

    # Conectar modo silencioso (pulsar espacio para escribir comandos)
    overlay.set_silent_input_callback(on_speech)

    initial_model, upgrade_model = get_model_paths()

    print("=" * 50)
    if DEBUG_MODE:
        print("VoiceFlow - MODO DEBUG")
    else:
        print("VoiceFlow - Activo")
        print(f"Motor: {engine_type}")
        if engine_type == "vosk":
            model_name = os.path.basename(initial_model)
            print(f"Modelo inicial: {model_name}")
            if upgrade_model:
                upgrade_name = os.path.basename(upgrade_model)
                print(f"Upgrade pendiente: {upgrade_name}")
        elif engine_type == "hybrid":
            hybrid_config = config.get("hybrid", {})
            wake_word = hybrid_config.get("wake_word", "alexa")
            cmd_window = hybrid_config.get("command_window", 3.0)
            print(f"Wake-word: '{wake_word}' + Win+H")
            print(f"Ventana de comando: {cmd_window}s")
        elif engine_type == "picovoice":
            pv_config = config.get("picovoice", {})
            keyword_path = pv_config.get("keyword_path", "")
            # Extraer nombre del wake-word del archivo
            wake_word = os.path.basename(keyword_path).split("_")[0] if keyword_path else "unknown"
            cmd_window = pv_config.get("command_window", 5.0)
            sensitivity = pv_config.get("sensitivity", 0.7)
            print(f"Wake-word: '{wake_word}' (Picovoice) + Win+H")
            print(f"Sensibilidad: {sensitivity}, Ventana: {cmd_window}s")
        else:
            oww_config = config.get("openwakeword", {})
            oww_models = oww_config.get("models", [])
            if oww_models:
                print(f"Modelos OWW: {', '.join(oww_models)}")
            else:
                print("Modelos OWW: todos los pre-entrenados")
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
    print("  [Espacio]   -> Modo silencioso (escribir)")
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

        # Iniciar motor según tipo seleccionado
        if engine_type == "hybrid":
            from core.hybrid_engine import HybridEngine
            from ui.capture_overlay import CaptureOverlay

            hybrid_config = config.get("hybrid", {})

            # Crear overlay de captura para Win+H (posicionado sobre el icono)
            cmd_window = hybrid_config.get("command_window")
            overlay_pos = tuple(overlay_config.get("position", [1850, 50]))
            capture_overlay = CaptureOverlay(timeout=cmd_window, overlay_position=overlay_pos)

            # Callback para cambio de estado del híbrido
            def on_hybrid_state(state):
                if state == "awake":
                    # Activar animación de listening (sacudida + pulso)
                    overlay.set_listening(True)
                elif state == "idle":
                    # Desactivar animación de listening
                    overlay.set_listening(False)

            engine = HybridEngine(
                model_path=initial_model,  # Ignorado, compatibilidad
                on_result=on_speech,
                on_mic_level=on_mic_level,
                gain=audio_gain,
                mic_threshold=mic_threshold,
                blocksize=blocksize,
                wake_word=hybrid_config.get("wake_word", "alexa"),
                oww_threshold=hybrid_config.get("threshold", 0.5),
                command_window=cmd_window,
                on_state_change=on_hybrid_state,
                on_timeout=show_auto_help,
                capture_overlay=capture_overlay
            )
        elif engine_type == "picovoice":
            from core.picovoice_engine import PicovoiceHybridEngine
            from ui.capture_overlay import CaptureOverlay

            pv_config = config.get("picovoice", {})

            # Crear overlay de captura para Win+H (posicionado sobre el icono)
            cmd_window = pv_config.get("command_window", 5.0)
            overlay_pos = tuple(overlay_config.get("position", [1850, 50]))
            capture_overlay = CaptureOverlay(timeout=cmd_window, overlay_position=overlay_pos)

            # Callback para cambio de estado
            def on_pv_state(state):
                if state == "awake":
                    overlay.set_listening(True)
                elif state == "idle":
                    overlay.set_listening(False)

            engine = PicovoiceHybridEngine(
                model_path=None,  # No usado
                on_result=on_speech,
                on_mic_level=on_mic_level,
                gain=audio_gain,
                mic_threshold=mic_threshold,
                access_key=pv_config.get("access_key"),
                keyword_path=pv_config.get("keyword_path"),
                model_pv_path=pv_config.get("model_path"),
                sensitivity=pv_config.get("sensitivity", 0.7),
                command_window=cmd_window,
                on_state_change=on_pv_state,
                on_timeout=show_auto_help,
                capture_overlay=capture_overlay
            )
        elif engine_type == "openwakeword":
            from core.oww_engine import OpenWakeWordEngine

            oww_config = config.get("openwakeword", {})
            engine = OpenWakeWordEngine(
                model_path=initial_model,  # Ignorado, compatibilidad
                on_result=on_speech,
                on_mic_level=on_mic_level,
                gain=audio_gain,
                mic_threshold=mic_threshold,
                blocksize=blocksize,
                oww_models=oww_config.get("models", None) or None,
                oww_threshold=oww_config.get("threshold", 0.5)
            )
        else:
            from core.engine import VoiceEngine

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

        # Sonido de "ready" para indicar que el sistema está listo
        sounds.play("ding")

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
