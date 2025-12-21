#!/usr/bin/env python3
"""
Transcript Watcher para Claude Code

Monitorea el archivo de transcript (.jsonl) de Claude Code
y detecta cuando se ejecutan herramientas que requieren confirmación.

Alternativa al sistema de hooks PreToolUse.

Uso:
    python transcript_watcher.py [--project NOMBRE_PROYECTO]
"""

import json
import time
import argparse
from pathlib import Path
from typing import Optional, Callable
from urllib.request import Request, urlopen
from urllib.error import URLError

# Configuración
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
VOICEFLOW_URL = "http://localhost:8765/api/notification"
POLL_INTERVAL = 0.3  # segundos entre polls
TIMEOUT = 2

# Herramientas que requieren confirmación (en modo default)
TOOLS_NEED_CONFIRM = {"Write", "Edit", "NotebookEdit", "Bash"}

# Comandos Bash auto-aprobados
BASH_AUTO_APPROVED = [
    "git add", "git commit", "git push", "git status", "git diff", "git log",
    "python -c", "python -m py_compile", "python ", "timeout 5 python",
    "pip install", "dir", "wc", "echo", "cat", "ls", "pwd", "cd",
    "curl"  # Para testing de APIs
]


class TranscriptWatcher:
    """Monitorea un archivo de transcript de Claude Code."""

    def __init__(
        self,
        project_path: Path,
        on_tool_use: Optional[Callable] = None,
        on_tool_complete: Optional[Callable] = None,
        verbose: bool = False,
        auto_dismiss: bool = True
    ):
        self.project_path = project_path
        self.on_tool_use = on_tool_use or self._default_tool_use_handler
        self.on_tool_complete = on_tool_complete or self._default_tool_complete_handler
        self.verbose = verbose  # True = notificar TODAS las herramientas
        self.auto_dismiss = auto_dismiss
        self.file_positions: dict[Path, int] = {}
        self.seen_tool_ids: set[str] = set()
        self.seen_result_ids: set[str] = set()
        self.running = False

    def find_active_transcript(self) -> Optional[Path]:
        """Encuentra el archivo de transcript más reciente."""
        if not self.project_path.exists():
            return None

        jsonl_files = list(self.project_path.glob("*.jsonl"))
        if not jsonl_files:
            return None

        # Ordenar por fecha de modificación (más reciente primero)
        jsonl_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return jsonl_files[0]

    def _is_bash_auto_approved(self, command: str) -> bool:
        """Verifica si un comando Bash está auto-aprobado."""
        cmd_lower = command.strip().lower()
        for prefix in BASH_AUTO_APPROVED:
            if cmd_lower.startswith(prefix.lower()):
                return True
        return False

    def _needs_confirmation(self, tool_name: str, tool_input: dict) -> bool:
        """Determina si una herramienta necesita confirmación."""
        if tool_name not in TOOLS_NEED_CONFIRM:
            return False

        if tool_name == "Bash":
            command = tool_input.get("command", "")
            return not self._is_bash_auto_approved(command)

        return True

    def _process_line(self, line: str):
        """Procesa una línea del transcript."""
        if not line.strip():
            return

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type")
        message = data.get("message", {})
        content = message.get("content", [])

        if not isinstance(content, list):
            return

        for block in content:
            if not isinstance(block, dict):
                continue

            block_type = block.get("type")

            # Detectar tool_use (asistente ejecuta herramienta)
            if msg_type == "assistant" and block_type == "tool_use":
                tool_id = block.get("id", "")
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})

                if tool_id not in self.seen_tool_ids:
                    self.seen_tool_ids.add(tool_id)
                    needs_confirm = self._needs_confirmation(tool_name, tool_input)

                    if self.verbose:
                        # Modo verbose: notificar TODAS las herramientas
                        self.on_tool_use(tool_name, tool_input, tool_id, needs_confirm)
                    elif needs_confirm:
                        # Modo normal: solo herramientas que requieren confirmación
                        self.on_tool_use(tool_name, tool_input, tool_id, True)

            # Detectar tool_result (herramienta completada)
            elif msg_type == "user" and block_type == "tool_result":
                tool_use_id = block.get("tool_use_id", "")

                if tool_use_id and tool_use_id not in self.seen_result_ids:
                    self.seen_result_ids.add(tool_use_id)
                    self.on_tool_complete(tool_use_id)

    def _read_new_lines(self, transcript: Path) -> list[str]:
        """Lee líneas nuevas desde la última posición conocida."""
        pos = self.file_positions.get(transcript, 0)

        try:
            with open(transcript, "r", encoding="utf-8") as f:
                f.seek(pos)
                new_content = f.read()
                self.file_positions[transcript] = f.tell()
        except (IOError, OSError):
            return []

        return new_content.strip().split("\n") if new_content.strip() else []

    def _default_tool_use_handler(self, tool_name: str, tool_input: dict, tool_id: str, needs_confirm: bool = True):
        """Handler por defecto para tool_use: imprime y envía notificación."""
        mode = "confirm" if needs_confirm else "info"
        print(f"[Watcher] Tool: {tool_name} ({mode}, ID: {tool_id[:12]}...)", flush=True)

        # Construir descripción
        if tool_name == "Write":
            file_path = tool_input.get("file_path", "unknown")
            body = f"Crear: {Path(file_path).name}"
        elif tool_name == "Edit":
            file_path = tool_input.get("file_path", "unknown")
            body = f"Editar: {Path(file_path).name}"
        elif tool_name == "Bash":
            command = tool_input.get("command", "")[:60]
            body = f"$ {command}"
        elif tool_name == "Read":
            file_path = tool_input.get("file_path", "unknown")
            body = f"Leer: {Path(file_path).name}"
        elif tool_name == "Glob":
            pattern = tool_input.get("pattern", "")
            body = f"Buscar: {pattern}"
        elif tool_name == "Grep":
            pattern = tool_input.get("pattern", "")[:40]
            body = f"Grep: {pattern}"
        elif tool_name == "Task":
            desc = tool_input.get("description", "")[:40]
            body = f"Agent: {desc}"
        elif tool_name == "TodoWrite":
            body = "Actualizando tareas"
        else:
            body = f"{tool_name}"

        # Enviar a VoiceFlow
        self._send_notification(tool_name, body, tool_id, needs_confirm)

    def _default_tool_complete_handler(self, tool_use_id: str):
        """Handler por defecto para tool_result: envía dismiss."""
        print(f"[Watcher] Completado: {tool_use_id[:12]}...", flush=True)
        self._send_dismiss(tool_use_id)

    def _send_notification(self, tool_name: str, body: str, tool_id: str, needs_confirm: bool = True):
        """Envía notificación a VoiceFlow."""
        if needs_confirm:
            # Notificación de confirmación (amarillo/naranja con botones)
            payload = {
                "correlation_id": tool_id,
                "title": f"Claude Code - {tool_name}",
                "body": body,
                "type": "confirmation",
                "actions": [
                    {"id": "accept", "label": "Aceptar", "hotkey": "1", "style": "primary"},
                    {"id": "cancel", "label": "Cancelar", "hotkey": "escape", "style": "danger"}
                ],
                "source": "transcript_watcher",
                "timeout_seconds": 120
            }
        else:
            # Notificación informativa (verde, sin botones, auto-dismiss)
            payload = {
                "correlation_id": tool_id,
                "title": tool_name,
                "body": body,
                "type": "info",
                "actions": [],
                "source": "transcript_watcher",
                "timeout_seconds": 5,  # Auto-dismiss rápido
                "style": "success"  # Estilo verde
            }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(
                VOICEFLOW_URL,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urlopen(req, timeout=TIMEOUT) as response:
                success = response.status == 200
            print(f"[Watcher] Notificación enviada: {success}", flush=True)
        except URLError as e:
            print(f"[Watcher] VoiceFlow no disponible: {e}", flush=True)
        except Exception as e:
            print(f"[Watcher] Error: {e}", flush=True)

    def _send_dismiss(self, tool_use_id: str):
        """Envía dismiss de notificación a VoiceFlow."""
        # Usar DELETE en /api/notification/{id}
        dismiss_url = f"{VOICEFLOW_URL.rsplit('/', 1)[0]}/notification/{tool_use_id}"

        try:
            req = Request(dismiss_url, method="DELETE")
            with urlopen(req, timeout=TIMEOUT) as response:
                success = response.status == 200
            if success:
                print(f"[Watcher] Dismiss enviado: {tool_use_id[:12]}...", flush=True)
        except URLError:
            pass  # Silencioso si no hay servidor
        except Exception as e:
            print(f"[Watcher] Error dismiss: {e}", flush=True)

    def run(self):
        """Ejecuta el watcher en loop."""
        self.running = True
        print(f"[Watcher] Monitoreando: {self.project_path}", flush=True)

        last_transcript = None

        while self.running:
            transcript = self.find_active_transcript()

            if transcript != last_transcript:
                if transcript:
                    print(f"[Watcher] Transcript activo: {transcript.name}", flush=True)
                    # Posicionarse al final del archivo existente (ignorar histórico)
                    self.file_positions[transcript] = transcript.stat().st_size
                last_transcript = transcript

            if transcript:
                new_lines = self._read_new_lines(transcript)
                for line in new_lines:
                    self._process_line(line)

            time.sleep(POLL_INTERVAL)

    def stop(self):
        """Detiene el watcher."""
        self.running = False


def find_project_by_name(name: str) -> Optional[Path]:
    """Busca un proyecto por nombre parcial."""
    if not CLAUDE_PROJECTS_DIR.exists():
        return None

    for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
        if project_dir.is_dir() and name.lower() in project_dir.name.lower():
            return project_dir
    return None


def main():
    parser = argparse.ArgumentParser(description="Transcript Watcher para Claude Code")
    parser.add_argument("--project", "-p", help="Nombre del proyecto (parcial)")
    parser.add_argument("--list", "-l", action="store_true", help="Listar proyectos")
    args = parser.parse_args()

    if args.list:
        print("Proyectos disponibles:")
        for project in CLAUDE_PROJECTS_DIR.iterdir():
            if project.is_dir():
                transcripts = list(project.glob("*.jsonl"))
                print(f"  {project.name} ({len(transcripts)} transcripts)")
        return

    # Buscar proyecto
    if args.project:
        project_path = find_project_by_name(args.project)
        if not project_path:
            print(f"Proyecto no encontrado: {args.project}")
            return
    else:
        # Buscar VoiceFlow por defecto
        project_path = find_project_by_name("VoiceFlow")
        if not project_path:
            print("No se encontró proyecto VoiceFlow. Usa --project NOMBRE")
            return

    print(f"[Watcher] Proyecto: {project_path.name}")

    watcher = TranscriptWatcher(project_path)

    try:
        watcher.run()
    except KeyboardInterrupt:
        print("\n[Watcher] Detenido")
        watcher.stop()


if __name__ == "__main__":
    main()
