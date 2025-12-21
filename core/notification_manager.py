"""
NotificationManager - Orquestador de notificaciones.

Conecta el servidor de eventos, el panel de UI y el operador de acciones.
"""

import time
from typing import Optional, Callable, Dict
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class NotificationState:
    """Estado de una notificación en el manager."""
    correlation_id: str
    data: dict
    status: str = "pending"
    created_at: float = 0
    executed_at: float = 0
    intent: Optional[str] = None


class NotificationManager(QObject):
    """
    Gestor del ciclo de vida de notificaciones.

    Conecta:
    - EventServer (recibe notificaciones)
    - NotificationPanel (muestra UI)
    - Actions (ejecuta intents en VS Code)

    Uso:
        manager = NotificationManager(
            panel=notification_panel,
            execute_callback=actions.execute_notification_intent
        )
        server = EventServer(
            on_notification=manager.on_notification,
            on_intent=manager.on_intent
        )
    """

    # Signals para actualizar UI desde cualquier thread
    notification_received = pyqtSignal(dict)
    intent_executed = pyqtSignal(str, str)  # correlation_id, status

    def __init__(
        self,
        panel=None,
        execute_callback: Optional[Callable[[dict], bool]] = None,
        sounds=None
    ):
        super().__init__()

        self.panel = panel
        self.execute_callback = execute_callback
        self.sounds = sounds

        self._notifications: Dict[str, NotificationState] = {}

        # Conectar panel si existe
        if self.panel:
            self.panel.intent_signal.connect(self._on_panel_intent)

    def on_notification(self, data: dict):
        """
        Callback cuando llega una notificación del servidor.

        Args:
            data: Dict con datos de la notificación
        """
        cid = data.get("correlation_id", "unknown")

        # Guardar estado
        self._notifications[cid] = NotificationState(
            correlation_id=cid,
            data=data,
            status="pending",
            created_at=time.time()
        )

        # Reproducir sonido
        if self.sounds:
            try:
                self.sounds.play("notification")
            except:
                self.sounds.play("ding")

        # Mostrar en panel
        if self.panel:
            self.panel.add_notification(data)

        print(f"[NotificationManager] Nueva: {data.get('title', 'Sin título')}")

    def on_intent(self, intent_data: dict):
        """
        Callback cuando se recibe un intent desde el servidor.

        Args:
            intent_data: Dict con correlation_id, intent, hotkey, source
        """
        cid = intent_data.get("correlation_id", "")
        intent = intent_data.get("intent", "")

        if cid not in self._notifications:
            print(f"[NotificationManager] Intent para notificación desconocida: {cid}")
            return

        state = self._notifications[cid]

        # Ejecutar intent
        success = self._execute_intent(intent_data)

        # Actualizar estado
        state.status = "completed" if success else "failed"
        state.executed_at = time.time()
        state.intent = intent

        # Actualizar panel
        if self.panel:
            self.panel.update_status(cid, state.status)

        # Sonido
        if self.sounds:
            sound = "success" if success else "error"
            self.sounds.play(sound)

        # Eliminar después de un momento
        if self.panel:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.panel.remove_notification(cid))

    def _on_panel_intent(self, correlation_id: str, action: dict):
        """
        Callback cuando el usuario hace click en un botón del panel.

        Args:
            correlation_id: ID de la notificación
            action: Dict con id, label, hotkey, style
        """
        intent_data = {
            "correlation_id": correlation_id,
            "intent": action.get("id", "unknown"),
            "hotkey": action.get("hotkey", "enter"),
            "source": "overlay"
        }

        # Ejecutar
        self.on_intent(intent_data)

    def _execute_intent(self, intent_data: dict) -> bool:
        """
        Ejecuta el intent en VS Code.

        Args:
            intent_data: Dict con datos del intent

        Returns:
            True si tuvo éxito
        """
        if not self.execute_callback:
            print("[NotificationManager] No hay callback de ejecución configurado")
            return False

        try:
            # Preparar acción
            action = {
                "id": intent_data.get("intent", "unknown"),
                "hotkey": intent_data.get("hotkey", "enter"),
                "label": intent_data.get("intent", "unknown")
            }

            # Ejecutar
            result = self.execute_callback(action)
            return result if result is not None else True

        except Exception as e:
            print(f"[NotificationManager] Error ejecutando intent: {e}")
            return False

    # ========== API PÚBLICA ==========

    def get_notification(self, correlation_id: str) -> Optional[NotificationState]:
        """Obtiene el estado de una notificación."""
        return self._notifications.get(correlation_id)

    def get_pending_count(self) -> int:
        """Número de notificaciones pendientes."""
        return sum(1 for n in self._notifications.values() if n.status == "pending")

    def clear_all(self):
        """Elimina todas las notificaciones."""
        self._notifications.clear()
        if self.panel:
            self.panel.clear_all()

    def cancel_notification(self, correlation_id: str):
        """Cancela una notificación sin ejecutar."""
        if correlation_id in self._notifications:
            state = self._notifications[correlation_id]
            state.status = "cancelled"

            if self.panel:
                self.panel.update_status(correlation_id, "cancelled")
                self.panel.remove_notification(correlation_id)

    def on_dismiss(self, correlation_id: str):
        """
        Callback cuando se recibe un dismiss (ej. desde transcript watcher).

        Esto ocurre cuando el usuario confirmó en VSCode y la herramienta
        se completó, pero la notificación en VoiceFlow sigue activa.

        Args:
            correlation_id: ID de la notificación a cerrar
        """
        # Actualizar estado interno
        if correlation_id in self._notifications:
            state = self._notifications[correlation_id]
            if state.status == "pending":
                state.status = "dismissed"
                state.executed_at = time.time()

        # Cerrar en el panel
        if self.panel:
            self.panel.remove_notification(correlation_id)

        print(f"[NotificationManager] Dismiss: {correlation_id[:12]}...")
