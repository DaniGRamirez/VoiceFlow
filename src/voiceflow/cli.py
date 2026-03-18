"""VoiceFlow CLI — global voice companion."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys

import typer

from voiceflow.config import load_config, ensure_home

app = typer.Typer(
    name="vf",
    help="VoiceFlow — ambient voice shell with TTS and wake-word",
    no_args_is_help=True,
)


@app.command()
def start(
    headless: bool = typer.Option(False, help="Daemon only, no listen/overlay"),
    port: int | None = typer.Option(None, help="Override daemon port"),
    debug: bool = typer.Option(False, "-d", "--debug", help="Debug mode (no voice engine)"),
):
    """Start VoiceFlow daemon (full mode by default)."""
    from voiceflow.pid import is_daemon_running, write_pid, remove_pid, read_pid

    if is_daemon_running():
        pid = read_pid()
        typer.echo(f"VoiceFlow ya está activo (PID {pid})")
        raise typer.Exit(1)

    ensure_home()
    config = load_config()
    if port:
        config["daemon"]["port"] = port

    # Create TTS engine
    from voiceflow.tts.sapi import SAPIEngine
    tts = SAPIEngine()

    # Create daemon
    from voiceflow.daemon import VoiceFlowDaemon
    daemon = VoiceFlowDaemon(
        tts_engine=tts,
        host=config["daemon"]["host"],
        port=config["daemon"]["port"],
        config=config,
    )

    write_pid()
    actual_port = config["daemon"]["port"]
    typer.echo(f"VoiceFlow iniciado en ws://localhost:{actual_port}")

    if headless:
        typer.echo("Modo headless — solo daemon + TTS")
        _run_headless(daemon, remove_pid)
    else:
        _run_full(daemon, config, debug, remove_pid)


def _run_headless(daemon, remove_pid):
    """Run daemon only (no UI, no listen)."""

    async def run():
        await daemon.start()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            await daemon.stop()
            remove_pid()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        remove_pid()
        typer.echo("\nVoiceFlow detenido")


def _run_full(daemon, config, debug_mode, remove_pid):
    """Run full mode: daemon in background thread + Qt overlay + speech engine on main thread."""
    import threading

    # Start daemon in background thread
    daemon_loop = None

    def daemon_thread_fn():
        nonlocal daemon_loop
        daemon_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(daemon_loop)
        daemon_loop.run_until_complete(daemon.start())
        typer.echo(f"Daemon WS activo en puerto {daemon.port}")
        daemon_loop.run_forever()

    daemon_thread = threading.Thread(target=daemon_thread_fn, daemon=True)
    daemon_thread.start()

    # Give daemon a moment to start
    import time
    time.sleep(0.5)

    # Now run the old VoiceFlow main loop (Qt + engine)
    # This requires being run from the VoiceFlow project directory
    # where models/, audio/, config.json etc. are available
    try:
        _run_legacy_main(daemon, config, debug_mode)
    except Exception as e:
        typer.echo(f"Error en modo full: {e}", err=True)
        typer.echo("Tip: vf start debe ejecutarse desde el directorio de VoiceFlow", err=True)
        typer.echo("     o usa 'vf start --headless' para solo daemon + TTS", err=True)
    finally:
        # Clean shutdown of daemon thread
        if daemon_loop and daemon_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(daemon.stop(), daemon_loop)
            try:
                future.result(timeout=5)
            except Exception:
                pass
            daemon_loop.call_soon_threadsafe(daemon_loop.stop)
            daemon_thread.join(timeout=3)
        remove_pid()


def _resolve_project_dir(vf_config) -> str:
    """Find the VoiceFlow project directory (where main.py, bootstrap.py etc. live).

    Checks in order:
    1. project_dir in ~/.voiceflow/config.yaml
    2. VF_PROJECT_DIR env var
    3. Current working directory (if it has main.py)
    """
    # Config
    project_dir = vf_config.get("project_dir")
    if project_dir and os.path.isfile(os.path.join(project_dir, "main.py")):
        return project_dir

    # Env var
    env_dir = os.environ.get("VF_PROJECT_DIR")
    if env_dir and os.path.isfile(os.path.join(env_dir, "main.py")):
        return env_dir

    # CWD
    if os.path.isfile(os.path.join(os.getcwd(), "main.py")):
        return os.getcwd()

    raise RuntimeError(
        "No se encontró el directorio del proyecto VoiceFlow.\n"
        "Opciones:\n"
        "  1. Ejecuta 'vf start' desde el directorio de VoiceFlow\n"
        "  2. Añade project_dir a ~/.voiceflow/config.yaml\n"
        "  3. Exporta VF_PROJECT_DIR=<ruta>\n"
        "  4. Usa 'vf start --headless' para solo daemon + TTS"
    )


def _run_legacy_main(daemon, vf_config, debug_mode):
    """Run the legacy VoiceFlow main loop with Qt overlay and speech engine.

    Integrates with the WS daemon by broadcasting transcriptions.
    """
    # Resolve and add project dir to sys.path so legacy modules are importable
    project_dir = _resolve_project_dir(vf_config)
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)
    # Also set CWD so relative paths in legacy code work (models/, audio/, etc.)
    os.chdir(project_dir)
    typer.echo(f"Proyecto VoiceFlow: {project_dir}")

    # Clean sys.argv so legacy argparse doesn't see typer's args (e.g. "start")
    original_argv = sys.argv
    sys.argv = [sys.argv[0]]
    if debug_mode:
        sys.argv.append("-d")

    from cli import parse_args, get_engine_type, get_dictation_mode, get_model_paths
    from bootstrap import (
        create_core_components,
        create_notification_system,
        start_transcript_watcher,
        start_command_watcher,
        launch_browser_if_configured,
        create_engine,
        print_startup_info,
    )
    from commands_builtin import (
        register_builtin_commands,
        load_custom_commands,
        setup_hint_callbacks,
        set_command_watcher,
    )
    from core.state import State
    from core.commands import CommandRegistry
    from core.logger import get_logger
    from config.settings import load_config as load_legacy_config, print_config_validation

    import threading

    # Use legacy config (config.json) for UI/engine settings
    args = parse_args()
    if debug_mode:
        args.debug = True

    legacy_config = load_legacy_config()

    if not print_config_validation(legacy_config):
        raise RuntimeError("Configuración inválida")

    engine_type = get_engine_type(args)
    dictation_mode = get_dictation_mode(args)
    initial_model, upgrade_model = get_model_paths(args)

    # Create core components
    state_machine, overlay, sounds, actions = create_core_components(
        legacy_config, args.debug, dictation_mode
    )

    # Launch browser if configured
    launch_browser_if_configured(legacy_config)

    # Create notification system
    notification_panel, notification_manager, event_server = create_notification_system(
        legacy_config, overlay, actions, sounds
    )

    if notification_manager:
        start_transcript_watcher(legacy_config, notification_manager)

    # Command registry
    registry = CommandRegistry()
    register_builtin_commands(registry, state_machine, actions, sounds, overlay)
    setup_hint_callbacks(overlay, sounds, actions, state_machine)
    load_custom_commands(registry, legacy_config, sounds, overlay)

    command_watcher = start_command_watcher(registry, legacy_config, sounds, overlay)
    if command_watcher:
        set_command_watcher(command_watcher)

    # HTTP command endpoint
    if event_server:
        def on_http_command(text: str) -> dict:
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

    # State → UI
    state_machine.on_change(lambda old, new: overlay.set_state(new))

    logger = get_logger()
    is_wake_word_engine = engine_type in ("picovoice", "hybrid")

    def show_auto_help():
        if overlay._auto_help:
            actions.on_ayuda(state_machine.state, registry, overlay)

    # Speech callback — executes commands AND broadcasts transcription via daemon
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
                # Not a local command — broadcast as transcription via WS
                daemon.broadcast_transcription_threadsafe(text, final=True)

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

    overlay.set_silent_input_callback(on_speech)

    print_startup_info(args.debug, engine_type, legacy_config, initial_model, upgrade_model, dictation_mode)

    # Create and start engine
    engine = None
    if not args.debug:
        engine = create_engine(
            legacy_config, engine_type, on_speech,
            lambda level: overlay.set_mic_level(level),
            overlay, show_auto_help, initial_model, upgrade_model,
        )
        logger.set_model_callback(engine.get_model_name)
        voice_thread = threading.Thread(target=engine.start, daemon=True)
        voice_thread.start()
        sounds.play("ding")

    # Qt event loop (blocks until quit)
    try:
        if args.debug:
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
        qt_app = QApplication.instance()
        if qt_app:
            qt_app.aboutToQuit.connect(lambda: print("[Main] aboutToQuit signal recibido"))
            print("[Main] Iniciando event loop de Qt...")
            exit_code = qt_app.exec()
            print(f"[Main] Event loop terminó con código: {exit_code}")

    except KeyboardInterrupt:
        print("[Main] KeyboardInterrupt recibido")
    finally:
        try:
            print(logger.get_session_summary())
            logger.save()
        except Exception:
            pass
        try:
            actions.release_keys()
        except Exception:
            pass
        try:
            if command_watcher:
                command_watcher.stop()
        except Exception:
            pass
        try:
            if engine:
                engine.stop()
        except Exception:
            pass
        try:
            overlay.quit()
        except Exception:
            pass


@app.command()
def stop():
    """Stop the running VoiceFlow daemon."""
    from voiceflow.pid import is_daemon_running, read_pid, remove_pid

    if not is_daemon_running():
        typer.echo("VoiceFlow no está corriendo")
        raise typer.Exit(1)

    pid = read_pid()
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
        typer.echo(f"VoiceFlow detenido (PID {pid})")
    except (ProcessLookupError, OSError):
        typer.echo("Proceso no encontrado, limpiando PID file")
    remove_pid()


@app.command()
def say(
    text: str = typer.Argument(..., help="Text to speak"),
    priority: str = typer.Option("normal", "-p", "--priority", help="low|normal|high|urgent"),
):
    """Send text to VoiceFlow daemon for TTS."""
    from voiceflow.client import VoiceFlowClient
    from voiceflow.protocol import Priority

    config = load_config()
    client = VoiceFlowClient(
        host=config["daemon"]["host"],
        port=config["daemon"]["port"],
    )

    try:
        prio = Priority(priority)
    except ValueError:
        typer.echo(f"Prioridad inválida: {priority}. Usa: low, normal, high, urgent")
        raise typer.Exit(1)

    try:
        ack = asyncio.run(client.say(text, priority=prio, source="vf-cli"))
        if ack.get("queued"):
            typer.echo(f"Encolado [{ack['id']}] posición {ack['position']}")
        else:
            typer.echo("Mensaje descartado (cola llena)")
    except ConnectionError:
        typer.echo("VoiceFlow no está corriendo. Usa 'vf start' primero.", err=True)
        raise typer.Exit(1)


@app.command()
def status():
    """Show VoiceFlow daemon status."""
    from voiceflow.client import VoiceFlowClient

    config = load_config()
    client = VoiceFlowClient(
        host=config["daemon"]["host"],
        port=config["daemon"]["port"],
    )

    try:
        st = asyncio.run(client.status())
        typer.echo(f"Estado:   {st['daemon']}")
        typer.echo(f"Motor:    {st['engine']}")
        typer.echo(f"Hablando: {'sí' if st['speaking'] else 'no'}")
        typer.echo(f"Cola:     {st['queueLength']} mensajes")
        typer.echo(f"Mute:     {'sí' if st['muted'] else 'no'}")
        if st.get("currentText"):
            typer.echo(f"Actual:   {st['currentText']}")
    except ConnectionError:
        typer.echo("VoiceFlow no está corriendo")
        raise typer.Exit(1)


@app.command()
def doctor():
    """Check VoiceFlow dependencies and system status."""
    import importlib.util

    checks = [
        ("typer", "typer", True),
        ("websockets", "websockets", True),
        ("pyyaml", "yaml", True),
        ("PyQt6", "PyQt6", False),
        ("numpy", "numpy", False),
        ("pvporcupine", "pvporcupine", False),
        ("pvrecorder", "pvrecorder", False),
        ("pyautogui", "pyautogui", False),
        ("pygetwindow", "pygetwindow", False),
        ("pyperclip", "pyperclip", False),
        ("python-dotenv", "dotenv", False),
        ("pygame", "pygame", False),
        ("sounddevice", "sounddevice", False),
        ("fastapi", "fastapi", False),
        ("uvicorn", "uvicorn", False),
    ]

    ok = 0
    missing_optional = []
    missing_required = []

    for name, module, required in checks:
        spec = importlib.util.find_spec(module)
        if spec:
            typer.echo(f"  + {name}")
            ok += 1
        elif required:
            typer.echo(f"  ! {name} (REQUERIDO)")
            missing_required.append(name)
        else:
            typer.echo(f"  - {name}")
            missing_optional.append(name)

    typer.echo(f"\n{ok}/{len(checks)} deps OK")

    if missing_required:
        typer.echo(f"\nFaltan deps requeridas: {', '.join(missing_required)}")

    if missing_optional:
        typer.echo(f"\nOpcionales no instaladas: {', '.join(missing_optional)}")
        typer.echo("Instalar: python -m pipx inject voiceflow " + " ".join(missing_optional))

    from voiceflow.config import VF_HOME
    config_path = VF_HOME / "config.yaml"
    if config_path.exists():
        typer.echo(f"\nConfig: {config_path}")
        cfg = load_config()
        project_dir = cfg.get("project_dir")
        if project_dir:
            import os
            if os.path.isfile(os.path.join(project_dir, "main.py")):
                typer.echo(f"Proyecto: {project_dir} (OK)")
            else:
                typer.echo(f"Proyecto: {project_dir} (NO ENCONTRADO)")
        else:
            typer.echo("Proyecto: no configurado (necesario para full mode)")
    else:
        typer.echo(f"\nConfig: no existe ({config_path})")

    from voiceflow.pid import is_daemon_running, read_pid
    if is_daemon_running():
        typer.echo(f"Daemon: corriendo (PID {read_pid()})")
    else:
        typer.echo("Daemon: no activo")


@app.command()
def listen(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON lines"),
):
    """Subscribe to VoiceFlow transcriptions via WebSocket.

    Prints transcribed speech to stdout. Useful for piping to other tools.
    Press Ctrl+C to stop.
    """
    import websockets

    config = load_config()
    url = f"ws://{config['daemon']['host']}:{config['daemon']['port']}"

    async def subscribe():
        try:
            async with websockets.connect(url) as ws:
                typer.echo(f"Escuchando transcripciones en {url}...", err=True)
                async for raw in ws:
                    data = json.loads(raw)
                    if data.get("type") == "transcription":
                        if json_output:
                            print(json.dumps(data), flush=True)
                        else:
                            text = data.get("text", "")
                            marker = "." if data.get("final") else "..."
                            print(f"{text}{marker}", flush=True)
        except (OSError, ConnectionRefusedError):
            typer.echo("VoiceFlow no está corriendo", err=True)
            raise typer.Exit(1)

    try:
        asyncio.run(subscribe())
    except KeyboardInterrupt:
        typer.echo("\nDesconectado", err=True)


@app.command("config")
def show_config():
    """Show current configuration."""
    import yaml
    cfg = load_config()
    typer.echo(yaml.dump(cfg, default_flow_style=False, allow_unicode=True))
