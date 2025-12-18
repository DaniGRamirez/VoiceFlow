"""
VoiceFlow Overlay - El Organismo

Un ente vivo que escucha, reacciona y responde.
No es una interfaz, es una presencia.
"""

import math
import sys
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QApplication, QWidget, QMenu, QGraphicsDropShadowEffect,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QPoint, QPointF,
    QPropertyAnimation, QEasingCurve, QRectF
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPainterPath,
    QRadialGradient, QFont
)

from core.state import State
from config.settings import save_config, load_config
from ui.easing import (
    breathing_factor, organic_noise, lerp_smooth,
    ease_out_elastic, ease_out_back, micro_vibration
)


class Overlay(QWidget):
    """
    El organismo vivo que representa VoiceFlow.

    Principios:
    - Nada aparece de golpe
    - Nada desaparece sin despedirse
    - Todo tiene inercia
    - La UI no manda: responde
    """

    # Signals para comunicación thread-safe
    state_signal = pyqtSignal(object)
    flash_signal = pyqtSignal(str, int)
    mic_level_signal = pyqtSignal(float)

    # Paleta de colores (temperaturas, no señales)
    COLORS = {
        State.IDLE: ("#555555", "#666666"),      # Gris cálido
        State.DICTATING: ("#C0392B", "#E74C3C"),  # Rojo vivo
        State.PROCESSING: ("#8B7355", "#9A8262"), # Tierra pensativo
    }

    SUCCESS_COLOR = "#2D5A27"  # Verde muy oscuro, sutil
    ERROR_COLOR = "#5A2727"    # Rojo muy oscuro, sutil

    def __init__(self, size: int = 40, position: tuple = (1850, 50), opacity: float = 0.9):
        # Crear QApplication si no existe
        if QApplication.instance() is None:
            self._app = QApplication(sys.argv)
        else:
            self._app = QApplication.instance()

        super().__init__()

        # Configuración base
        self._base_size = size
        self._current_size = float(size)
        self._target_size = float(size)
        self._display_size = float(size)
        self._opacity = opacity
        self._position = position

        # Estado del organismo
        self._state = State.IDLE
        self._prev_state = State.IDLE

        # Animación
        self._time = 0.0
        self._phase = 0.0
        self._mic_level = 0.0
        self._smoothed_mic = 0.0
        self._size_velocity = 0.0

        # Color actual (para transiciones)
        self._current_color = QColor("#555555")
        self._target_color = QColor("#555555")

        # Flash
        self._flash_active = False
        self._flash_color = None

        # Transición de estado
        self._transition_progress = 1.0

        # Spores (pop-ups) activos
        self._spores = []

        # Hints
        self._hint_window = None
        self._on_listo_callback = None
        self._on_cancela_callback = None

        # Drag
        self._drag_pos = None

        # Setup
        self._setup_window()
        self._setup_shadow()
        self._connect_signals()
        self._start_animation()

    def _setup_window(self):
        """Configura la ventana transparente."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(self._opacity)

        # Margen amplio para glow y expansión del núcleo
        # El núcleo puede crecer hasta base_size + 15px, y el glow es 1.4x
        self._margin = 40
        total_size = self._base_size + self._margin * 2
        self.setFixedSize(total_size, total_size)
        self.move(self._position[0], self._position[1])

        self.show()

    def _setup_shadow(self):
        """La sombra se dibuja manualmente en paintEvent para evitar conflictos con WA_TranslucentBackground."""
        # No usar QGraphicsDropShadowEffect - causa UpdateLayeredWindowIndirect errors en Windows
        pass

    def _connect_signals(self):
        """Conecta signals para comunicación thread-safe."""
        self.state_signal.connect(self._on_state_change)
        self.flash_signal.connect(self._on_flash)
        self.mic_level_signal.connect(self._on_mic_level)

    def _start_animation(self):
        """Inicia el loop de animación (60 FPS)."""
        self._timer = QTimer()
        self._timer.timeout.connect(self._animate)
        self._timer.start(16)  # ~60 FPS

    # ========== ANIMACIÓN ==========

    def _animate(self):
        """Loop principal de animación - el organismo respira."""
        dt = 0.016  # ~60 FPS
        self._time += dt
        self._phase += dt

        # Suavizar nivel de micrófono (inercia)
        self._smoothed_mic = lerp_smooth(self._smoothed_mic, self._mic_level, 0.15)

        # Calcular tamaño objetivo según estado
        if self._state == State.DICTATING:
            # Se hincha con el audio
            self._target_size = self._base_size + self._smoothed_mic * 15
        elif self._state == State.PROCESSING:
            # Ligeramente contraído
            self._target_size = self._base_size * 0.95
        else:
            self._target_size = self._base_size

        # Interpolación elástica del tamaño
        diff = self._target_size - self._current_size
        self._size_velocity = self._size_velocity * 0.85 + diff * 0.15
        self._current_size += self._size_velocity

        # Respiración base
        breath = breathing_factor(self._time, rate=0.4, amplitude=0.025)
        self._display_size = self._current_size * breath

        # Avanzar transición de color
        if self._transition_progress < 1.0:
            self._transition_progress = min(1.0, self._transition_progress + dt * 2.5)

        # Calcular color actual
        if not self._flash_active:
            self._update_color()

        # Redibujar
        self.update()

    def _update_color(self):
        """Actualiza el color según el estado actual."""
        colors = self.COLORS.get(self._state, self.COLORS[State.IDLE])
        base_color = QColor(colors[0])
        light_color = QColor(colors[1])

        # Pulso de color según estado
        if self._state == State.IDLE:
            # Pulso muy lento
            factor = (math.sin(self._phase * 0.5) + 1) / 2
        elif self._state == State.DICTATING:
            # Pulso más rápido + respuesta al mic
            base_factor = (math.sin(self._phase * 2) + 1) / 2
            factor = min(1.0, base_factor * 0.4 + self._smoothed_mic * 0.6)
        else:
            # PROCESSING - pulso medio
            factor = (math.sin(self._phase * 1.5) + 1) / 2

        # Interpolar entre base y light
        r = int(base_color.red() + (light_color.red() - base_color.red()) * factor)
        g = int(base_color.green() + (light_color.green() - base_color.green()) * factor)
        b = int(base_color.blue() + (light_color.blue() - base_color.blue()) * factor)

        target = QColor(r, g, b)

        # Transición suave si estamos cambiando de estado
        if self._transition_progress < 1.0:
            self._current_color = self._blend_colors(
                self._current_color, target, self._transition_progress
            )
        else:
            self._current_color = target

    def _blend_colors(self, c1: QColor, c2: QColor, factor: float) -> QColor:
        """Mezcla dos colores."""
        r = int(c1.red() + (c2.red() - c1.red()) * factor)
        g = int(c1.green() + (c2.green() - c1.green()) * factor)
        b = int(c1.blue() + (c2.blue() - c1.blue()) * factor)
        return QColor(r, g, b)

    # ========== DIBUJO ==========

    def paintEvent(self, event):
        """Dibuja el organismo."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Centro del widget
        center = self.rect().center()
        cx, cy = center.x(), center.y()

        # Radio actual
        radius = self._display_size / 2

        # Color a usar
        if self._flash_active and self._flash_color:
            fill_color = self._flash_color
        else:
            fill_color = self._current_color

        # Sombra difusa (dibujada manualmente)
        self._draw_shadow(painter, cx, cy + 3, radius)

        # Glow (halo) en estado DICTATING
        if self._state == State.DICTATING and not self._flash_active:
            self._draw_glow(painter, cx, cy, radius)

        # Dibujar el círculo orgánico
        self._draw_organic_circle(painter, cx, cy, radius, fill_color)

    def _draw_shadow(self, painter: QPainter, cx: float, cy: float, radius: float):
        """Dibuja sombra difusa debajo del núcleo."""
        shadow_radius = radius * 1.15
        gradient = QRadialGradient(cx, cy, shadow_radius)
        gradient.setColorAt(0, QColor(0, 0, 0, 40))
        gradient.setColorAt(0.6, QColor(0, 0, 0, 20))
        gradient.setColorAt(1, QColor(0, 0, 0, 0))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), shadow_radius, shadow_radius)

    def _draw_glow(self, painter: QPainter, cx: float, cy: float, radius: float):
        """Dibuja el halo difuso en grabación."""
        glow_radius = radius * 1.4
        gradient = QRadialGradient(cx, cy, glow_radius)

        # Color del glow basado en el nivel de mic
        intensity = int(40 + self._smoothed_mic * 60)
        gradient.setColorAt(0, QColor(231, 76, 60, intensity))
        gradient.setColorAt(0.5, QColor(231, 76, 60, int(intensity * 0.3)))
        gradient.setColorAt(1, QColor(231, 76, 60, 0))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_radius, glow_radius)

    def _draw_organic_circle(self, painter: QPainter, cx: float, cy: float,
                             radius: float, color: QColor):
        """Dibuja el círculo con deformación orgánica."""
        path = QPainterPath()
        num_points = 36

        for i in range(num_points + 1):
            angle = (i / num_points) * 2 * math.pi

            # Deformación orgánica del borde
            if self._state == State.DICTATING:
                # Más deformación durante grabación
                noise = organic_noise(angle, self._time, scale=3.0, amplitude=0.03)
            else:
                # Deformación sutil en idle
                noise = organic_noise(angle, self._time, scale=2.0, amplitude=0.015)

            r = radius * noise

            x = cx + math.cos(angle) * r
            y = cy + math.sin(angle) * r

            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        path.closeSubpath()

        # Rellenar
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor("#222222"), 1))
        painter.drawPath(path)

    # ========== API THREAD-SAFE ==========

    def set_state(self, state: State):
        """Thread-safe: cambia el estado del organismo."""
        self.state_signal.emit(state)

    def flash(self, color: str, duration_ms: int = 200):
        """Thread-safe: flash de color."""
        self.flash_signal.emit(color, duration_ms)

    def flash_success(self):
        self.flash(self.SUCCESS_COLOR, 200)

    def flash_error(self):
        self.flash(self.ERROR_COLOR, 200)

    def flash_unknown(self):
        """Flash sutil para comando no reconocido."""
        self.flash("#4A4A4A", 150)

    def set_mic_level(self, level: float):
        """Thread-safe: actualiza nivel de micrófono (0.0 - 1.0)."""
        self.mic_level_signal.emit(min(1.0, max(0.0, level)))

    # ========== SLOTS ==========

    def _on_state_change(self, state: State):
        """Slot: procesa cambio de estado."""
        if state != self._state:
            self._prev_state = self._state
            self._state = state
            self._transition_progress = 0.0

            # Mostrar/ocultar hints
            if state == State.DICTATING:
                self.show_hints()
            elif self._prev_state == State.DICTATING:
                self.hide_hints()

    def _on_flash(self, color: str, duration_ms: int):
        """Slot: procesa flash de color."""
        self._flash_active = True
        self._flash_color = QColor(color)
        QTimer.singleShot(duration_ms, self._end_flash)

    def _end_flash(self):
        """Termina el flash."""
        self._flash_active = False
        self._flash_color = None

    def _on_mic_level(self, level: float):
        """Slot: actualiza nivel de mic."""
        self._mic_level = level

    # ========== DRAG & DROP ==========

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ========== MENÚ CONTEXTUAL ==========

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1a1a1a;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 8px;
            }
            QMenu::item {
                padding: 8px 24px;
                color: #888;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2a2a2a;
                color: #ccc;
            }
            QMenu::separator {
                height: 1px;
                background: #333;
                margin: 4px 8px;
            }
        """)

        # Estado actual
        state_names = {
            State.IDLE: "Escuchando",
            State.DICTATING: "Absorbiendo",
            State.PROCESSING: "Pensando"
        }
        state_action = menu.addAction(f"● {state_names.get(self._state, 'Unknown')}")
        state_action.setEnabled(False)

        menu.addSeparator()

        # Submenú transparencia
        opacity_menu = menu.addMenu("Transparencia")
        for val in [0.5, 0.7, 0.9, 1.0]:
            action = opacity_menu.addAction(f"{int(val*100)}%")
            action.triggered.connect(lambda checked, v=val: self._set_opacity(v))

        # Submenú tamaño
        size_menu = menu.addMenu("Tamaño")
        for size in [30, 40, 50, 60]:
            action = size_menu.addAction(f"{size}px")
            action.triggered.connect(lambda checked, s=size: self._set_size(s))

        menu.addSeparator()

        # Guardar posición
        save_action = menu.addAction("Guardar posición")
        save_action.triggered.connect(self._save_position)

        # Salir
        quit_action = menu.addAction("Salir")
        quit_action.triggered.connect(self.quit)

        menu.exec(event.globalPos())

    def _set_opacity(self, opacity: float):
        self._opacity = opacity
        self.setWindowOpacity(opacity)

    def _set_size(self, size: int):
        self._base_size = size
        self._current_size = float(size)
        self._target_size = float(size)

    def _save_position(self):
        """Guarda la posición actual en config.json."""
        pos = (self.x(), self.y())
        config = load_config()
        config["overlay"]["position"] = list(pos)
        config["overlay"]["size"] = self._base_size
        config["overlay"]["opacity"] = self._opacity
        save_config(config)
        print(f"[UI] Configuración guardada: pos={pos}, size={self._base_size}")

    # ========== HINTS ==========

    def set_hint_callbacks(self, on_listo: Callable, on_cancela: Callable):
        """Configura callbacks para los hints."""
        self._on_listo_callback = on_listo
        self._on_cancela_callback = on_cancela

    def show_hints(self):
        """Muestra los hints de listo/cancela."""
        if self._hint_window:
            return

        self._hint_window = QWidget(None, Qt.WindowType.FramelessWindowHint |
                                    Qt.WindowType.WindowStaysOnTopHint |
                                    Qt.WindowType.Tool)
        self._hint_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._hint_window.setWindowOpacity(0.95)

        layout = QVBoxLayout(self._hint_window)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Frame contenedor
        frame = QWidget()
        frame.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-radius: 12px;
            }
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 8, 12, 10)
        frame_layout.setSpacing(8)

        # Título
        title = QLabel("Absorbiendo...")
        title.setStyleSheet("color: #E74C3C; font-size: 11px; font-weight: 500;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(title)

        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        listo_btn = QPushButton("listo")
        listo_btn.setStyleSheet("""
            QPushButton {
                background-color: #27AE60;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2ECC71;
            }
        """)
        listo_btn.clicked.connect(self._on_hint_listo)
        btn_layout.addWidget(listo_btn)

        cancela_btn = QPushButton("cancela")
        cancela_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #C0392B;
            }
        """)
        cancela_btn.clicked.connect(self._on_hint_cancela)
        btn_layout.addWidget(cancela_btn)

        frame_layout.addLayout(btn_layout)
        layout.addWidget(frame)

        # Posicionar debajo del overlay
        x = self.x() - 30
        y = self.y() + self.height() + 8
        self._hint_window.move(x, y)
        self._hint_window.show()

    def hide_hints(self):
        """Oculta los hints."""
        if self._hint_window:
            self._hint_window.close()
            self._hint_window = None

    def _on_hint_listo(self):
        if self._on_listo_callback:
            self._on_listo_callback()

    def _on_hint_cancela(self):
        if self._on_cancela_callback:
            self._on_cancela_callback()

    # ========== UTILIDADES ==========

    def get_position(self) -> tuple:
        return (self.x(), self.y())

    def update(self):
        """Fuerza repintado."""
        super().update()

    def quit(self):
        """Cierra el overlay."""
        self.hide_hints()
        self.close()
        if self._app:
            self._app.quit()
