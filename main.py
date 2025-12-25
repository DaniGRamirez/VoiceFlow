#!/usr/bin/env python3
"""
VoiceFlow - Control por voz para VSCode

Entry point that orchestrates CLI parsing, component bootstrap, and main loop.
"""

import os
import sys
import threading
import atexit
import signal

# Force immediate stdout flush
sys.stdout.reconfigure(line_buffering=True)


def _exit_handler():
    print("[ATEXIT] Proceso terminando via atexit", flush=True)


def _signal_handler(signum, frame):
    print(f"[SIGNAL] Recibida señal {signum}", flush=True)
    import traceback
    traceback.print_stack(frame)


# Register signal handlers
atexit.register(_exit_handler)
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)
if hasattr(signal, 'SIGBREAK'):
    signal.signal(signal.SIGBREAK, _signal_handler)


def main():
    """Main entry point."""
    from cli import parse_args, get_engine_type, get_dictation_mode, get_model_paths
    from bootstrap import (
        create_core_components,
        create_notification_system,
        start_transcript_watcher,
        launch_browser_if_configured,
        create_engine,
        print_startup_info
    )
    from commands_builtin import (
        register_builtin_commands,
        load_custom_commands,
        setup_hint_callbacks
    )
    from core.state import State
    from core.commands import CommandRegistry
    from core.logger import get_logger
    from config.settings import load_config

    # Parse arguments
    args = parse_args()
    debug_mode = args.debug

    # Load config
    config = load_config()

    # Get engine and dictation settings
    engine_type = get_engine_type(args)
    dictation_mode = get_dictation_mode(args)
    initial_model, upgrade_model = get_model_paths(args)

    # Create core components
    state_machine, overlay, sounds, actions = create_core_components(
        config, debug_mode, dictation_mode
    )

    # Launch browser if configured
    launch_browser_if_configured(config)

    # Create notification system
    notification_panel, notification_manager, event_server = create_notification_system(
        config, overlay, actions, sounds
    )

    # Start transcript watcher if notifications are enabled
    if notification_manager:
        start_transcript_watcher(config, notification_manager)

    # Create command registry
    registry = CommandRegistry()

    # Register built-in commands
    register_builtin_commands(registry, state_machine, actions, sounds, overlay)

    # Setup overlay hint callbacks
    setup_hint_callbacks(overlay, sounds, actions, state_machine)

    # Load custom commands
    load_custom_commands(registry, config, sounds, overlay)

    # Configure HTTP command endpoint
    if event_server:
        def on_http_command(text: str) -> dict:
            """Execute command received via HTTP."""
            commands = registry.find_chain(text, state_machine.state)
            if not commands:
                return {"success": False, "executed": [], "error": f"Comando '{text}' no reconocido"}

            executed = []
            for cmd in commands:
                try:
                    if cmd.sound:
                        sounds.play(cmd.sound)
                    overlay.flash_success()
                    cmd.action()
                    executed.append(cmd.keywords[0])
                except Exception as e:
                    return {"success": False, "executed": executed, "error": str(e)}

            return {"success": True, "executed": executed}

        event_server.on_command = on_http_command
        print(f"[HTTP] Endpoint /api/command habilitado para comandos remotos")

    # Connect state changes to UI
    def on_state_change(old: State, new: State):
        overlay.set_state(new)

    state_machine.on_change(on_state_change)

    # Initialize logger
    logger = get_logger()

    # Is wake-word engine?
    is_wake_word_engine = engine_type in ("picovoice", "hybrid")

    def show_auto_help():
        """Show auto-help if enabled."""
        if overlay._auto_help:
            actions.on_ayuda(state_machine.state, registry, overlay)

    # Speech callback
    def on_speech(text: str):
        from PyQt6.QtCore import QTimer
        try:
            print(f"  {text}", flush=True)
            commands = registry.find_chain(text, state_machine.state)

            if commands:
                cmd_names = [cmd.keywords[0] for cmd in commands]
                print(f"   -> {' + '.join(cmd_names)}", flush=True)

                def execute_command(index: int):
                    if index >= len(commands):
                        return
                    cmd = commands[index]
                    if cmd.sound:
                        sounds.play(cmd.sound)
                    overlay.flash_success()
                    overlay.show_text(cmd.keywords[0], is_command=True)
                    logger.log_command(cmd.keywords[0], text if index == 0 else f"(chain: {text})")
                    cmd.action()
                    if index < len(commands) - 1:
                        QTimer.singleShot(150, lambda: execute_command(index + 1))

                execute_command(0)
            else:
                if state_machine.state == State.IDLE:
                    print(f"   (ignorado)", flush=True)
                    overlay.flash_unknown()
                    logger.log_ignored(text)
                    if is_wake_word_engine and text:
                        show_auto_help()
                if text:
                    overlay.show_text(text, is_command=False)

        except Exception as e:
            print(f"[ERROR on_speech] {type(e).__name__}: {e}", flush=True)
            import traceback
            traceback.print_exc()

    # Connect silent input mode
    overlay.set_silent_input_callback(on_speech)

    # Print startup info
    print_startup_info(debug_mode, engine_type, config, initial_model, upgrade_model, dictation_mode)

    # Create and start engine
    engine = None
    if not debug_mode:
        def on_mic_level(level: float):
            overlay.set_mic_level(level)

        engine = create_engine(
            config, engine_type, on_speech, on_mic_level,
            overlay, show_auto_help, initial_model, upgrade_model
        )

        logger.set_model_callback(engine.get_model_name)

        voice_thread = threading.Thread(target=engine.start, daemon=True)
        voice_thread.start()
        sounds.play("ding")

    # Main UI loop
    try:
        if debug_mode:
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

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(
                lambda: print("[Main] aboutToQuit signal recibido")
            )
            print("[Main] Iniciando event loop de Qt...")
            exit_code = app.exec()
            print(f"[Main] Event loop terminó con código: {exit_code}")

    except KeyboardInterrupt:
        print("[Main] KeyboardInterrupt recibido")
    except Exception as e:
        print(f"\n[ERROR Main] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[Main] Entrando en finally - limpiando...")

        try:
            print(logger.get_session_summary())
            logger.save()
        except Exception as e:
            print(f"[Main] Error guardando log: {e}")

        try:
            actions.release_keys()
        except Exception as e:
            print(f"[Main] Error liberando teclas: {e}")

        try:
            if engine:
                engine.stop()
        except Exception as e:
            print(f"[Main] Error deteniendo engine: {e}")

        try:
            overlay.quit()
        except Exception as e:
            print(f"[Main] Error cerrando overlay: {e}")


if __name__ == "__main__":
    main()
