#!/usr/bin/env python3
"""
Test unitario de deduplicación - no requiere VoiceFlow corriendo.
"""

import sys
sys.path.insert(0, r"c:\Users\danig\OneDrive\Documentos\Proyectos\VoiceFlow")

from core.notification_manager import NotificationManager

def test_dedup():
    print("=== Test Unitario de Deduplicación ===\n")

    # Crear manager sin panel ni callbacks
    manager = NotificationManager(panel=None, execute_callback=None)

    # Test 1: Notificaciones idénticas
    print("Test 1: 3 notificaciones idénticas")
    data1 = {"correlation_id": "id1", "title": "Bash", "body": "$ npm install", "tool_name": "Bash"}
    data2 = {"correlation_id": "id2", "title": "Bash", "body": "$ npm install", "tool_name": "Bash"}
    data3 = {"correlation_id": "id3", "title": "Bash", "body": "$ npm install", "tool_name": "Bash"}

    r1 = manager.on_notification(data1)
    r2 = manager.on_notification(data2)
    r3 = manager.on_notification(data3)

    print(f"  Notif 1: accepted={r1}")
    print(f"  Notif 2: accepted={r2}")
    print(f"  Notif 3: accepted={r3}")
    print(f"  Pendientes: {manager.get_pending_count()}")

    assert r1 == True, "Primera debería ser aceptada"
    assert r2 == False, "Segunda debería ser rechazada (duplicada)"
    assert r3 == False, "Tercera debería ser rechazada (duplicada)"
    assert manager.get_pending_count() == 1, "Solo 1 pendiente"
    print("  ✓ PASS\n")

    # Limpiar
    manager.clear_all()

    # Test 2: Notificaciones diferentes
    print("Test 2: 3 notificaciones diferentes")
    data_a = {"correlation_id": "a1", "title": "Bash", "body": "$ npm install", "tool_name": "Bash"}
    data_b = {"correlation_id": "b1", "title": "Bash", "body": "$ npm build", "tool_name": "Bash"}
    data_c = {"correlation_id": "c1", "title": "Write", "body": "test.py", "tool_name": "Write"}

    ra = manager.on_notification(data_a)
    rb = manager.on_notification(data_b)
    rc = manager.on_notification(data_c)

    print(f"  Notif A (npm install): accepted={ra}")
    print(f"  Notif B (npm build): accepted={rb}")
    print(f"  Notif C (Write): accepted={rc}")
    print(f"  Pendientes: {manager.get_pending_count()}")

    assert ra == True, "A debería ser aceptada"
    assert rb == True, "B debería ser aceptada (diferente body)"
    assert rc == True, "C debería ser aceptada (diferente tool)"
    assert manager.get_pending_count() == 3, "3 pendientes"
    print("  ✓ PASS\n")

    # Test 3: Duplicada después de resolver
    print("Test 3: Duplicada después de resolver la original")
    manager.clear_all()

    data_x = {"correlation_id": "x1", "title": "Bash", "body": "$ test", "tool_name": "Bash"}
    data_y = {"correlation_id": "x2", "title": "Bash", "body": "$ test", "tool_name": "Bash"}

    rx1 = manager.on_notification(data_x)
    print(f"  Primera: accepted={rx1}")

    # Simular que se resolvió
    manager._notifications["x1"].status = "completed"

    rx2 = manager.on_notification(data_y)
    print(f"  Segunda (después de resolver): accepted={rx2}")

    # Ahora debería aceptarse porque la original ya no está pendiente
    assert rx1 == True
    assert rx2 == True, "Debería aceptarse porque la original ya no está pendiente"
    print("  ✓ PASS\n")

    print("=" * 40)
    print("Todos los tests pasaron!")
    print("=" * 40)


if __name__ == "__main__":
    test_dedup()
