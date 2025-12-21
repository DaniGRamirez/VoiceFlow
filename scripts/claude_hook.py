#!/usr/bin/env python
"""
Claude Code Hook - Envía notificaciones a VoiceFlow.

Este script se ejecuta como hook de Claude Code para capturar eventos
y enviarlos al servidor de notificaciones de VoiceFlow.

Configuración en .claude/settings.json:
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": ".*",
        "hooks": ["python scripts/claude_hook.py pre_tool"]
      }
    ],
    "PostToolUse": [
      {
        "matcher": ".*",
        "hooks": ["python scripts/claude_hook.py post_tool"]
      }
    ],
    "Notification": [
      {
        "hooks": ["python scripts/claude_hook.py notification"]
      }
    ]
  }
}

Uso manual para pruebas:
    python scripts/claude_hook.py test
    python scripts/claude_hook.py notification --title "Test" --body "Mensaje"
"""

import sys
import json
import argparse
import uuid
from typing import Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# Configuración
VOICEFLOW_URL = "http://localhost:8765"
TIMEOUT = 2  # segundos


def send_notification(
    title: str,
    body: str = "",
    notification_type: str = "confirmation",
    actions: Optional[list] = None,
    timeout_seconds: int = 120
) -> bool:
    """
    Envía una notificación a VoiceFlow.

    Args:
        title: Título de la notificación
        body: Cuerpo/descripción
        notification_type: confirmation, choice, info
        actions: Lista de acciones disponibles
        timeout_seconds: Tiempo antes de expirar

    Returns:
        True si se envió correctamente
    """
    if not REQUESTS_AVAILABLE:
        print("[Hook] requests no instalado", file=sys.stderr)
        return False

    if actions is None:
        actions = [
            {"id": "accept", "label": "Aceptar", "hotkey": "enter", "style": "primary"},
            {"id": "cancel", "label": "Cancelar", "hotkey": "escape", "style": "secondary"}
        ]

    payload = {
        "correlation_id": str(uuid.uuid4()),
        "title": title,
        "body": body,
        "type": notification_type,
        "actions": actions,
        "source": "claude_code",
        "timeout_seconds": timeout_seconds
    }

    try:
        response = requests.post(
            f"{VOICEFLOW_URL}/api/notification",
            json=payload,
            timeout=TIMEOUT
        )
        if response.status_code == 200:
            print(f"[Hook] Notificación enviada: {title}")
            return True
        else:
            print(f"[Hook] Error {response.status_code}: {response.text}", file=sys.stderr)
            return False
    except requests.exceptions.ConnectionError:
        print("[Hook] VoiceFlow no disponible", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[Hook] Error: {e}", file=sys.stderr)
        return False


def handle_pre_tool(stdin_data: str):
    """
    Maneja evento PreToolUse.

    Claude Code envía JSON con información de la herramienta.
    """
    try:
        data = json.loads(stdin_data)
        tool_name = data.get("tool_name", "unknown")
        tool_input = data.get("tool_input", {})

        # Solo notificar para herramientas peligrosas
        dangerous_tools = ["Bash", "Write", "Edit", "shell"]

        if tool_name in dangerous_tools:
            # Construir descripción
            if tool_name == "Bash":
                command = tool_input.get("command", "")
                body = f"Comando: {command[:100]}..."
            elif tool_name in ["Write", "Edit"]:
                file_path = tool_input.get("file_path", "")
                body = f"Archivo: {file_path}"
            else:
                body = json.dumps(tool_input)[:100]

            send_notification(
                title=f"Claude: {tool_name}",
                body=body,
                notification_type="confirmation",
                actions=[
                    {"id": "accept", "label": "Permitir", "hotkey": "enter", "style": "primary"},
                    {"id": "cancel", "label": "Rechazar", "hotkey": "escape", "style": "danger"}
                ]
            )

    except json.JSONDecodeError:
        print(f"[Hook] JSON inválido: {stdin_data[:100]}", file=sys.stderr)
    except Exception as e:
        print(f"[Hook] Error procesando pre_tool: {e}", file=sys.stderr)


def handle_post_tool(stdin_data: str):
    """Maneja evento PostToolUse."""
    try:
        data = json.loads(stdin_data)
        tool_name = data.get("tool_name", "unknown")
        result = data.get("result", {})

        # Solo notificar errores
        if result.get("error"):
            send_notification(
                title=f"Error: {tool_name}",
                body=str(result.get("error"))[:200],
                notification_type="info",
                actions=[
                    {"id": "ok", "label": "OK", "hotkey": "enter", "style": "secondary"}
                ],
                timeout_seconds=30
            )

    except Exception as e:
        print(f"[Hook] Error procesando post_tool: {e}", file=sys.stderr)


def handle_notification(stdin_data: str):
    """Maneja notificación directa de Claude Code."""
    try:
        data = json.loads(stdin_data) if stdin_data else {}

        title = data.get("title", "Claude Code")
        body = data.get("body", data.get("message", ""))

        send_notification(
            title=title,
            body=body,
            notification_type=data.get("type", "info"),
            timeout_seconds=data.get("timeout", 60)
        )

    except Exception as e:
        print(f"[Hook] Error procesando notification: {e}", file=sys.stderr)


def test_notification():
    """Envía una notificación de prueba."""
    print("Enviando notificación de prueba...")

    success = send_notification(
        title="Claude Code - Prueba",
        body="Esta es una notificación de prueba del sistema.",
        notification_type="confirmation",
        actions=[
            {"id": "accept", "label": "Aceptar", "hotkey": "enter", "style": "primary"},
            {"id": "cancel", "label": "Cancelar", "hotkey": "escape", "style": "secondary"},
            {"id": "option1", "label": "Opción 1", "hotkey": "1", "style": "secondary"}
        ],
        timeout_seconds=60
    )

    if success:
        print("Notificación enviada correctamente")
    else:
        print("Error al enviar notificación")

    return success


def main():
    parser = argparse.ArgumentParser(description="Claude Code Hook para VoiceFlow")
    parser.add_argument("event", nargs="?", default="test",
                       choices=["pre_tool", "post_tool", "notification", "test"],
                       help="Tipo de evento")
    parser.add_argument("--title", help="Título de la notificación")
    parser.add_argument("--body", help="Cuerpo de la notificación")
    parser.add_argument("--type", default="info", help="Tipo: confirmation, choice, info")

    args = parser.parse_args()

    # Leer stdin si hay datos
    stdin_data = ""
    if not sys.stdin.isatty():
        stdin_data = sys.stdin.read()

    if args.event == "test":
        test_notification()

    elif args.event == "pre_tool":
        handle_pre_tool(stdin_data)

    elif args.event == "post_tool":
        handle_post_tool(stdin_data)

    elif args.event == "notification":
        if args.title:
            send_notification(
                title=args.title,
                body=args.body or "",
                notification_type=args.type
            )
        else:
            handle_notification(stdin_data)


if __name__ == "__main__":
    main()
