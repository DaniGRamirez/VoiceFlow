"""
NotificationPanel - Panel de notificaciones de Claude Code.

Panel flotante always-on-top que muestra notificaciones duplicadas de Claude Code,
posicionado justo encima del overlay de VoiceFlow.
"""

import uuid
import time
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass, field

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint, QSize
)
from PyQt6.QtGui import QFont, QColor


@dataclass
class NotificationAction:
    """Acción disponible en una notificación."""
    id: str
    label: str
    hotkey: str = "enter"
    style: str = "secondary"  # primary, secondary, danger


@dataclass
class Notification:
    """Modelo de notificación."""
    correlation_id: str
    title: str
    body: str
    type: str = "confirmation"  # confirmation, choice, info, input
    actions: List[NotificationAction] = field(default_factory=list)
    source: str = "claude_code"
    timestamp: float = field(default_factory=time.time)
    timeout_seconds: int = 120
    status: str = "pending"  # pending, executing, completed, failed, expired

    @classmethod
    def from_dict(cls, data: dict) -> "Notification":
        """Crea una Notification desde un dict."""
        actions = []
        for a in data.get("actions", []):
            if isinstance(a, dict):
                actions.append(NotificationAction(
                    id=a.get("id", "unknown"),
                    label=a.get("label", a.get("id", "?")),
                    hotkey=a.get("hotkey", "enter"),
                    style=a.get("style", "secondary")
                ))
            elif isinstance(a, str):
                # Formato simple: ["accept", "cancel"]
                actions.append(NotificationAction(
                    id=a,
                    label=a.capitalize(),
                    hotkey="enter" if a == "accept" else "escape",
                    style="primary" if a == "accept" else "secondary"
                ))

        return cls(
            correlation_id=data.get("correlation_id", str(uuid.uuid4())),
            title=data.get("title", "Notificación"),
            body=data.get("body", ""),
            type=data.get("type", "confirmation"),
            actions=actions,
            source=data.get("source", "claude_code"),
            timestamp=data.get("timestamp", time.time()),
            timeout_seconds=data.get("timeout_seconds", 120),
            status=data.get("status", "pending")
        )


class NotificationWidget(QFrame):
    """Widget individual para una notificación."""

    # Signal: (correlation_id, action_dict)
    action_clicked = pyqtSignal(str, dict)

    # Estilos de botón
    BUTTON_STYLES = {
        "primary": """
            QPushButton {
                background-color: #2D7D46;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #3D9D56;
            }
            QPushButton:pressed {
                background-color: #1D6D36;
            }
        """,
        "secondary": """
            QPushButton {
                background-color: #3a3a3a;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                color: white;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """,
        "danger": """
            QPushButton {
                background-color: #8B3A3A;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #A54A4A;
            }
            QPushButton:pressed {
                background-color: #6B2A2A;
            }
        """
    }

    def __init__(self, notification: Notification, parent=None):
        super().__init__(parent)
        self.notification = notification
        self._setup_ui()

    def _setup_ui(self):
        """Configura la UI del widget."""
        self.setStyleSheet("""
            NotificationWidget {
                background-color: rgba(25, 25, 25, 245);
                border: 1px solid #404040;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Título
        title_label = QLabel(self.notification.title)
        title_label.setStyleSheet("""
            color: #ffffff;
            font-family: 'Segoe UI';
            font-size: 12px;
            font-weight: 600;
            background: transparent;
        """)
        layout.addWidget(title_label)

        # Cuerpo (si existe)
        if self.notification.body:
            body_label = QLabel(self.notification.body)
            body_label.setStyleSheet("""
                color: #aaaaaa;
                font-family: 'Segoe UI';
                font-size: 11px;
                background: transparent;
            """)
            body_label.setWordWrap(True)
            layout.addWidget(body_label)

        # Botones de acciones
        if self.notification.actions:
            buttons_layout = QHBoxLayout()
            buttons_layout.setSpacing(8)
            buttons_layout.addStretch()

            for action in self.notification.actions:
                btn = QPushButton(action.label)
                style = self.BUTTON_STYLES.get(action.style, self.BUTTON_STYLES["secondary"])
                btn.setStyleSheet(style)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)

                # Conectar click
                btn.clicked.connect(
                    lambda checked, a=action: self._on_action_click(a)
                )
                buttons_layout.addWidget(btn)

            layout.addLayout(buttons_layout)

        # Tamaño fijo
        self.setMinimumWidth(280)
        self.setMaximumWidth(350)

    def _on_action_click(self, action: NotificationAction):
        """Emite signal cuando se hace click en una acción."""
        action_dict = {
            "id": action.id,
            "label": action.label,
            "hotkey": action.hotkey,
            "style": action.style
        }
        self.action_clicked.emit(self.notification.correlation_id, action_dict)

    def set_status(self, status: str):
        """Actualiza el estado visual de la notificación."""
        self.notification.status = status

        if status == "executing":
            self.setStyleSheet("""
                NotificationWidget {
                    background-color: rgba(45, 45, 25, 245);
                    border: 1px solid #6a6a3a;
                    border-radius: 8px;
                }
            """)
        elif status == "completed":
            self.setStyleSheet("""
                NotificationWidget {
                    background-color: rgba(25, 45, 25, 245);
                    border: 1px solid #3a6a3a;
                    border-radius: 8px;
                }
            """)
        elif status == "failed":
            self.setStyleSheet("""
                NotificationWidget {
                    background-color: rgba(45, 25, 25, 245);
                    border: 1px solid #6a3a3a;
                    border-radius: 8px;
                }
            """)


class NotificationPanel(QWidget):
    """
    Panel flotante que muestra notificaciones de Claude Code.

    Posicionado encima del overlay de VoiceFlow.
    """

    # Signal: (correlation_id, action_dict)
    intent_signal = pyqtSignal(str, dict)

    # Signal interno para thread-safety
    _add_notification_signal = pyqtSignal(dict)
    _remove_notification_signal = pyqtSignal(str)
    _update_status_signal = pyqtSignal(str, str)

    def __init__(self, overlay_widget=None, margin_top: int = 80, max_visible: int = 3):
        super().__init__(None, Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool |
                         Qt.WindowType.WindowDoesNotAcceptFocus)

        self.overlay_widget = overlay_widget
        self.margin_top = margin_top
        self.max_visible = max_visible

        self._notifications: Dict[str, NotificationWidget] = {}
        self._notification_order: List[str] = []

        self._setup_ui()
        self._connect_signals()

        # Timer para actualizar posición si el overlay se mueve
        self._position_timer = QTimer()
        self._position_timer.timeout.connect(self._update_position)
        self._position_timer.start(500)

    def _setup_ui(self):
        """Configura la UI del panel."""
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        # Container para notificaciones
        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(8)
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        self._layout.addWidget(self._container)

        # Tamaño inicial
        self.setFixedWidth(360)
        self.hide()  # Oculto hasta que haya notificaciones

    def _connect_signals(self):
        """Conecta signals internos para thread-safety."""
        self._add_notification_signal.connect(self._do_add_notification)
        self._remove_notification_signal.connect(self._do_remove_notification)
        self._update_status_signal.connect(self._do_update_status)

    def _update_position(self):
        """Actualiza posición del panel encima del overlay."""
        if not self.overlay_widget or not self.isVisible():
            return

        # Obtener posición del overlay
        overlay_pos = self.overlay_widget.pos()
        overlay_width = self.overlay_widget.width()

        # Centrar horizontalmente sobre el overlay
        panel_width = self.width()
        x = overlay_pos.x() + (overlay_width - panel_width) // 2

        # Posicionar encima del overlay con margen
        y = overlay_pos.y() - self.height() - self.margin_top

        # Asegurar que no se salga de la pantalla
        if y < 10:
            y = 10

        self.move(x, y)

    # ========== API PÚBLICA (thread-safe) ==========

    def add_notification(self, notification_data: dict):
        """
        Añade una notificación al panel.

        Args:
            notification_data: Dict con campos de notificación
        """
        self._add_notification_signal.emit(notification_data)

    def remove_notification(self, correlation_id: str):
        """Elimina una notificación del panel."""
        self._remove_notification_signal.emit(correlation_id)

    def update_status(self, correlation_id: str, status: str):
        """Actualiza el estado de una notificación."""
        self._update_status_signal.emit(correlation_id, status)

    # ========== SLOTS INTERNOS ==========

    def _do_add_notification(self, data: dict):
        """Slot: añade notificación (ejecuta en main thread)."""
        notification = Notification.from_dict(data)

        # Si ya existe, actualizar
        if notification.correlation_id in self._notifications:
            self._do_remove_notification(notification.correlation_id)

        # Crear widget
        widget = NotificationWidget(notification)
        widget.action_clicked.connect(self._on_action_clicked)

        # Añadir al layout
        self._container_layout.addWidget(widget)
        self._notifications[notification.correlation_id] = widget
        self._notification_order.append(notification.correlation_id)

        # Limitar número visible
        while len(self._notification_order) > self.max_visible:
            oldest_id = self._notification_order.pop(0)
            self._do_remove_notification(oldest_id)

        # Ajustar tamaño y mostrar
        self.adjustSize()
        self._update_position()
        self.show()

        print(f"[NotificationPanel] Añadida: {notification.title}")

        # Auto-remove después de timeout
        timeout_ms = notification.timeout_seconds * 1000
        QTimer.singleShot(timeout_ms, lambda: self._on_timeout(notification.correlation_id))

    def _do_remove_notification(self, correlation_id: str):
        """Slot: elimina notificación."""
        if correlation_id not in self._notifications:
            return

        widget = self._notifications.pop(correlation_id)
        if correlation_id in self._notification_order:
            self._notification_order.remove(correlation_id)

        # Animar salida
        self._container_layout.removeWidget(widget)
        widget.deleteLater()

        # Ocultar panel si no hay más notificaciones
        if not self._notifications:
            self.hide()
        else:
            self.adjustSize()
            self._update_position()

        print(f"[NotificationPanel] Eliminada: {correlation_id}")

    def _do_update_status(self, correlation_id: str, status: str):
        """Slot: actualiza estado de notificación."""
        if correlation_id in self._notifications:
            self._notifications[correlation_id].set_status(status)

    def _on_action_clicked(self, correlation_id: str, action: dict):
        """Callback cuando se hace click en una acción."""
        print(f"[NotificationPanel] Acción: {action['id']} en {correlation_id}")

        # Marcar como ejecutando
        self.update_status(correlation_id, "executing")

        # Emitir intent
        self.intent_signal.emit(correlation_id, action)

    def _on_timeout(self, correlation_id: str):
        """Callback cuando expira el timeout de una notificación."""
        if correlation_id in self._notifications:
            widget = self._notifications[correlation_id]
            if widget.notification.status == "pending":
                print(f"[NotificationPanel] Timeout: {correlation_id}")
                self.update_status(correlation_id, "expired")
                # Eliminar después de un momento
                QTimer.singleShot(2000, lambda: self.remove_notification(correlation_id))

    # ========== MÉTODOS DE CONVENIENCIA ==========

    def clear_all(self):
        """Elimina todas las notificaciones."""
        for cid in list(self._notifications.keys()):
            self.remove_notification(cid)

    @property
    def notification_count(self) -> int:
        """Número de notificaciones activas."""
        return len(self._notifications)

    def has_pending(self) -> bool:
        """True si hay notificaciones pendientes."""
        return any(
            w.notification.status == "pending"
            for w in self._notifications.values()
        )
