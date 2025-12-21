#!/usr/bin/env python3
"""
Hook de Claude Code - PermissionRequest

Se dispara cuando Claude pide permiso al usuario.
Recibe tool_name y tool_input, inferimos las acciones disponibles.

Payload que recibe:
{
  "session_id": "abc123",
  "hook_event_name": "PermissionRequest",
  "tool_name": "Bash",
  "tool_input": {
    "command": "npm install",
    "description": "..."
  },
  "permission_mode": "default"
}
"""

import json
import sys
import os
import uuid
from urllib.request import Request, urlopen
from urllib.error import URLError

VOICEFLOW_URL = "http://localhost:8765/api/notification"
TIMEOUT = 2

# Acciones simples: Aceptar o Cancelar
# Hotkeys: 1 para aceptar (opción 1), Escape para cancelar
DEFAULT_ACTIONS = [
    {"id": "accept", "label": "Aceptar", "hotkey": "1", "style": "primary"},
    {"id": "cancel", "label": "Cancelar", "hotkey": "escape", "style": "danger"}
]

# Herramientas que SIEMPRE requieren confirmación (nunca auto-aprobadas)
TOOLS_ALWAYS_CONFIRM = {"Write", "Edit", "NotebookEdit"}

# Herramientas que NUNCA requieren confirmación (solo lectura)
TOOLS_NEVER_CONFIRM = {"Read", "Glob", "Grep", "WebSearch", "WebFetch", "TodoWrite", "Task"}

# Patrones de Bash auto-aprobados (de settings.local.json)
BASH_AUTO_APPROVED_PREFIXES = [
    "git add", "git commit", "git push", "git status", "git diff", "git log",
    "python -c", "python -m py_compile", "python ", "timeout 5 python",
    "pip install", "dir", "wc", "echo", "cat", "ls", "pwd", "cd"
]


def needs_confirmation(tool_name: str, tool_input: dict, permission_mode: str) -> bool:
    """Determina si esta herramienta necesita confirmación del usuario."""
    # Herramientas de solo lectura nunca necesitan confirmación
    if tool_name in TOOLS_NEVER_CONFIRM:
        return False

    # Si permission_mode es acceptEdits, Write/Edit/NotebookEdit pasan automáticamente
    if permission_mode == "acceptEdits" and tool_name in TOOLS_ALWAYS_CONFIRM:
        return False

    # En modo default, Write y Edit siempre necesitan confirmación
    if tool_name in TOOLS_ALWAYS_CONFIRM:
        return True

    # Para Bash, verificar si el comando está auto-aprobado
    if tool_name == "Bash":
        command = tool_input.get("command", "").strip().lower()
        for prefix in BASH_AUTO_APPROVED_PREFIXES:
            if command.startswith(prefix.lower()):
                return False
        # Comando Bash no auto-aprobado = necesita confirmación
        return True

    # Por defecto, asumir que necesita confirmación
    return True


def build_body(tool_name: str, tool_input: dict) -> str:
    """Construye descripción legible de la operación."""
    if tool_name == "Write":
        file_path = tool_input.get("file_path", "unknown")
        filename = os.path.basename(file_path)
        return f"Crear archivo: {filename}"
    elif tool_name == "Edit":
        file_path = tool_input.get("file_path", "unknown")
        filename = os.path.basename(file_path)
        return f"Editar: {filename}"
    elif tool_name == "Bash":
        command = tool_input.get("command", "")[:80]
        return f"$ {command}"
    elif tool_name == "Read":
        file_path = tool_input.get("file_path", "unknown")
        filename = os.path.basename(file_path)
        return f"Leer: {filename}"
    elif tool_name == "Task":
        prompt = tool_input.get("prompt", "")[:60]
        return f"Subagente: {prompt}..."
    else:
        return f"{tool_name}: {str(tool_input)[:60]}"


def send_notification(tool_name: str, tool_input: dict, session_id: str) -> bool:
    """Envía notificación a VoiceFlow."""

    body = build_body(tool_name, tool_input)
    actions = DEFAULT_ACTIONS

    payload = {
        "correlation_id": session_id or str(uuid.uuid4()),
        "title": f"Claude Code - {tool_name}",
        "body": body,
        "type": "confirmation",
        "actions": actions,
        "source": "claude_permission_request",
        "timeout_seconds": 120
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            VOICEFLOW_URL,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        response = urlopen(req, timeout=TIMEOUT)
        return response.status == 200
    except URLError:
        return False
    except Exception as e:
        print(f"[Hook] Error: {e}", file=sys.stderr)
        return False


def main():
    try:
        input_data = json.load(sys.stdin)

        # Log completo del input para debug
        log_path = r"c:\Users\danig\OneDrive\Documentos\Proyectos\VoiceFlow\hook_debug.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n=== Hook llamado ===\n")
            f.write(json.dumps(input_data, indent=2, ensure_ascii=False))
            f.write("\n")

        tool_name = input_data.get("tool_name", "unknown")
        tool_input = input_data.get("tool_input", {})
        session_id = input_data.get("session_id", "")
        permission_mode = input_data.get("permission_mode", "default")

        # Verificar si necesita confirmación
        if not needs_confirmation(tool_name, tool_input, permission_mode):
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"Saltado (mode={permission_mode}): {tool_name}\n")
            sys.exit(0)

        # Log para debug
        print(f"[Hook] Tool: {tool_name}", file=sys.stderr)

        result = send_notification(tool_name, tool_input, session_id)
        print(f"[Hook] Enviado: {result}", file=sys.stderr)

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"Notificación enviada: {result}\n")

        # Exit 0 = no bloquear, dejar que Claude muestre su diálogo
        sys.exit(0)

    except json.JSONDecodeError as e:
        print(f"[Hook] JSON Error: {e}", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"[Hook] Error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
