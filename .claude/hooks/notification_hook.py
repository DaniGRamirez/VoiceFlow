#!/usr/bin/env python3
"""
Hook de Claude Code - Notification

Captura las notificaciones REALES que Claude muestra al usuario,
incluyendo el mensaje exacto de los permission prompts.

El JSON que recibe incluye:
{
  "hook_event_name": "Notification",
  "message": "Claude needs your permission to use Bash",
  "notification_type": "permission_prompt"
}
"""

import json
import sys
import uuid
from urllib.request import Request, urlopen
from urllib.error import URLError

VOICEFLOW_URL = "http://localhost:8765/api/notification"
TIMEOUT = 2


def send_notification(message: str, notification_type: str) -> bool:
    """Envía notificación a VoiceFlow con el mensaje real de Claude."""

    # Determinar título y acciones según el tipo
    if notification_type == "permission_prompt":
        title = "Claude Code"
        actions = [
            {"id": "accept", "label": "Permitir", "hotkey": "y", "style": "primary"},
            {"id": "reject", "label": "Rechazar", "hotkey": "n", "style": "danger"}
        ]
        timeout = 120
    elif notification_type == "idle_prompt":
        title = "Claude esperando"
        actions = [
            {"id": "ok", "label": "OK", "hotkey": "enter", "style": "secondary"}
        ]
        timeout = 30
    else:
        title = "Claude Code"
        actions = [
            {"id": "ok", "label": "OK", "hotkey": "enter", "style": "secondary"}
        ]
        timeout = 30

    payload = {
        "correlation_id": str(uuid.uuid4()),
        "title": title,
        "body": message,  # El mensaje REAL que ve el usuario
        "type": "confirmation" if notification_type == "permission_prompt" else "info",
        "actions": actions,
        "source": "claude_code_notification",
        "timeout_seconds": timeout
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
        # VoiceFlow no está corriendo
        return False
    except Exception as e:
        print(f"[Hook] Error: {e}", file=sys.stderr)
        return False


def main():
    try:
        # Leer datos del hook desde stdin
        input_data = json.load(sys.stdin)

        message = input_data.get("message", "")
        notification_type = input_data.get("notification_type", "unknown")

        # Solo procesar si hay mensaje
        if message:
            send_notification(message, notification_type)

        # Exit 0 = no bloquear
        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)
    except Exception as e:
        print(f"[Hook] Error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
