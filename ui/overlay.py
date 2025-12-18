"""
VoiceFlow Overlay - El Organismo

Un ente vivo que escucha, reacciona y responde.
No es una interfaz, es una presencia.
"""

import math
import sys
import random
from typing import Optional, Callable, List

from PyQt6.QtWidgets import (
    QApplication, QWidget, QMenu,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QPointF, QRectF
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPainterPath,
    QRadialGradient, QLinearGradient, QFont
)

from core.state import State
from config.settings import save_config, load_config
from ui.easing import (
    breathing_factor, organic_noise, lerp_smooth,
    ease_out_elastic, ease_out_back, micro_vibration,
    lava_deformation, squash_stretch, lerp
)


class Spore:
    """Pop-up orgánico que emerge del núcleo."""

    def __init__(self, text: str, start_y: float, end_y: float, center_x: float,
                 duration: float = 2.0, is_command: bool = False):
        self.text = text
        self.center_x = center_x
        self.start_y = start_y
        self.end_y = end_y
        self.duration = duration
        self.is_command = is_command

        self.age = 0.0
        self.scale = 0.0
        self.opacity = 0.0
        self.y = start_y

        # Tiempos de cada fase - comandos más rápidos, textos más lentos
        self.appear_time = 0.25  # 250ms para aparecer
        if is_command:
            self.hold_time = 1.0     # Comandos: 1s visible
        else:
            self.hold_time = 2.0     # Textos reconocidos: 2s visible
        self.fade_time = 0.5    # 500ms para desvanecer

    def update(self, dt: float) -> bool:
        """Actualiza el spore. Retorna False si debe eliminarse."""
        self.age += dt

        total = self.appear_time + self.hold_time + self.fade_time
        if self.age >= total:
            return False

        # Fase de aparición (crecer + mover hacia abajo)
        if self.age < self.appear_time:
            t = self.age / self.appear_time
            self.scale = ease_out_back(t, 1.3)
            self.opacity = t
            # Mover de start_y a end_y durante aparición
            self.y = self.start_y + (self.end_y - self.start_y) * ease_out_back(t, 1.0)

        # Fase estable (quieto, visible)
        elif self.age < self.appear_time + self.hold_time:
            self.scale = 1.0
            self.opacity = 1.0
            self.y = self.end_y  # Quedarse en posición final

        # Fase de desvanecimiento (solo fade, sin mover)
        else:
            fade_t = (self.age - self.appear_time - self.hold_time) / self.fade_time
            self.scale = 1.0  # Mantener tamaño
            self.opacity = 1.0 - fade_t
            self.y = self.end_y  # No moverse

        return True


class Overlay(QWidget):
    """
    El organismo vivo que representa VoiceFlow.

    Estados:
    - IDLE: Óvalo negro pequeño con borde plateado, deformación tipo lava
    - DICTATING: Círculo rojizo, el mic deforma la forma significativamente
    - PROCESSING: Contraído, micro-vibraciones
    """

    # Signals para comunicación thread-safe
    state_signal = pyqtSignal(object)
    flash_signal = pyqtSignal(str, int)
    mic_level_signal = pyqtSignal(float)
    spore_signal = pyqtSignal(str, bool)  # texto, es_comando
    help_signal = pyqtSignal(list)  # lista de (comando, descripcion)

    # Colores
    IDLE_FILL = "#0a0a0a"  # Negro profundo
    IDLE_BORDER = "#8a8a8a"  # Plateado
    DICTATING_FILL = ("#B83227", "#E74C3C")  # Rojo cálido
    PROCESSING_FILL = "#1a1a1a"  # Gris muy oscuro
    PAUSED_FILL = "#8B7500"  # Amarillo oscuro/dorado
    PAUSED_BORDER = "#D4AA00"  # Dorado brillante

    SUCCESS_COLOR = "#2D5A27"
    ERROR_COLOR = "#5A2727"

    def __init__(self, size: int = 40, position: tuple = (1850, 50), opacity: float = 0.9):
        # Crear QApplication si no existe
        if QApplication.instance() is None:
            self._app = QApplication(sys.argv)
        else:
            self._app = QApplication.instance()

        super().__init__()

        # Configuración base
        self._base_size = size
        self._idle_size = size * 0.5  # Más pequeño en IDLE (era 0.7)
        self._current_size = float(self._idle_size)
        self._target_size = float(self._idle_size)
        self._display_size = float(self._idle_size)
        self._opacity = opacity
        self._position = position

        # Forma (1.0 = círculo, >1 = óvalo horizontal)
        self._current_squash = 2.2  # Óvalo más aplanado en IDLE (era 1.6)
        self._target_squash = 2.2

        # Estado del organismo
        self._state = State.IDLE
        self._prev_state = State.IDLE

        # Animación
        self._time = 0.0
        self._phase = 0.0
        self._mic_level = 0.0
        self._smoothed_mic = 0.0
        self._size_velocity = 0.0
        self._squash_velocity = 0.0

        # Color actual (para transiciones)
        self._current_color = QColor(self.IDLE_FILL)
        self._border_color = QColor(self.IDLE_BORDER)
        self._border_opacity = 1.0

        # Flash
        self._flash_active = False
        self._flash_color = None
        self._flash_progress = 0.0

        # Transición de estado - momento de cambio visible
        self._transition_progress = 1.0
        self._transition_flash = 0.0  # Flash blanco al cambiar

        # Spores (pop-ups)
        self._spores: List[Spore] = []

        # Hints
        self._hint_window = None
        self._paused_hint_window = None
        self._help_window = None
        self._on_listo_callback = None
        self._on_cancela_callback = None
        self._on_reanuda_callback = None

        # Drag
        self._drag_pos = None

        # Setup
        self._setup_window()
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

        # Margen amplio para glow, deformación y spores
        self._margin = 60
        total_size = self._base_size + self._margin * 2
        self.setFixedSize(total_size + 40, total_size + 60)  # Extra para spores
        self.move(self._position[0], self._position[1])

        self.show()

    def _connect_signals(self):
        """Conecta signals para comunicación thread-safe."""
        self.state_signal.connect(self._on_state_change)
        self.flash_signal.connect(self._on_flash)
        self.mic_level_signal.connect(self._on_mic_level)
        self.spore_signal.connect(self._spawn_spore)
        self.help_signal.connect(self._show_help_popup)

    def _start_animation(self):
        """Inicia el loop de animación (60 FPS)."""
        self._timer = QTimer()
        self._timer.timeout.connect(self._animate)
        self._timer.start(16)  # ~60 FPS

    # ========== ANIMACIÓN ==========

    def _animate(self):
        """Loop principal de animación - el organismo vive."""
        dt = 0.016  # ~60 FPS
        self._time += dt
        self._phase += dt

        # Suavizar nivel de micrófono - ASIMÉTRICO: sube rápido, baja lento
        if self._mic_level > self._smoothed_mic:
            # Subida rápida (pico instantáneo)
            self._smoothed_mic = lerp_smooth(self._smoothed_mic, self._mic_level, 0.7)
        else:
            # Bajada lenta (decay orgánico)
            self._smoothed_mic = lerp_smooth(self._smoothed_mic, self._mic_level, 0.05)

        # DEBUG: Imprimir nivel de mic cada 30 frames (~0.5s)
        if int(self._time * 60) % 30 == 0 and self._mic_level > 0.01:
            print(f"[MIC] raw={self._mic_level:.3f} smooth={self._smoothed_mic:.3f}")

        # Calcular objetivos según estado
        if self._state == State.DICTATING:
            # Crece con el mic (moderado)
            self._target_size = self._base_size + self._smoothed_mic * 60  # bajado de 150
            self._target_squash = 1.0  # Círculo
        elif self._state == State.PROCESSING:
            self._target_size = self._base_size * 0.85
            self._target_squash = 1.0
        elif self._state == State.PAUSED:
            self._target_size = self._idle_size * 0.9  # Un poco más pequeño
            self._target_squash = 1.0  # Cuadrado/círculo para diferenciarlo
        else:  # IDLE
            # En IDLE: el tamaño base crece con el mic - SUPER EXAGERADO
            self._target_size = self._idle_size + self._smoothed_mic * 80  # era 40
            self._target_squash = 2.2  # Óvalo muy horizontal/aplanado

        # Interpolación del tamaño - ASIMÉTRICA: sube rápido, baja lento
        size_diff = self._target_size - self._current_size
        if size_diff > 0:
            # Creciendo: rápido
            self._size_velocity = self._size_velocity * 0.3 + size_diff * 0.7
        else:
            # Encogiendo: lento y suave
            self._size_velocity = self._size_velocity * 0.9 + size_diff * 0.1
        self._current_size += self._size_velocity

        # Interpolación del squash
        squash_diff = self._target_squash - self._current_squash
        self._squash_velocity = self._squash_velocity * 0.85 + squash_diff * 0.15
        self._current_squash += self._squash_velocity

        # Respiración base
        breath = breathing_factor(self._time, rate=0.4, amplitude=0.02)
        self._display_size = self._current_size * breath

        # Transición de estado
        if self._transition_progress < 1.0:
            self._transition_progress = min(1.0, self._transition_progress + dt * 4.0)

        # Flash de transición (decae rápido)
        if self._transition_flash > 0:
            self._transition_flash = max(0, self._transition_flash - dt * 8.0)

        # Actualizar color
        self._update_color()

        # Actualizar spores
        self._spores = [s for s in self._spores if s.update(dt)]

        # Redibujar
        self.update()

    def _update_color(self):
        """Actualiza el color según el estado actual."""
        if self._state == State.IDLE:
            target_fill = QColor(self.IDLE_FILL)
            self._border_opacity = lerp_smooth(self._border_opacity, 1.0, 0.1)
        elif self._state == State.DICTATING:
            # Color varía con el mic
            base = QColor(self.DICTATING_FILL[0])
            bright = QColor(self.DICTATING_FILL[1])
            factor = self._smoothed_mic
            r = int(base.red() + (bright.red() - base.red()) * factor)
            g = int(base.green() + (bright.green() - base.green()) * factor)
            b = int(base.blue() + (bright.blue() - base.blue()) * factor)
            target_fill = QColor(r, g, b)
            self._border_opacity = lerp_smooth(self._border_opacity, 0.0, 0.15)
        elif self._state == State.PAUSED:
            target_fill = QColor(self.PAUSED_FILL)
            self._border_opacity = lerp_smooth(self._border_opacity, 1.0, 0.1)
        else:  # PROCESSING
            target_fill = QColor(self.PROCESSING_FILL)
            self._border_opacity = lerp_smooth(self._border_opacity, 0.3, 0.1)

        # Transición suave de color
        self._current_color = self._blend_colors(
            self._current_color, target_fill, 0.1
        )

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

        # Centro del widget (ajustado para spores debajo)
        cx = self.width() / 2
        cy = self._margin + self._base_size / 2

        radius = self._display_size / 2

        # Color a usar
        if self._flash_active and self._flash_color:
            fill_color = self._flash_color
        else:
            fill_color = self._current_color

        # Flash de transición (blanco)
        if self._transition_flash > 0:
            flash_color = QColor(255, 255, 255, int(self._transition_flash * 100))
            fill_color = self._blend_colors(fill_color, flash_color, self._transition_flash)

        # Sombra
        self._draw_shadow(painter, cx, cy + 2, radius)

        # Glow en DICTATING
        if self._state == State.DICTATING:
            self._draw_glow(painter, cx, cy, radius)

        # El núcleo orgánico
        self._draw_nucleus(painter, cx, cy, radius, fill_color)

        # Dibujar spores
        self._draw_spores(painter, cx, cy)

    def _draw_shadow(self, painter: QPainter, cx: float, cy: float, radius: float):
        """Sombra difusa."""
        # Ajustar sombra al squash
        rx = radius * self._current_squash * 1.1
        ry = radius / self._current_squash * 1.1

        gradient = QRadialGradient(cx, cy, max(rx, ry))
        gradient.setColorAt(0, QColor(0, 0, 0, 30))
        gradient.setColorAt(0.7, QColor(0, 0, 0, 10))
        gradient.setColorAt(1, QColor(0, 0, 0, 0))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), rx, ry)

    def _draw_glow(self, painter: QPainter, cx: float, cy: float, radius: float):
        """Halo difuso en grabación - SUPER EXAGERADO."""
        glow_radius = radius * 3.0  # Mucho más grande
        intensity = int(80 + self._smoothed_mic * 400)  # Muy intenso, visible incluso callado
        intensity = min(intensity, 255)  # Cap a 255

        gradient = QRadialGradient(cx, cy, glow_radius)
        gradient.setColorAt(0, QColor(231, 76, 60, intensity))
        gradient.setColorAt(0.4, QColor(231, 76, 60, int(intensity * 0.4)))
        gradient.setColorAt(1, QColor(231, 76, 60, 0))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_radius, glow_radius)

    def _draw_nucleus(self, painter: QPainter, cx: float, cy: float,
                      radius: float, color: QColor):
        """Dibuja el núcleo con deformación orgánica y bordes suaves."""

        # En IDLE con squash alto o PAUSED, dibujar elipse simple con bordes muy redondeados
        if (self._state == State.IDLE and self._current_squash > 1.5) or self._state == State.PAUSED:
            # Elipse simple - más limpio y redondeado
            rx = radius * self._current_squash
            ry = radius / self._current_squash

            # En IDLE: el tamaño reacciona al micrófono - MEGA EXAGERADO
            if self._state == State.IDLE:
                mic_pulse = 1.0 + self._smoothed_mic * 3.0  # Hasta 300% más grande con voz!
                rx *= mic_pulse
                ry *= mic_pulse

            # Aplicar respiración sutil con lava muy suave
            breath_lava = 1.0 + math.sin(self._time * 0.3) * 0.015
            rx *= breath_lava
            ry *= breath_lava

            path = QPainterPath()
            path.addEllipse(QPointF(cx, cy), rx, ry)

            # Relleno
            painter.setBrush(QBrush(color))

            # Borde (plateado para IDLE, dorado para PAUSED)
            if self._border_opacity > 0.05:
                if self._state == State.PAUSED:
                    border_color = QColor(self.PAUSED_BORDER)
                else:
                    border_color = QColor(self.IDLE_BORDER)

                # En IDLE: el borde reacciona al micrófono - MEGA EXAGERADO
                if self._state == State.IDLE:
                    # Opacidad base + boost por micrófono
                    mic_opacity = min(1.0, self._border_opacity + self._smoothed_mic * 1.0)
                    border_color.setAlphaF(mic_opacity)
                    # Grosor varía con el micrófono (2 a 20!) - MEGA GRUESO
                    border_width = 2.0 + self._smoothed_mic * 18.0
                    painter.setPen(QPen(border_color, border_width))
                else:
                    border_color.setAlphaF(self._border_opacity)
                    painter.setPen(QPen(border_color, 1.5))
            else:
                painter.setPen(Qt.PenStyle.NoPen)

            painter.drawPath(path)
            return

        # Para otros estados: deformación orgánica completa
        num_points = 32

        points = []
        for i in range(num_points):
            angle = (i / num_points) * 2 * math.pi

            # Base: squash/stretch para óvalo
            squash_factor = squash_stretch(angle, self._current_squash)

            # Deformación según estado
            if self._state == State.DICTATING:
                # Deformación moderada con el mic
                noise = organic_noise(angle, self._time * 2, scale=3.0, amplitude=0.08)
                mic_deform = 1.0 + self._smoothed_mic * 0.5 * math.sin(angle * 3 + self._time * 5)
                deform = noise * mic_deform
            else:  # PROCESSING
                # Micro-vibraciones
                vibration = 1.0 + micro_vibration(0.02)
                deform = squash_factor * vibration

            r = radius * deform
            x = cx + math.cos(angle) * r
            y = cy + math.sin(angle) * r
            points.append((x, y))

        # Dibujar path con curvas suaves (Catmull-Rom spline aproximado)
        path = QPainterPath()
        path.moveTo(points[0][0], points[0][1])

        for i in range(num_points):
            p0 = points[(i - 1) % num_points]
            p1 = points[i]
            p2 = points[(i + 1) % num_points]
            p3 = points[(i + 2) % num_points]

            tension = 0.4
            cp1x = p1[0] + (p2[0] - p0[0]) * tension / 3
            cp1y = p1[1] + (p2[1] - p0[1]) * tension / 3
            cp2x = p2[0] - (p3[0] - p1[0]) * tension / 3
            cp2y = p2[1] - (p3[1] - p1[1]) * tension / 3

            path.cubicTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])

        path.closeSubpath()

        # Relleno
        painter.setBrush(QBrush(color))

        # Borde plateado (solo visible en IDLE)
        if self._border_opacity > 0.05:
            border_color = QColor(self.IDLE_BORDER)
            border_color.setAlphaF(self._border_opacity)
            painter.setPen(QPen(border_color, 1.5))
        else:
            painter.setPen(Qt.PenStyle.NoPen)

        painter.drawPath(path)

    def _draw_spores(self, painter: QPainter, cx: float, cy: float):
        """Dibuja los spores (pop-ups orgánicos) con fondo."""
        font = QFont("Segoe UI", 9)
        painter.setFont(font)

        for spore in self._spores:
            if spore.opacity <= 0:
                continue

            # Medir texto para el fondo
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(spore.text)
            text_height = metrics.height()

            # Padding del fondo
            pad_x = 8
            pad_y = 4
            bg_width = text_width + pad_x * 2
            bg_height = text_height + pad_y * 2

            # Posición centrada
            x = spore.center_x - bg_width / 2 * spore.scale
            y = spore.y - bg_height / 2 * spore.scale

            painter.save()
            painter.translate(x + bg_width / 2 * spore.scale,
                            y + bg_height / 2 * spore.scale)
            painter.scale(spore.scale, spore.scale)

            # Fondo según tipo
            if spore.is_command:
                # Verde para comandos aceptados
                bg_color = QColor(34, 85, 51, int(220 * spore.opacity))
            else:
                # Gris oscuro para texto normal
                bg_color = QColor(20, 20, 20, int(200 * spore.opacity))

            painter.setBrush(QBrush(bg_color))
            painter.setPen(Qt.PenStyle.NoPen)

            # Rectángulo redondeado
            bg_rect = QRectF(-bg_width / 2, -bg_height / 2, bg_width, bg_height)
            painter.drawRoundedRect(bg_rect, 6, 6)

            # Color del texto según tipo
            if spore.is_command:
                text_color = QColor(180, 255, 180)  # Verde claro para comandos
                font.setWeight(QFont.Weight.Medium)
            else:
                text_color = QColor(180, 180, 180)  # Gris claro para texto normal
                font.setWeight(QFont.Weight.Light)

            text_color.setAlphaF(spore.opacity)
            painter.setFont(font)
            painter.setPen(text_color)

            # Texto centrado
            text_rect = QRectF(-bg_width / 2, -bg_height / 2, bg_width, bg_height)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, spore.text)

            painter.restore()

    # ========== API THREAD-SAFE ==========

    def set_state(self, state: State):
        """Thread-safe: cambia el estado del organismo."""
        self.state_signal.emit(state)

    def flash(self, color: str, duration_ms: int = 200):
        """Thread-safe: flash de color."""
        self.flash_signal.emit(color, duration_ms)

    def flash_success(self):
        self.flash(self.SUCCESS_COLOR, 150)

    def flash_error(self):
        self.flash(self.ERROR_COLOR, 150)

    def flash_unknown(self):
        """Flash sutil para comando no reconocido."""
        self.flash("#2a2a2a", 100)

    def set_mic_level(self, level: float):
        """Thread-safe: actualiza nivel de micrófono (0.0 - 1.0)."""
        self.mic_level_signal.emit(min(1.0, max(0.0, level)))

    def show_text(self, text: str, is_command: bool = False):
        """Thread-safe: muestra texto como spore."""
        self.spore_signal.emit(text, is_command)

    def show_help(self, commands: list):
        """Thread-safe: muestra pop-up de ayuda con comandos.
        commands: lista de tuplas (keyword, descripcion)
        """
        self.help_signal.emit(commands)

    # ========== SLOTS ==========

    def _on_state_change(self, state: State):
        """Slot: procesa cambio de estado."""
        if state != self._state:
            self._prev_state = self._state
            self._state = state
            self._transition_progress = 0.0
            self._transition_flash = 1.0  # Flash visible al cambiar

            # Mostrar/ocultar hints según estado
            if state == State.DICTATING:
                self.show_hints()
            elif state == State.PAUSED:
                self.show_paused_hint()
            elif self._prev_state == State.DICTATING:
                self.hide_hints()
            elif self._prev_state == State.PAUSED:
                self.hide_paused_hint()

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

    def _spawn_spore(self, text: str, is_command: bool):
        """Slot: crea un nuevo spore con stack vertical."""
        cx = self.width() / 2
        cy = self._margin + self._base_size / 2

        # Calcular radio visual real según estado
        # En IDLE el óvalo es pequeño y aplanado, usar la altura visual
        if self._state == State.IDLE:
            visual_radius = (self._display_size / 2) / self._current_squash
        else:
            visual_radius = self._display_size / 2

        # Calcular la posición Y basada en spores existentes
        # para evitar overlap (stack vertical)
        spore_height = 24  # Altura aproximada de un spore
        spore_spacing = 4  # Espacio entre spores

        # Comandos salen justo debajo del núcleo, textos más abajo
        if is_command:
            base_y = cy + visual_radius + 5  # Comandos: muy pegados al núcleo
        else:
            base_y = cy + visual_radius + 25  # Textos: más abajo

        # Encontrar slots ocupados (solo entre spores del mismo tipo)
        occupied_slots = []
        for s in self._spores:
            if s.opacity > 0.3 and s.is_command == is_command:
                slot = int((s.end_y - base_y) / (spore_height + spore_spacing))
                if slot >= 0:
                    occupied_slots.append(slot)

        # Encontrar el primer slot libre
        slot = 0
        while slot in occupied_slots:
            slot += 1

        # Calcular posición Y final
        end_y = base_y + slot * (spore_height + spore_spacing)
        # Empieza en el borde inferior del núcleo
        start_y = cy + visual_radius

        spore = Spore(text, start_y, end_y, cx, is_command=is_command)
        self._spores.append(spore)

    def _show_help_popup(self, commands: list):
        """Slot: muestra pop-up de ayuda con lista de comandos."""
        # Cerrar si ya existe
        if self._help_window:
            self._help_window.close()
            self._help_window = None

        self._help_window = QWidget(None, Qt.WindowType.FramelessWindowHint |
                                    Qt.WindowType.WindowStaysOnTopHint |
                                    Qt.WindowType.Tool)
        self._help_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self._help_window)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        # Frame contenedor con estilo pop-up
        frame = QWidget()
        frame.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 20, 230);
                border-radius: 8px;
            }
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(10, 8, 10, 8)
        frame_layout.setSpacing(3)

        # Añadir cada comando
        for keyword, desc in commands:
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            # Keyword
            kw_label = QLabel(keyword)
            kw_label.setStyleSheet("""
                color: #b4ffb4;
                font-family: 'Segoe UI';
                font-size: 9px;
                font-weight: 500;
                background: transparent;
            """)
            kw_label.setMinimumWidth(60)
            row_layout.addWidget(kw_label)

            # Descripción
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("""
                color: #888888;
                font-family: 'Segoe UI';
                font-size: 9px;
                background: transparent;
            """)
            row_layout.addWidget(desc_label)
            row_layout.addStretch()

            frame_layout.addWidget(row)

        layout.addWidget(frame)

        # Ajustar tamaño
        self._help_window.adjustSize()

        # Posicionar encima del núcleo, centrado
        help_width = self._help_window.width()
        overlay_center_x = self.x() + self.width() / 2
        x = int(overlay_center_x - help_width / 2)
        y = self.y() - self._help_window.height() - 8
        self._help_window.move(x, y)
        self._help_window.show()

        # Auto-cerrar después de 4 segundos
        QTimer.singleShot(4000, self._hide_help_popup)

    def _hide_help_popup(self):
        """Cierra el pop-up de ayuda."""
        if self._help_window:
            self._help_window.close()
            self._help_window = None

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
            State.IDLE: "Esperando",
            State.DICTATING: "Absorbiendo",
            State.PROCESSING: "Pensando",
            State.PAUSED: "Pausado"
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
        self._idle_size = size * 0.7
        if self._state == State.IDLE:
            self._current_size = float(self._idle_size)
            self._target_size = float(self._idle_size)

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
        """Muestra los hints de listo/cancela con estética de pop-ups (vertical)."""
        if self._hint_window:
            return

        self._hint_window = QWidget(None, Qt.WindowType.FramelessWindowHint |
                                    Qt.WindowType.WindowStaysOnTopHint |
                                    Qt.WindowType.Tool)
        self._hint_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Layout vertical
        layout = QVBoxLayout(self._hint_window)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Botón listo - estilo pop-up verde
        listo_btn = QPushButton("listo")
        listo_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(34, 85, 51, 220);
                color: #b4ffb4;
                border: none;
                border-radius: 6px;
                padding: 5px 16px;
                font-family: 'Segoe UI';
                font-size: 9px;
                font-weight: 500;
                min-width: 50px;
            }
            QPushButton:hover {
                background-color: rgba(45, 110, 65, 230);
            }
        """)
        listo_btn.clicked.connect(self._on_hint_listo)
        layout.addWidget(listo_btn)

        # Botón cancela - estilo pop-up rojo
        cancela_btn = QPushButton("cancela")
        cancela_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(90, 39, 39, 220);
                color: #ffb4b4;
                border: none;
                border-radius: 6px;
                padding: 5px 16px;
                font-family: 'Segoe UI';
                font-size: 9px;
                font-weight: 500;
                min-width: 50px;
            }
            QPushButton:hover {
                background-color: rgba(120, 50, 50, 230);
            }
        """)
        cancela_btn.clicked.connect(self._on_hint_cancela)
        layout.addWidget(cancela_btn)

        # Ajustar tamaño
        self._hint_window.adjustSize()

        # Posicionar justo encima del núcleo, centrado
        hint_width = self._hint_window.width()
        overlay_center_x = self.x() + self.width() / 2
        x = int(overlay_center_x - hint_width / 2)
        y = self.y() - self._hint_window.height() - 5
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

    def set_reanuda_callback(self, on_reanuda: Callable):
        """Configura callback para el hint de reanuda."""
        self._on_reanuda_callback = on_reanuda

    def show_paused_hint(self):
        """Muestra el hint de reanuda para el estado PAUSED."""
        if self._paused_hint_window:
            return

        self._paused_hint_window = QWidget(None, Qt.WindowType.FramelessWindowHint |
                                           Qt.WindowType.WindowStaysOnTopHint |
                                           Qt.WindowType.Tool)
        self._paused_hint_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self._paused_hint_window)
        layout.setContentsMargins(4, 4, 4, 4)

        # Botón reanuda - estilo dorado/amarillo para coincidir con PAUSED
        reanuda_btn = QPushButton("reanuda")
        reanuda_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(139, 117, 0, 220);
                color: #ffe066;
                border: none;
                border-radius: 6px;
                padding: 5px 16px;
                font-family: 'Segoe UI';
                font-size: 9px;
                font-weight: 500;
                min-width: 50px;
            }
            QPushButton:hover {
                background-color: rgba(180, 150, 0, 230);
            }
        """)
        reanuda_btn.clicked.connect(self._on_hint_reanuda)
        layout.addWidget(reanuda_btn)

        # Ajustar tamaño
        self._paused_hint_window.adjustSize()

        # Posicionar justo encima del núcleo, centrado
        hint_width = self._paused_hint_window.width()
        overlay_center_x = self.x() + self.width() / 2
        x = int(overlay_center_x - hint_width / 2)
        y = self.y() - self._paused_hint_window.height() - 5
        self._paused_hint_window.move(x, y)
        self._paused_hint_window.show()

    def hide_paused_hint(self):
        """Oculta el hint de pausa."""
        if self._paused_hint_window:
            self._paused_hint_window.close()
            self._paused_hint_window = None

    def _on_hint_reanuda(self):
        if self._on_reanuda_callback:
            self._on_reanuda_callback()

    # ========== UTILIDADES ==========

    def get_position(self) -> tuple:
        return (self.x(), self.y())

    def update(self):
        """Fuerza repintado."""
        super().update()

    def quit(self):
        """Cierra el overlay."""
        self.hide_hints()
        self.hide_paused_hint()
        self.close()
        if self._app:
            self._app.quit()
