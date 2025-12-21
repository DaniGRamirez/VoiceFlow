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

        tool_name = input_data.get("tool_name", "unknown")
        tool_input = input_data.get("tool_input", {})
        session_id = input_data.get("session_id", "")

        send_notification(tool_name, tool_input, session_id)

        # Exit 0 = no bloquear, dejar que Claude muestre su diálogo
        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)
    except Exception as e:
        print(f"[Hook] Error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
