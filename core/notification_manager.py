"""
NotificationManager - Orquestador de notificaciones.

Conecta el servidor de eventos, el panel de UI y el operador de acciones.
Opcionalmente envía push notifications via Pushover.
"""

import time
from typing import Optional, Callable, Dict
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal

from core.pushover_client import PushoverClient


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
        sounds=None,
        pushover_client: Optional[PushoverClient] = None,
        tailscale_url: Optional[str] = None
    ):
        super().__init__()

        self.panel = panel
        self.execute_callback = execute_callback
        self.sounds = sounds
        self.pushover = pushover_client
        self.tailscale_url = tailscale_url  # ej: "http://100.x.x.x:8765"

        self._notifications: Dict[str, NotificationState] = {}

        # Conectar panel si existe
        if self.panel:
            self.panel.intent_signal.connect(self._on_panel_intent)
            self.panel.dismiss_signal.connect(self._on_panel_dismiss)
            self.panel.vscode_signal.connect(self._on_panel_vscode)

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

        # Enviar push notification si está configurado
        self._send_push_notification(data)

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

        # Ejecutar (el panel ya ocultó la notificación)
        success = self._execute_intent(intent_data)

        # Actualizar estado interno
        if correlation_id in self._notifications:
            state = self._notifications[correlation_id]
            state.status = "completed" if success else "failed"
            state.executed_at = time.time()
            state.intent = action.get("id", "unknown")

        # Sonido
        if self.sounds:
            sound = "success" if success else "error"
            self.sounds.play(sound)

    def _on_panel_dismiss(self, correlation_id: str):
        """
        Callback cuando el usuario cierra manualmente una notificación.

        No ejecuta ninguna acción, solo actualiza estado.
        """
        if correlation_id in self._notifications:
            state = self._notifications[correlation_id]
            state.status = "dismissed"
            state.executed_at = time.time()

        print(f"[NotificationManager] Dismiss manual: {correlation_id[:12]}...")

    def _on_panel_vscode(self, correlation_id: str):
        """
        Callback cuando el usuario hace click en VS Code.

        Enfoca VS Code sin ejecutar ninguna acción de la notificación.
        """
        print(f"[NotificationManager] VS Code: {correlation_id[:12]}...")

        # Ejecutar acción de ir a VS Code
        if self.execute_callback:
            try:
                # Usamos una acción especial para VS Code
                action = {
                    "id": "vscode",
                    "hotkey": None,  # No enviar hotkey
                    "label": "VS Code"
                }
                self.execute_callback(action)
            except Exception as e:
                print(f"[NotificationManager] Error al ir a VS Code: {e}")

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

    # ========== PUSHOVER ==========

    def _send_push_notification(self, data: dict):
        """
        Envía push notification a iPhone via Pushover.

        Args:
            data: Datos de la notificación
        """
        if not self.pushover or not self.pushover.enabled:
            return

        cid = data.get("correlation_id", "unknown")
        title = data.get("title", "Claude Code")
        message = data.get("message", "Confirmación requerida")

        # Extraer información adicional
        tool_name = data.get("tool_name", "")
        permission_mode = data.get("permission_mode", "")

        # Construir mensaje más informativo
        if tool_name:
            message = f"🔧 {tool_name}\n{message}"

        if permission_mode == "always":
            message = f"{message}\n⚡ Auto-approve disponible"

        # URL para responder (si hay Tailscale configurado)
        url = None
        if self.tailscale_url:
            url = f"{self.tailscale_url}/api/intent"

        # Enviar
        self.pushover.send_notification(
            title=title,
            message=message,
            url=url,
            correlation_id=cid,
            callback=self._on_push_result
        )

    def _on_push_result(self, success: bool, response: str):
        """Callback cuando se completa el envío de push."""
        if not success:
            print(f"[NotificationManager] Push falló: {response}")

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
                state.status = "resolved"
                state.executed_at = time.time()

        # Mostrar feedback visual "resuelto" y luego cerrar
        if self.panel:
            # mark_resolved muestra overlay verde, oculta botones,
            # y elimina la notificación después de 2 segundos
            self.panel.mark_resolved(correlation_id, dismiss_delay_ms=2000)

        print(f"[NotificationManager] Resuelto: {correlation_id[:12]}...")
