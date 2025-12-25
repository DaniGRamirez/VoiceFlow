"""
NotificationManager - Orquestador de notificaciones.

Conecta el servidor de eventos, el panel de UI y el operador de acciones.
Opcionalmente envía push notifications via Pushover.
"""

import time
import hashlib
from typing import Optional, Callable, Dict
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, pyqtSignal

from core.pushover_client import PushoverClient


# Configuración de deduplicación
DEDUP_WINDOW_SECONDS = 10.0  # Ventana de tiempo para considerar duplicados
DEDUP_MAX_ENTRIES = 50  # Máximo de entries en el cache de dedup

# Agrupación de ráfagas: si llegan múltiples notificaciones en este tiempo,
# solo mostrar 1 y auto-aceptar las demás cuando se acepta la primera
BURST_WINDOW_MS = 1000  # 1 segundo

# Límites para cleanup automático
MAX_NOTIFICATIONS = 100  # Máximo de notificaciones en memoria
CLEANUP_AGE_SECONDS = 3600  # Eliminar notificaciones mayores a 1 hora


@dataclass
class NotificationState:
    """Estado de una notificación en el manager."""
    correlation_id: str
    data: dict
    status: str = "pending"
    created_at: float = 0
    executed_at: float = 0
    intent: Optional[str] = None
    dedup_key: str = ""  # Clave para deduplicación


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

        # Cache de deduplicación: dedup_key -> (correlation_id, timestamp)
        self._dedup_cache: Dict[str, tuple] = {}

        # Agrupación de ráfagas: session_id -> [correlation_ids]
        # Cuando se acepta una, se aceptan todas del mismo grupo
        self._burst_groups: Dict[str, list] = {}
        self._last_notification_time: float = 0

        # Conectar panel si existe
        if self.panel:
            self.panel.intent_signal.connect(self._on_panel_intent)
            self.panel.dismiss_signal.connect(self._on_panel_dismiss)
            self.panel.vscode_signal.connect(self._on_panel_vscode)

    def _generate_dedup_key(self, data: dict) -> str:
        """
        Genera una clave única para deduplicación basada en el contenido.

        Usa título + body + tool_name para identificar notificaciones similares.
        Ignora el correlation_id ya que cada acción de agente genera uno nuevo.
        """
        title = data.get("title", "")
        body = data.get("body", "")
        tool_name = data.get("tool_name", "")

        # Crear string normalizado
        content = f"{title}|{body}|{tool_name}".lower().strip()

        # Hash corto para la clave
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _is_duplicate(self, dedup_key: str) -> tuple:
        """
        Verifica si una notificación es duplicada.

        Returns:
            (is_dup, existing_cid): Tuple con bool y correlation_id existente si es dup
        """
        now = time.time()

        # Limpiar entries expiradas del cache
        expired_keys = [
            k for k, (cid, ts) in self._dedup_cache.items()
            if now - ts > DEDUP_WINDOW_SECONDS
        ]
        for k in expired_keys:
            del self._dedup_cache[k]

        # Limitar tamaño del cache
        if len(self._dedup_cache) > DEDUP_MAX_ENTRIES:
            # Eliminar las más antiguas
            sorted_entries = sorted(self._dedup_cache.items(), key=lambda x: x[1][1])
            for k, _ in sorted_entries[:10]:
                del self._dedup_cache[k]

        # Verificar si existe
        if dedup_key in self._dedup_cache:
            existing_cid, ts = self._dedup_cache[dedup_key]
            # Solo es duplicado si la notificación original aún está pendiente
            if existing_cid in self._notifications:
                existing_state = self._notifications[existing_cid]
                if existing_state.status == "pending":
                    return (True, existing_cid)

        return (False, None)

    def on_notification(self, data: dict) -> bool:
        """
        Callback cuando llega una notificación del servidor.

        Args:
            data: Dict con datos de la notificación

        Returns:
            True si la notificación fue aceptada, False si era duplicada
        """
        cid = data.get("correlation_id", "unknown")
        session_id = data.get("session_id", "")
        now = time.time()

        # Generar clave de deduplicación
        dedup_key = self._generate_dedup_key(data)

        # Debug: mostrar qué se usa para dedup
        title = data.get("title", "")
        body = data.get("body", "")

        # Verificar si es duplicada (mismo contenido exacto)
        is_dup, existing_cid = self._is_duplicate(dedup_key)
        if is_dup:
            print(f"[NotificationManager] DUPLICADA IGNORADA: {title} (existente: {existing_cid[:12]}...)")
            return False  # Indica al servidor que no la guarde

        # Detectar ráfaga: si llega dentro de BURST_WINDOW_MS de la anterior
        # y es de la misma sesión, agrupar
        is_burst = False
        time_since_last = (now - self._last_notification_time) * 1000  # en ms

        if session_id and time_since_last < BURST_WINDOW_MS:
            # Es parte de una ráfaga
            if session_id in self._burst_groups and self._burst_groups[session_id]:
                is_burst = True
                self._burst_groups[session_id].append(cid)
                print(f"[NotificationManager] Ráfaga detectada: {title} (grupo={len(self._burst_groups[session_id])} items)")

        # Si no es ráfaga, iniciar nuevo grupo
        if not is_burst and session_id:
            self._burst_groups[session_id] = [cid]

        self._last_notification_time = now

        # Registrar en cache de dedup
        self._dedup_cache[dedup_key] = (cid, now)

        # Guardar estado
        self._notifications[cid] = NotificationState(
            correlation_id=cid,
            data=data,
            status="pending" if not is_burst else "burst_pending",
            created_at=time.time(),
            dedup_key=dedup_key
        )

        # Si es parte de una ráfaga (no la primera), no mostrar UI
        if is_burst:
            print(f"[NotificationManager] Ráfaga silenciosa: {title} (se resolverá con la primera)")
            return True  # Aceptada pero sin UI

        # Reproducir sonido (solo para la primera de la ráfaga)
        if self.sounds:
            try:
                self.sounds.play("notification")
            except Exception:
                self.sounds.play("ding")

        # Mostrar en panel (solo la primera)
        if self.panel:
            # Si hay más en el grupo, indicar cuántas
            burst_count = len(self._burst_groups.get(session_id, []))
            if burst_count > 1:
                data = data.copy()
                data["title"] = f"{data.get('title', '')} (+{burst_count - 1} más)"
            self.panel.add_notification(data)

        # Enviar push notification si está configurado
        self._send_push_notification(data)

        # Cleanup periódico de notificaciones antiguas
        self._cleanup_old_notifications()

        print(f"[NotificationManager] Nueva: {data.get('title', 'Sin título')}")
        return True  # Notificación aceptada

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

            # Resolver también las notificaciones del mismo grupo de ráfaga
            session_id = state.data.get("session_id", "")
            if session_id and session_id in self._burst_groups:
                burst_cids = self._burst_groups[session_id]
                for burst_cid in burst_cids:
                    if burst_cid != correlation_id and burst_cid in self._notifications:
                        burst_state = self._notifications[burst_cid]
                        if burst_state.status == "burst_pending":
                            burst_state.status = "completed"
                            burst_state.executed_at = time.time()
                            print(f"[NotificationManager] Ráfaga resuelta: {burst_cid[:12]}...")
                # Limpiar grupo
                del self._burst_groups[session_id]

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
        self._dedup_cache.clear()
        if self.panel:
            self.panel.clear_all()

    def cancel_notification(self, correlation_id: str):
        """Cancela una notificación sin ejecutar."""
        if correlation_id in self._notifications:
            state = self._notifications[correlation_id]
            state.status = "cancelled"

            # Limpiar del cache de dedup
            if state.dedup_key and state.dedup_key in self._dedup_cache:
                del self._dedup_cache[state.dedup_key]

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

    def _cleanup_old_notifications(self):
        """
        Elimina notificaciones antiguas para evitar memory leaks.

        Se ejecuta automáticamente después de cada nueva notificación.
        """
        now = time.time()

        # Si no hay demasiadas, no hacer nada
        if len(self._notifications) <= MAX_NOTIFICATIONS:
            return

        # Ordenar por created_at (más viejas primero)
        sorted_items = sorted(
            self._notifications.items(),
            key=lambda x: x[1].created_at
        )

        # Calcular cuántas eliminar
        to_remove = len(self._notifications) - MAX_NOTIFICATIONS
        removed = 0

        for cid, state in sorted_items:
            if removed >= to_remove:
                break

            # Solo eliminar si no está pendiente o si es muy antigua
            age = now - state.created_at
            if state.status != "pending" or age > CLEANUP_AGE_SECONDS:
                del self._notifications[cid]

                # Limpiar también del cache de dedup
                if state.dedup_key and state.dedup_key in self._dedup_cache:
                    del self._dedup_cache[state.dedup_key]

                removed += 1

        if removed > 0:
            print(f"[NotificationManager] Cleanup: {removed} notificaciones antiguas eliminadas")
