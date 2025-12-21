#!/usr/bin/env python3
"""
Test de deduplicación de notificaciones.

Simula múltiples notificaciones para verificar que la deduplicación funciona.
"""

import time
import json
from urllib.request import Request, urlopen
import uuid

VOICEFLOW_URL = "http://localhost:8765/api/notification"

def send_notification(title: str, body: str, tool_name: str = "") -> dict:
    """Envía una notificación y retorna la respuesta."""
    payload = {
        "correlation_id": str(uuid.uuid4()),  # Cada una con ID diferente
        "title": title,
        "body": body,
        "tool_name": tool_name,
        "type": "confirmation",
        "actions": [
            {"id": "accept", "label": "Aceptar", "hotkey": "1", "style": "primary"},
            {"id": "cancel", "label": "Cancelar", "hotkey": "escape", "style": "danger"}
        ],
        "source": "test_dedup",
        "timeout_seconds": 60
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            VOICEFLOW_URL,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        response = urlopen(req, timeout=5)
        return json.loads(response.read().decode())
    except Exception as e:
        return {"error": str(e)}


def test_exact_duplicates():
    """Test 1: Notificaciones exactamente iguales."""
    print("\n=== Test 1: Duplicados exactos ===")
    print("Enviando 3 notificaciones idénticas...")

    for i in range(3):
        result = send_notification(
            title="Claude Code - Bash",
            body="$ npm install",
            tool_name="Bash"
        )
        print(f"  [{i+1}] {result}")
        time.sleep(0.5)

    print("Esperado: Solo la primera debería aparecer en el panel")


def test_same_title_different_body():
    """Test 2: Mismo título, diferente body (comandos diferentes)."""
    print("\n=== Test 2: Mismo título, diferente body ===")
    print("Enviando 3 notificaciones con diferente comando...")

    commands = ["$ npm install", "$ npm run build", "$ npm test"]
    for i, cmd in enumerate(commands):
        result = send_notification(
            title="Claude Code - Bash",
            body=cmd,
            tool_name="Bash"
        )
        print(f"  [{i+1}] {cmd} -> {result}")
        time.sleep(0.5)

    print("Esperado: Las 3 deberían aparecer (son diferentes)")


def test_burst_same_notification():
    """Test 3: Ráfaga rápida del mismo contenido."""
    print("\n=== Test 3: Ráfaga rápida (mismo contenido) ===")
    print("Enviando 5 notificaciones idénticas sin delay...")

    for i in range(5):
        result = send_notification(
            title="Claude Code - Write",
            body="Crear archivo: test.py",
            tool_name="Write"
        )
        print(f"  [{i+1}] {result}")

    print("Esperado: Solo la primera debería aparecer")


def check_pending():
    """Verifica cuántas notificaciones pendientes hay."""
    try:
        req = Request("http://localhost:8765/api/status")
        response = urlopen(req, timeout=5)
        data = json.loads(response.read().decode())
        print(f"\nEstado actual: {data.get('pending_count', 0)} pendientes, {data.get('notifications_count', 0)} total")
        return data
    except Exception as e:
        print(f"Error al verificar estado: {e}")
        return {}


def main():
    print("=" * 50)
    print("TEST DE DEDUPLICACIÓN DE NOTIFICACIONES")
    print("=" * 50)
    print("\nAsegúrate de que VoiceFlow esté corriendo (python main.py)")

    input("\nPresiona Enter para comenzar...")

    check_pending()

    test_exact_duplicates()
    time.sleep(2)
    check_pending()

    input("\nPresiona Enter para el siguiente test...")

    test_same_title_different_body()
    time.sleep(2)
    check_pending()

    input("\nPresiona Enter para el siguiente test...")

    test_burst_same_notification()
    time.sleep(2)
    check_pending()

    print("\n" + "=" * 50)
    print("Tests completados. Verifica el panel de notificaciones.")
    print("=" * 50)


if __name__ == "__main__":
    main()
