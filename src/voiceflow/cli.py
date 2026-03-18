"""VoiceFlow CLI — global voice companion."""
from __future__ import annotations

import asyncio
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

    async def run():
        await daemon.start()
        try:
            await asyncio.Future()  # Run forever
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


@app.command("config")
def show_config():
    """Show current configuration."""
    import yaml
    cfg = load_config()
    typer.echo(yaml.dump(cfg, default_flow_style=False, allow_unicode=True))
