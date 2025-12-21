#!/usr/bin/env python3
"""
Hook de Claude Code - PreToolUse

Se ejecuta ANTES de que Claude use herramientas como Write, Edit, Bash.
Envía una notificación a VoiceFlow para que el usuario pueda ver qué está pasando.

Configuración en .claude/settings.json o settings.local.json:
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/pre_tool_notification.py"
          }
        ]
      }
    ]
  }
}
"""

import json
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError
import uuid

VOICEFLOW_URL = "http://localhost:8765/api/notification"
TIMEOUT = 2


def send_notification(tool_name: str, tool_input: dict) -> bool:
    """Envía notificación a VoiceFlow."""
    import os

    # Construir descripción según la herramienta
    if tool_name == "Write":
        file_path = tool_input.get("file_path", "unknown")
        filename = os.path.basename(file_path)
        body = f"Crear archivo: {filename}"
    elif tool_name == "Edit":
        file_path = tool_input.get("file_path", "unknown")
        filename = os.path.basename(file_path)
        old_string = tool_input.get("old_string", "")[:40]
        body = f"Editar: {filename}"
    elif tool_name == "Bash":
        command = tool_input.get("command", "")[:60]
        body = f"$ {command}"
    else:
        body = f"Herramienta: {tool_name}"

    payload = {
        "correlation_id": str(uuid.uuid4()),
        "title": f"Claude Code",
        "body": body,
        "type": "confirmation",
        "actions": [
            {"id": "accept", "label": "Permitir", "hotkey": "y", "style": "primary"},
            {"id": "reject", "label": "Rechazar", "hotkey": "n", "style": "danger"}
        ],
        "source": "claude_code_hook",
        "timeout_seconds": 60
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
        # VoiceFlow no está corriendo, continuar sin notificar
        return False
    except Exception as e:
        print(f"[Hook] Error: {e}", file=sys.stderr)
        return False


def main():
    try:
        # Leer datos del hook desde stdin
        input_data = json.load(sys.stdin)

        tool_name = input_data.get("tool_name", "unknown")
        tool_input = input_data.get("tool_input", {})

        # Enviar notificación (no bloqueante)
        send_notification(tool_name, tool_input)

        # Exit 0 = permitir que la herramienta continúe
        sys.exit(0)

    except json.JSONDecodeError:
        # Sin datos, continuar
        sys.exit(0)
    except Exception as e:
        print(f"[Hook] Error: {e}", file=sys.stderr)
        sys.exit(0)  # No bloquear aunque haya error


if __name__ == "__main__":
    main()
