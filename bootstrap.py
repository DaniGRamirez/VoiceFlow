"""
VoiceFlow Bootstrap - Component initialization.
"""

import os
import threading
from dataclasses import dataclass
from typing import Optional, Callable

from config.settings import load_config, BASE_DIR

# Type aliases for optional imports
SoundPlayer = Optional[object]
Overlay = Optional[object]
CommandWatcher = Optional[object]


@dataclass
class AppComponents:
    """Container for all VoiceFlow components."""
    config: dict
    state_machine: "StateMachine"
    overlay: "Overlay"
    sounds: "SoundPlayer"
    actions: "Actions"
    registry: "CommandRegistry"
    notification_panel: Optional["NotificationPanel"] = None
    notification_manager: Optional["NotificationManager"] = None
    event_server: Optional["EventServer"] = None
    command_watcher: Optional["CommandWatcher"] = None
    engine: Optional[object] = None
    logger: Optional["UsageLogger"] = None


def create_core_components(config: dict, debug_mode: bool, dictation_mode: str) -> tuple:
    """
    Create core components (state, overlay, sounds, actions).

    Returns:
        (state_machine, overlay, sounds, actions)
    """
    from core.state import StateMachine
    from core.actions import Actions
    from ui.overlay import Overlay
    from audio.feedback import SoundPlayer

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

    actions = Actions(config, debug_mode=debug_mode, dictation_mode=dictation_mode)

    return state_machine, overlay, sounds, actions


def create_notification_system(
    config: dict,
    overlay: "Overlay",
    actions: "Actions",
    sounds: "SoundPlayer"
) -> tuple:
    """
    Create notification system (panel, manager, server).

    Returns:
        (notification_panel, notification_manager, event_server) or (None, None, None)
    """
    notifications_config = config.get("notifications", {})
    if not notifications_config.get("enabled", True):
        return None, None, None

    try:
        from core.event_server import EventServer, FASTAPI_AVAILABLE
        from core.notification_manager import NotificationManager
        from ui.notification_panel import NotificationPanel
        from core.pushover_client import PushoverClient

        if not FASTAPI_AVAILABLE:
            print("[Notifications] FastAPI no instalado, notificaciones deshabilitadas")
            return None, None, None

        # Create panel
        panel_config = notifications_config.get("panel", {})
        notification_panel = NotificationPanel(
            overlay_widget=overlay,
            margin_top=panel_config.get("margin_top", 80),
            max_visible=panel_config.get("max_visible", 3)
        )
        notification_panel.show()

        # Setup Pushover
        pushover_config = config.get("pushover", {})
        pushover_client = None
        if pushover_config.get("enabled", False):
            pushover_client = PushoverClient(pushover_config)
            if pushover_client.enabled:
                print("[Pushover] Cliente inicializado")

        # Get Tailscale URL
        tailscale_url = _get_tailscale_url(config)

        # Create manager
        notification_manager = NotificationManager(
            panel=notification_panel,
            execute_callback=actions.execute_notification_intent,
            sounds=sounds,
            pushover_client=pushover_client,
            tailscale_url=tailscale_url
        )

        # Create server
        server_config = notifications_config.get("server", {})
        tailscale_config = config.get("tailscale", {})

        if tailscale_config.get("enabled", False):
            bind_host = tailscale_config.get("bind_address", "0.0.0.0")
        else:
            bind_host = server_config.get("host", "localhost")

        server_port = server_config.get("port", 8765)

        event_server = EventServer(
            host=bind_host,
            port=server_port,
            on_notification=notification_manager.on_notification,
            on_intent=notification_manager.on_intent,
            on_dismiss=notification_manager.on_dismiss,
            tailscale_config=tailscale_config,
            execute_action=actions.execute_notification_intent,
            on_command=None  # Configured later
        )
        event_server.start()

        if tailscale_config.get("enabled", False):
            print(f"[Tailscale] Servidor expuesto en http://{bind_host}:{server_port}")
        else:
            print(f"[Notifications] Servidor activo en http://localhost:{server_port}")

        return notification_panel, notification_manager, event_server

    except ImportError as e:
        print(f"[Notifications] No disponible: {e}")
        return None, None, None
    except Exception as e:
        print(f"[Notifications] Error inicializando: {e}")
        return None, None, None


def _get_tailscale_url(config: dict) -> Optional[str]:
    """Get Tailscale URL if enabled."""
    tailscale_config = config.get("tailscale", {})
    if not tailscale_config.get("enabled", False):
        return None

    import subprocess
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            tailscale_ip = result.stdout.strip().split("\n")[0]
            server_port = config.get("notifications", {}).get("server", {}).get("port", 8765)
            return f"http://{tailscale_ip}:{server_port}"
    except Exception:
        pass
    return None


def start_transcript_watcher(config: dict, notification_manager: "NotificationManager"):
    """Start transcript watcher if enabled."""
    try:
        from core.transcript_watcher import TranscriptWatcher, find_project_by_name

        watcher_config = config.get("transcript_watcher", {})
        if not watcher_config.get("enabled", True):
            print("[Watcher] Deshabilitado en config")
            return

        project_path = find_project_by_name("VoiceFlow")
        if not project_path:
            print("[Watcher] No se encontró proyecto VoiceFlow en Claude")
            return

        watcher = TranscriptWatcher(
            project_path=project_path,
            on_tool_complete=lambda tool_id: notification_manager.on_dismiss(tool_id),
            verbose=watcher_config.get("verbose", False),
            auto_dismiss=watcher_config.get("auto_dismiss_on_result", True)
        )
        watcher_thread = threading.Thread(target=watcher.run, daemon=True)
        watcher_thread.start()
        mode = "verbose" if watcher_config.get("verbose") else "confirmaciones"
        print(f"[Watcher] Monitoreando transcripts ({mode}): {project_path.name}")

    except Exception as e:
        print(f"[Watcher] Error inicializando: {e}")


def start_command_watcher(
    registry: "CommandRegistry",
    config: dict,
    sounds: Optional["SoundPlayer"] = None,
    overlay: Optional["Overlay"] = None
) -> Optional["CommandWatcher"]:
    """
    Start the custom command file watcher if enabled.

    Returns:
        CommandWatcher instance or None if disabled/failed
    """
    custom_config = config.get("custom_commands", {})

    if not custom_config.get("enabled", True):
        return None

    hot_reload_config = custom_config.get("hot_reload", {})
    if not hot_reload_config.get("enabled", True):
        print("[CommandWatcher] Hot reload deshabilitado en config")
        return None

    try:
        from core.command_watcher import CommandWatcher
        from core.custom_commands import CustomCommandLoader

        commands_dir = os.path.join(BASE_DIR, "config", "commands")

        # Create loader factory
        def create_loader():
            return CustomCommandLoader(
                commands_dir=commands_dir,
                allow_dangerous=custom_config.get("allow_dangerous_actions", False),
                sound_player=sounds,
                overlay=overlay
            )

        watcher = CommandWatcher(
            commands_dir=commands_dir,
            registry=registry,
            loader_factory=create_loader,
            config=config,
            sounds=sounds,
            overlay=overlay,
            debounce_seconds=hot_reload_config.get("debounce_seconds", 0.5)
        )

        if watcher.start():
            return watcher
        else:
            return None

    except ImportError as e:
        print(f"[CommandWatcher] No disponible: {e}")
        return None
    except Exception as e:
        print(f"[CommandWatcher] Error inicializando: {e}")
        return None


def launch_browser_if_configured(config: dict):
    """Launch browser in debug mode if configured."""
    browser_config = config.get("browser", {})
    if not browser_config.get("auto_launch", False):
        return

    from core.browser.chrome_launcher import launch_browser_debug, is_chrome_debug_running

    debug_port = browser_config.get("debug_port", 9222)
    browser_type = browser_config.get("type", "edge")
    user_data_dir = browser_config.get("user_data_dir")

    if is_chrome_debug_running(debug_port):
        print(f"[Browser] Ya hay navegador en puerto {debug_port}")
    else:
        print(f"[Browser] Lanzando {browser_type} en puerto {debug_port}...")
        success = launch_browser_debug(
            port=debug_port,
            browser=browser_type,
            user_data_dir=user_data_dir
        )
        if success:
            print(f"[Browser] Listo para Playwright en http://localhost:{debug_port}")
        else:
            print(f"[Browser] Error al lanzar navegador")


def create_engine(
    config: dict,
    engine_type: str,
    on_speech: Callable[[str], None],
    on_mic_level: Callable[[float], None],
    overlay: "Overlay",
    show_auto_help: Callable[[], None],
    initial_model: str,
    upgrade_model: Optional[str]
):
    """
    Create the appropriate speech engine.

    Returns:
        Engine instance
    """
    audio_config = config.get("audio", {})
    audio_gain = audio_config.get("gain", 2.0)
    mic_threshold = audio_config.get("mic_threshold", 1500)
    blocksize = audio_config.get("blocksize", 4000)
    overlay_config = config.get("overlay", {})

    if engine_type == "hybrid":
        from core.hybrid_engine import HybridEngine
        from ui.capture_overlay import CaptureOverlay

        hybrid_config = config.get("hybrid", {})
        cmd_window = hybrid_config.get("command_window", 5.0)
        overlay_pos = tuple(overlay_config.get("position", [1850, 50]))
        capture_overlay = CaptureOverlay(timeout=cmd_window, overlay_position=overlay_pos)

        def on_hybrid_state(state):
            overlay.set_listening(state == "awake")

        return HybridEngine(
            model_path=initial_model,
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
        cmd_window = pv_config.get("command_window", 5.0)
        overlay_pos = tuple(overlay_config.get("position", [1850, 50]))
        capture_overlay = CaptureOverlay(timeout=cmd_window, overlay_position=overlay_pos)

        def on_pv_state(state):
            overlay.set_listening(state == "awake")

        return PicovoiceHybridEngine(
            model_path=None,
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
        return OpenWakeWordEngine(
            model_path=initial_model,
            on_result=on_speech,
            on_mic_level=on_mic_level,
            gain=audio_gain,
            mic_threshold=mic_threshold,
            blocksize=blocksize,
            oww_models=oww_config.get("models", None) or None,
            oww_threshold=oww_config.get("threshold", 0.5)
        )

    else:  # vosk
        from core.engine import VoiceEngine

        return VoiceEngine(
            model_path=initial_model,
            on_result=on_speech,
            on_mic_level=on_mic_level,
            gain=audio_gain,
            mic_threshold=mic_threshold,
            blocksize=blocksize,
            upgrade_model_path=upgrade_model
        )


def print_startup_info(
    debug_mode: bool,
    engine_type: str,
    config: dict,
    initial_model: str,
    upgrade_model: Optional[str],
    dictation_mode: str
):
    """Print startup information."""
    print("=" * 50)
    if debug_mode:
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
    if debug_mode:
        print("  'exit'      -> Salir")
    print("=" * 50)
