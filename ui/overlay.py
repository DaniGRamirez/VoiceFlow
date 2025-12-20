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


def perlin_noise_1d(x: float) -> float:
    """
    Simple 1D Perlin-like noise for organic animation.
    Returns value between -1 and 1.
    """
    # Use multiple sine waves with different frequencies for noise-like behavior
    return (
        math.sin(x * 1.0) * 0.5 +
        math.sin(x * 2.3 + 1.7) * 0.3 +
        math.sin(x * 4.1 + 0.3) * 0.2
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


class Transition:
    """
    Gestiona una transición entre estados visuales.

    Las transiciones tienen 3 fases:
    1. COLLAPSE: El elemento origen colapsa hacia el centro
    2. HOLD: Pausa breve mostrando un punto blanco
    3. EXPAND: El elemento destino se expande desde el centro
    """

    def __init__(self, from_visual: str, to_visual: str, to_state: 'State'):
        """
        Args:
            from_visual: "bars" o "circle" - elemento que colapsa
            to_visual: "bars" o "circle" - elemento que aparece
            to_state: Estado destino (State.IDLE, State.DICTATING, etc.)
        """
        self.from_visual = from_visual
        self.to_visual = to_visual
        self.to_state = to_state

        self.time = 0.0
        self.phase = "collapse"  # "collapse" | "hold" | "expand"

        # Duraciones (segundos)
        self.collapse_duration = 0.1   # Colapso rápido
        self.hold_duration = 0.3       # Pausa en el centro
        self.expand_duration = 0.25    # Expansión con rebote

    @property
    def total_duration(self) -> float:
        return self.collapse_duration + self.hold_duration + self.expand_duration

    def update(self, dt: float) -> bool:
        """
        Actualiza la transición.

        Returns:
            True si la transición ha terminado
        """
        self.time += dt

        if self.time < self.collapse_duration:
            self.phase = "collapse"
        elif self.time < self.collapse_duration + self.hold_duration:
            self.phase = "hold"
        else:
            self.phase = "expand"

        return self.time >= self.total_duration

    def get_collapse_progress(self) -> float:
        """
        Progreso del colapso (0 = no colapsado, 1 = totalmente colapsado).
        """
        if self.phase == "collapse":
            return min(1.0, self.time / self.collapse_duration)
        return 1.0

    def get_expand_progress(self) -> float:
        """
        Progreso de la expansión (0 = no expandido, 1 = totalmente expandido).
        """
        if self.phase != "expand":
            return 0.0
        expand_time = self.time - self.collapse_duration - self.hold_duration
        return min(1.0, expand_time / self.expand_duration)


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
    listening_signal = pyqtSignal(bool)  # True = escuchando comando, False = fin

    # Colores
    IDLE_FILL = "#0a0a0a"  # Negro profundo
    IDLE_BORDER = "#8a8a8a"  # Plateado
    DICTATING_FILL = ("#B83227", "#E74C3C")  # Rojo cálido
    PROCESSING_FILL = "#1a1a1a"  # Gris muy oscuro
    PAUSED_FILL = "#8B7500"  # Amarillo oscuro/dorado
    PAUSED_BORDER = "#D4AA00"  # Dorado brillante

    SUCCESS_COLOR = "#2D5A27"
    ERROR_COLOR = "#5A2727"

    # Configuración de barras para IDLE (audio visualizer) - MÁS COMPACTO
    BAR_COUNT = 11  # Número impar para simetría
    BAR_WIDTH = 3  # Ancho de cada barra en px (era 4)
    BAR_GAP = 2  # Espacio entre barras (era 3)
    BAR_CORNER_RADIUS = 1.5  # Radio de esquinas redondeadas
    BAR_BASE_HEIGHT_RATIO = 0.25  # Altura mínima (25% del contenedor)
    BAR_MAX_HEIGHT_RATIO = 0.85  # Altura máxima (85% del contenedor)

    # Duraciones de animaciones (segundos)
    TRANSITION_DURATION = 0.35  # Duración de transiciones entre estados
    COLLAPSE_DURATION = 0.1  # Colapso rápido al centro (muy rápido)
    HOLD_DURATION = 0.5  # Pausa en el centro antes de expandir
    EXPAND_DURATION = 0.25  # Expansión después del colapso
    WAKE_SHAKE_DURATION = 0.3  # Duración de la sacudida al detectar wake-word
    LISTENING_PULSE_SPEED = 4.0  # Velocidad del pulso mientras escucha comando

    def __init__(self, size: int = 40, position: tuple = (1850, 50), opacity: float = 0.9, auto_help: bool = True):
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
        self._auto_help = auto_help  # Mostrar ayuda automática en errores

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

        # Modo silencioso (entrada de texto por teclado)
        self._silent_input_window = None
        self._on_silent_input_callback = None  # Callback para procesar texto

        # Drag
        self._drag_pos = None

        # === SISTEMA DE TRANSICIONES (NUEVO) ===
        # Modo visual actual: qué elemento se está mostrando
        self._visual_mode = "bars"  # "bars" | "circle"

        # Transición activa (None si no hay transición en curso)
        self._transition: Optional[Transition] = None

        # Despliegue de barras (0 = punto central, 1 = desplegadas)
        self._bars_deploy = 1.0

        # Escala del círculo (0.3 = pequeño para transición, 1.0 = normal)
        self._circle_scale = 1.0

        # Progreso de color del círculo (0 = blanco, 1 = color destino)
        self._circle_color_progress = 1.0

        # Estado de "escuchando comando" (wake-word detectado, barras como punto pulsante)
        self._listening_mode = False
        self._listening_time = 0.0

        # Sacudida por wake-word
        self._shake_time = 0.0
        self._shake_intensity = 0.0

        # Energía de las barras (basada en nivel de mic)
        self._bars_energy = 0.0

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

        # Permitir foco de teclado para teclas de debug
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

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
        self.listening_signal.connect(self._on_listening_change)

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
            self._smoothed_mic = lerp_smooth(self._smoothed_mic, self._mic_level, 0.7)
        else:
            self._smoothed_mic = lerp_smooth(self._smoothed_mic, self._mic_level, 0.05)

        # === ANIMACIÓN DE TRANSICIONES (usando clase Transition) ===
        if self._transition:
            finished = self._transition.update(dt)

            if self._transition.phase == "collapse":
                # Colapsar elemento origen
                collapse = self._transition.get_collapse_progress()
                if self._transition.from_visual == "bars":
                    self._bars_deploy = 1.0 - collapse
                else:  # circle
                    self._circle_scale = 1.0 - collapse * 0.7  # 1.0 → 0.3
                    self._circle_color_progress = 1.0 - collapse  # color → blanco

            elif self._transition.phase == "hold":
                # Todo colapsado (punto blanco)
                self._bars_deploy = 0.0
                self._circle_scale = 0.3
                self._circle_color_progress = 0.0

            else:  # expand
                # Expandir elemento destino
                expand = self._transition.get_expand_progress()
                expand_eased = ease_out_back(expand, 1.1)

                if self._transition.to_visual == "bars":
                    self._bars_deploy = expand_eased
                    self._circle_color_progress = 0.0
                else:  # circle
                    self._circle_scale = 0.3 + expand_eased * 0.7  # 0.3 → 1.0
                    self._circle_color_progress = expand  # blanco → color
                    self._bars_deploy = 0.0

            # Transición completada
            if finished:
                self._visual_mode = self._transition.to_visual
                self._transition = None
                # Valores finales
                if self._visual_mode == "bars":
                    self._bars_deploy = 1.0
                else:
                    self._circle_scale = 1.0
                    self._circle_color_progress = 1.0

        # === SACUDIDA POR WAKE-WORD ===
        if self._shake_time > 0:
            self._shake_time -= dt
            # Decay exponencial de la intensidad
            self._shake_intensity = self._shake_time / self.WAKE_SHAKE_DURATION

        # === MODO ESCUCHANDO COMANDO ===
        if self._listening_mode:
            self._listening_time += dt
            # En listening mode, las barras se mantienen desplegadas
            # pero con animación de pulsación (manejado en _draw_idle_bars)
            if not self._transition:
                self._bars_deploy = lerp_smooth(self._bars_deploy, 1.0, 0.1)
        elif self._visual_mode == "bars" and not self._transition:
            # Fuera de listening mode, las barras deben estar desplegadas
            self._bars_deploy = lerp_smooth(self._bars_deploy, 1.0, 0.1)

        # === ENERGÍA DE BARRAS ===
        mic_shaped = pow(self._smoothed_mic, 0.5) if self._smoothed_mic > 0 else 0
        target_energy = min(mic_shaped * 1.5, 1.0)

        if target_energy > self._bars_energy:
            self._bars_energy = lerp(self._bars_energy, target_energy, 0.3)
        else:
            self._bars_energy = lerp(self._bars_energy, target_energy, 0.05)

        # Calcular objetivos según estado
        if self._state == State.DICTATING:
            self._target_size = self._base_size + self._smoothed_mic * 40
            self._target_squash = 1.0
        elif self._state == State.PROCESSING:
            self._target_size = self._base_size * 0.85
            self._target_squash = 1.0
        elif self._state == State.PAUSED:
            self._target_size = self._idle_size * 0.9
            self._target_squash = 1.0
        else:  # IDLE
            mic_growth = min(self._smoothed_mic * 20, 12)
            self._target_size = self._idle_size + mic_growth
            self._target_squash = 2.2

        # Interpolación del tamaño
        size_diff = self._target_size - self._current_size
        if size_diff > 0:
            self._size_velocity = self._size_velocity * 0.3 + size_diff * 0.7
        else:
            self._size_velocity = self._size_velocity * 0.9 + size_diff * 0.1
        self._current_size += self._size_velocity

        # Interpolación del squash
        squash_diff = self._target_squash - self._current_squash
        self._squash_velocity = self._squash_velocity * 0.85 + squash_diff * 0.15
        self._current_squash += self._squash_velocity

        # Respiración base
        breath = breathing_factor(self._time, rate=0.4, amplitude=0.02)
        self._display_size = self._current_size * breath

        # Transición de estado vieja (para flash)
        if self._transition_progress < 1.0:
            self._transition_progress = min(1.0, self._transition_progress + dt * 4.0)

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
        """Dibuja el organismo con transiciones animadas."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Centro del widget (ajustado para spores debajo)
        cx = self.width() / 2
        cy = self._margin + self._base_size / 2

        radius = self._display_size / 2

        # Color base
        if self._flash_active and self._flash_color:
            fill_color = self._flash_color
        else:
            fill_color = self._current_color

        # Sombra
        self._draw_shadow(painter, cx, cy + 2, radius)

        # === LÓGICA DE DIBUJO SEGÚN TRANSICIÓN ===
        if self._transition:
            # Durante transición
            if self._transition.phase == "collapse":
                # Colapsar elemento origen
                if self._transition.from_visual == "bars":
                    self._draw_idle_bars(painter, cx, cy, radius, fill_color)
                else:  # circle
                    # Círculo encogiéndose y volviéndose blanco
                    scaled_radius = radius * self._circle_scale
                    circle_color = self._get_circle_color()
                    if self._circle_color_progress > 0.3:
                        self._draw_glow(painter, cx, cy, scaled_radius, self._circle_color_progress)
                    self._draw_nucleus(painter, cx, cy, scaled_radius, circle_color)

            elif self._transition.phase == "hold":
                # Punto blanco pulsante en el centro
                self._draw_point(painter, cx, cy)

            else:  # expand
                # Expandir elemento destino
                if self._transition.to_visual == "bars":
                    self._draw_idle_bars(painter, cx, cy, radius, fill_color)
                else:  # circle
                    # Círculo creciendo y coloreándose
                    scaled_radius = radius * self._circle_scale
                    circle_color = self._get_circle_color()
                    if self._circle_color_progress > 0.3:
                        self._draw_glow(painter, cx, cy, scaled_radius, self._circle_color_progress)
                    self._draw_nucleus(painter, cx, cy, scaled_radius, circle_color)

        else:
            # Estado estable (sin transición)
            if self._visual_mode == "bars":
                # Barras (IDLE o listening)
                self._draw_idle_bars(painter, cx, cy, radius, fill_color)
            else:
                # Círculo (DICTATING o PAUSED)
                circle_color = self._get_circle_color()
                if self._state == State.DICTATING:
                    self._draw_glow(painter, cx, cy, radius, 1.0)
                self._draw_nucleus(painter, cx, cy, radius, circle_color)

        # Dibujar spores
        self._draw_spores(painter, cx, cy)

    def _get_circle_color(self) -> QColor:
        """Calcula el color del círculo según estado y progreso."""
        white = QColor(255, 255, 255)

        if self._state == State.DICTATING:
            # Rojo
            red_base = QColor(self.DICTATING_FILL[0])
            red_bright = QColor(self.DICTATING_FILL[1])
            target_color = self._blend_colors(red_base, red_bright, self._smoothed_mic)
        elif self._state == State.PAUSED:
            # Amarillo/dorado
            target_color = QColor(self.PAUSED_FILL)
        else:
            target_color = white

        # Mezclar blanco y color destino según progreso
        return self._blend_colors(white, target_color, self._circle_color_progress)

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

    def _draw_glow(self, painter: QPainter, cx: float, cy: float, radius: float,
                   intensity_mult: float = 1.0):
        """Halo difuso en grabación.

        Args:
            intensity_mult: Multiplicador de intensidad (0-1) para transiciones
        """
        glow_radius = radius * 2.5
        base_intensity = int((60 + self._smoothed_mic * 300) * intensity_mult)
        base_intensity = min(base_intensity, 255)

        gradient = QRadialGradient(cx, cy, glow_radius)
        gradient.setColorAt(0, QColor(231, 76, 60, base_intensity))
        gradient.setColorAt(0.4, QColor(231, 76, 60, int(base_intensity * 0.4)))
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

            # En IDLE: el tamaño reacciona al micrófono (moderado, con límite)
            if self._state == State.IDLE:
                mic_pulse = 1.0 + min(self._smoothed_mic * 0.8, 0.5)  # Máximo 50% más grande
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

                # En IDLE: el borde reacciona al micrófono (moderado, con límite)
                if self._state == State.IDLE:
                    # Opacidad base + boost por micrófono
                    mic_opacity = min(1.0, self._border_opacity + self._smoothed_mic * 0.5)
                    border_color.setAlphaF(mic_opacity)
                    # Grosor varía con el micrófono (1.5 a 4px máximo)
                    border_width = 1.5 + min(self._smoothed_mic * 3.0, 2.5)
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

    def _draw_point(self, painter: QPainter, cx: float, cy: float):
        """
        Dibuja un punto blanco pulsante en el centro.
        Usado durante la fase "hold" de las transiciones.
        """
        # Pulsación sutil
        pulse = 1.0 + math.sin(self._time * 4) * 0.1
        point_size = 12 * pulse

        # Fondo negro redondeado
        bg_size = point_size + 10
        bg_rect = QRectF(
            cx - bg_size / 2,
            cy - bg_size / 2,
            bg_size,
            bg_size
        )
        painter.setBrush(QBrush(QColor(0, 0, 0)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bg_rect, 6, 6)

        # Punto blanco
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(QPointF(cx, cy), point_size / 2, point_size / 2)

    def _draw_idle_bars(self, painter: QPainter, cx: float, cy: float,
                        radius: float, color: QColor):
        """
        Dibuja barras de audio visualizer para el estado IDLE.

        Comportamiento:
        - Silencio: onda suave viajando de izquierda a derecha
        - Con mic: barras energéticas con perfil de campana
        - Transición: barras colapsan/despliegan desde el centro
        - Listening mode: pulso rítmico urgente + sacudida
        - Fondo negro sólido fijo, solo las barras escalan
        """
        # Dimensiones del contenedor - crece con energía
        base_container_height = 14  # Altura mínima en silencio
        max_container_height = 24   # Altura máxima con volumen
        energy = self._bars_energy

        # Usar _bars_deploy directamente (ya se actualiza en _animate())
        deploy = self._bars_deploy

        # Cuando está colapsado, usar altura fija para que el "punto" sea visible
        # Altura del punto: similar a cuando hay voz (18px)
        collapsed_container_height = 18
        normal_container_height = base_container_height + (max_container_height - base_container_height) * energy

        # Si deploy < 0.3, usar altura de punto; sino transición gradual
        if deploy < 0.3:
            container_height = collapsed_container_height
        else:
            transition = (deploy - 0.3) / 0.7
            container_height = lerp(collapsed_container_height, normal_container_height, transition)

        # Ancho del contenedor depende del despliegue
        full_container_width = (self.BAR_COUNT * self.BAR_WIDTH +
                               (self.BAR_COUNT - 1) * self.BAR_GAP)
        # Contraído: punto compacto (25% del ancho - más pequeño que antes)
        contracted_ratio = 0.25
        contracted_width = full_container_width * contracted_ratio

        # === SACUDIDA (shake) - SUTIL ===
        shake_offset_x = 0
        shake_offset_y = 0
        if self._shake_intensity > 0:
            # Sacudida sutil (valores reducidos a la mitad)
            shake_freq = 17.5  # Frecuencia (era 35)
            shake_amp = 5.0 * self._shake_intensity  # Amplitud máxima 5px (era 10)
            shake_offset_x = math.sin(self._time * shake_freq) * shake_amp
            shake_offset_y = math.cos(self._time * shake_freq * 1.3) * shake_amp * 0.6

        # Ancho del contenedor interpolado según despliegue
        container_width = lerp(contracted_width, full_container_width, deploy)

        # Posición del contenedor (centrado, con shake)
        container_x = cx - container_width / 2 + shake_offset_x
        container_y = cy - container_height / 2 + shake_offset_y

        # === FONDO NEGRO SÓLIDO (escala con energía) ===
        padding = 5
        bg_rect = QRectF(
            container_x - padding,
            container_y - padding,
            container_width + padding * 2,
            container_height + padding * 2
        )
        painter.setBrush(QBrush(QColor(0, 0, 0)))  # Negro sólido
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bg_rect, 6, 6)

        # Alturas base y máxima para barras
        base_height = container_height * self.BAR_BASE_HEIGHT_RATIO
        max_height = container_height * self.BAR_MAX_HEIGHT_RATIO
        height_range = max_height - base_height

        # Centro de las barras (para perfil de campana)
        center_idx = self.BAR_COUNT // 2

        # === DIBUJAR CADA BARRA ===
        # Calcular espaciado contraído (proporcional pero más junto)
        contracted_bar_width = self.BAR_WIDTH * 0.6  # 60% del ancho normal
        contracted_gap = (contracted_width - self.BAR_COUNT * contracted_bar_width) / max(1, self.BAR_COUNT - 1)

        for i in range(self.BAR_COUNT):
            # === ANIMACIÓN DE DESPLIEGUE ===
            # Aplicar easing al despliegue (ease out back para rebote)
            deploy_eased = ease_out_back(deploy, 1.2) if deploy < 1.0 else 1.0

            # Posición X desplegada (full width)
            deployed_x = container_x + i * (self.BAR_WIDTH + self.BAR_GAP)
            # Posición X contraída (mantiene separación dentro de contracted_width)
            contracted_x = container_x + i * (contracted_bar_width + contracted_gap)

            # Interpolar posición X entre contraída y desplegada
            bar_x = lerp(contracted_x, deployed_x, deploy_eased)

            # Ancho de barra también interpolado
            bar_width = lerp(contracted_bar_width, self.BAR_WIDTH, deploy_eased)

            # === PARÁMETROS ÚNICOS POR BARRA ===
            bar_seed = i * 137.5  # Golden angle
            phase_offset = (i / self.BAR_COUNT) * math.pi * 2
            speed_mult = 0.8 + (perlin_noise_1d(bar_seed) + 1) * 0.2

            # Desplazamiento vertical por onda (se calcula abajo)
            wave_lift = 0.0

            # === MODO LISTENING: Pulso rítmico moderado ===
            if self._listening_mode:
                # Pulso más lento y menos extremo
                pulse_speed = 2.5  # Más lento (era 4.0)
                pulse_raw = math.sin(self._listening_time * pulse_speed * math.pi * 2)

                # Suavizar un poco (no tan cuadrado)
                pulse = (math.tanh(pulse_raw * 2) + 1) / 2  # 0-1

                # Variación mínima por barra para que no sea robótico
                pulse_var = perlin_noise_1d(self._listening_time * 2 + bar_seed * 0.1) * 0.03

                # RANGO MODERADO: de pequeño (0.15) a medio-alto (0.7)
                height_factor = 0.15 + pulse * 0.55 + pulse_var
                height_factor = max(0.15, min(0.75, height_factor))

            else:
                # === MODO NORMAL ===

                # === MODO SILENCIO: Barras MICRO (casi invisibles) con onda ping-pong ===
                wave_speed = 2.4  # Doble de rápido (era 1.2)
                wave_width = 2.5  # Estrecha para más impacto

                # Onda ping-pong: va de izquierda a derecha y vuelve
                wave_range = self.BAR_COUNT - 1  # 0 a BAR_COUNT-1
                wave_cycle = (self._time * wave_speed) % (wave_range * 2)  # Ciclo completo ida+vuelta
                if wave_cycle <= wave_range:
                    # Ida: izquierda a derecha
                    wave_pos = wave_cycle
                else:
                    # Vuelta: derecha a izquierda
                    wave_pos = wave_range * 2 - wave_cycle

                dist_to_wave = abs(i - wave_pos)
                # Usar potencia para hacer la onda más "puntiaguda" (más contraste)
                wave_intensity = math.exp(-(dist_to_wave ** 2) / (2 * (wave_width / 2) ** 2))
                wave_intensity = pow(wave_intensity, 0.7)  # Más potencia en el pico

                organic_var = perlin_noise_1d(self._time * 0.3 * speed_mult + bar_seed) * 0.003
                # Barras MICRO: base 0.003 (1/3 de antes), onda añade hasta 0.12
                silence_component = 0.003 + wave_intensity * 0.12 + organic_var

                # Desplazamiento vertical por la onda (sube cuando pasa) - más pronunciado
                # Solo en silencio (energy baja), la onda "levanta" las barras
                wave_lift = wave_intensity * 4.0 * (1.0 - energy)  # Hasta 4px arriba

                # === MODO ENERGÉTICO: Perfil de campana + ruido ===
                sigma = self.BAR_COUNT / 3.0
                distance_from_center = abs(i - center_idx)
                bell_profile = math.exp(-(distance_from_center ** 2) / (2 * sigma ** 2))

                energy_noise = perlin_noise_1d(self._time * 2.5 * speed_mult + bar_seed * 2) * 0.15
                energy_wave = math.sin(self._time * 3.0 + phase_offset) * 0.1
                energy_component = bell_profile * 0.7 + energy_noise + energy_wave + 0.2

                # Mezclar según energía
                height_factor = lerp(silence_component, energy_component, energy)
                height_factor = max(0.05, min(1.0, height_factor))

            # === ALTURA FINAL ===
            # Durante colapso: mostrar como un PUNTO BLANCO visible
            # Cuando deploy < 0.3, todas las barras convergen a un punto blanco
            if deploy_eased < 0.3:
                # Altura fija para el "punto" - similar a cuando hay voz
                # Usamos altura proporcional al contenedor para que sea visible
                point_height = container_height * 0.6  # 60% del contenedor = punto visible
                bar_height = point_height
            else:
                # Transición gradual: de punto a barra normal
                # Mapear deploy de 0.3-1.0 a 0.0-1.0 para la transición
                transition = (deploy_eased - 0.3) / 0.7
                point_height = container_height * 0.6
                normal_height = (base_height + height_range * height_factor)
                bar_height = lerp(point_height, normal_height, transition)

            # Posición Y (centrada verticalmente, con wave_lift hacia arriba)
            # No aplicar wave_lift cuando está colapsado (todas quietas en el centro)
            if deploy_eased < 0.3:
                bar_y = cy - bar_height / 2 + shake_offset_y
            else:
                bar_y = cy - bar_height / 2 + shake_offset_y - wave_lift

            # === DIBUJAR LA BARRA ===
            bar_rect = QRectF(bar_x, bar_y, bar_width, bar_height)

            # Barras BLANCAS
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_rect, self.BAR_CORNER_RADIUS,
                                   self.BAR_CORNER_RADIUS)

        # === BORDE DEL CONTENEDOR ===
        if self._border_opacity > 0.05 and deploy > 0.5:
            border_color = QColor(self.IDLE_BORDER)
            border_opacity = min(1.0, self._border_opacity * 0.3 + energy * 0.2)
            border_color.setAlphaF(border_opacity * deploy)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(border_color, 1.0))
            painter.drawRoundedRect(bg_rect, 6, 6)

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

    def set_listening(self, listening: bool):
        """Thread-safe: activa/desactiva modo escucha (wake-word detectado)."""
        self.listening_signal.emit(listening)

    # ========== SLOTS ==========

    def _on_state_change(self, state: State):
        """Slot: procesa cambio de estado."""
        if state != self._state:
            self._prev_state = self._state
            self._state = state
            self._transition_progress = 0.0

            # Terminar modo listening al cambiar de estado
            self._listening_mode = False
            self._listening_time = 0.0

            # === CREAR TRANSICIÓN SEGÚN ESTADOS ===
            # Determinar visual origen y destino
            from_visual = self._visual_mode

            # Visual destino según estado
            if state == State.IDLE:
                to_visual = "bars"
            elif state == State.DICTATING:
                to_visual = "circle"
            elif state == State.PAUSED:
                to_visual = "circle"  # PAUSED usa círculo amarillo
            else:
                to_visual = "bars"

            # Crear transición si hay cambio de visual o cambio de estado significativo
            if from_visual != to_visual or state in (State.DICTATING, State.PAUSED, State.IDLE):
                self._transition = Transition(from_visual, to_visual, state)
            else:
                self._transition = None

            # Mostrar/ocultar hints según estado
            if state == State.DICTATING:
                self.show_hints()
            elif state == State.PAUSED:
                self.show_paused_hint()
            elif self._prev_state == State.DICTATING:
                self.hide_hints()
            elif self._prev_state == State.PAUSED:
                self.hide_paused_hint()

    def _on_listening_change(self, listening: bool):
        """Slot: procesa cambio de modo escucha (wake-word detectado)."""
        if listening and not self._listening_mode:
            # Iniciar modo listening con transición bars → bars
            self._listening_mode = True
            self._listening_time = 0.0
            self._shake_time = self.WAKE_SHAKE_DURATION
            self._shake_intensity = 1.0
            # Crear transición bars → bars (colapsa y expande)
            if self._visual_mode == "bars" and not self._transition:
                self._transition = Transition("bars", "bars", self._state)
        elif not listening and self._listening_mode:
            # Salir de listening mode con transición bars → bars
            self._listening_mode = False
            self._listening_time = 0.0
            # Crear transición bars → bars (colapsa y expande)
            if self._visual_mode == "bars" and not self._transition:
                self._transition = Transition("bars", "bars", self._state)

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

        # Auto-cerrar después de 8 segundos
        QTimer.singleShot(8000, self._hide_help_popup)

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

    # ========== TECLAS DE PRUEBA (DEBUG) ==========

    def keyPressEvent(self, event):
        """Teclas para probar animaciones manualmente."""
        from PyQt6.QtCore import Qt as QtCore

        key = event.key()

        # 1 = Activar listening mode (sacudida + pulso)
        if key == QtCore.Key.Key_1:
            print("[DEBUG] Tecla 1: Activando listening mode")
            self._on_listening_change(True)

        # 2 = Desactivar listening mode
        elif key == QtCore.Key.Key_2:
            print("[DEBUG] Tecla 2: Desactivando listening mode")
            self._on_listening_change(False)

        # 3 = Transición IDLE -> DICTATING
        elif key == QtCore.Key.Key_3:
            print("[DEBUG] Tecla 3: Transición IDLE -> DICTATING")
            self._on_state_change(State.DICTATING)

        # 4 = Transición DICTATING -> IDLE
        elif key == QtCore.Key.Key_4:
            print("[DEBUG] Tecla 4: Transición DICTATING -> IDLE")
            self._on_state_change(State.IDLE)

        # 5 = Solo sacudida (sin listening)
        elif key == QtCore.Key.Key_5:
            print("[DEBUG] Tecla 5: Sacudida")
            self._shake_time = self.WAKE_SHAKE_DURATION
            self._shake_intensity = 1.0

        # 6 = Simular mic alto
        elif key == QtCore.Key.Key_6:
            print("[DEBUG] Tecla 6: Mic alto (0.8)")
            self._mic_level = 0.8

        # 7 = Simular mic silencio
        elif key == QtCore.Key.Key_7:
            print("[DEBUG] Tecla 7: Mic silencio (0.0)")
            self._mic_level = 0.0

        # 8 = Transición DICTATING -> PAUSED
        elif key == QtCore.Key.Key_8:
            print("[DEBUG] Tecla 8: Transición DICTATING -> PAUSED")
            self._on_state_change(State.PAUSED)

        # 9 = Transición PAUSED -> DICTATING
        elif key == QtCore.Key.Key_9:
            print("[DEBUG] Tecla 9: Transición PAUSED -> DICTATING")
            self._on_state_change(State.DICTATING)

        # 0 = Reset a estado inicial
        elif key == QtCore.Key.Key_0:
            print("[DEBUG] Tecla 0: Reset a IDLE")
            self._state = State.IDLE
            self._visual_mode = "bars"
            self._transition = None
            self._bars_deploy = 1.0
            self._circle_scale = 1.0
            self._circle_color_progress = 1.0
            self._listening_mode = False
            self._shake_time = 0.0
            self._mic_level = 0.0

        # ESPACIO = Modo silencioso (entrada de texto por teclado)
        elif key == QtCore.Key.Key_Space:
            self._show_silent_input()

    # ========== MODO SILENCIOSO ==========

    def set_silent_input_callback(self, callback):
        """Configura el callback para procesar texto del modo silencioso."""
        self._on_silent_input_callback = callback

    def _show_silent_input(self):
        """Muestra ventana de entrada de texto para modo silencioso."""
        from PyQt6.QtWidgets import QLineEdit

        # Cerrar si ya existe
        if self._silent_input_window:
            self._silent_input_window.close()
            self._silent_input_window = None

        # Crear ventana
        self._silent_input_window = QWidget(None, Qt.WindowType.FramelessWindowHint |
                                            Qt.WindowType.WindowStaysOnTopHint |
                                            Qt.WindowType.Tool)
        self._silent_input_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self._silent_input_window)
        layout.setContentsMargins(0, 0, 0, 0)

        # Frame contenedor
        frame = QWidget()
        frame.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 20, 240);
                border-radius: 8px;
                border: 1px solid #E74C3C;
            }
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)
        frame_layout.setSpacing(6)

        # Label
        label = QLabel("Modo silencioso - Escribe comando:")
        label.setStyleSheet("""
            color: #888;
            font-family: 'Segoe UI';
            font-size: 9px;
            background: transparent;
            border: none;
        """)
        frame_layout.addWidget(label)

        # Campo de texto
        self._silent_input_field = QLineEdit()
        self._silent_input_field.setStyleSheet("""
            QLineEdit {
                background-color: rgba(40, 40, 40, 200);
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 10px;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #E74C3C;
            }
        """)
        self._silent_input_field.setPlaceholderText("ej: bloquear, captura, ayuda...")
        self._silent_input_field.returnPressed.connect(self._on_silent_input_submit)
        frame_layout.addWidget(self._silent_input_field)

        # Hint
        hint = QLabel("Enter = ejecutar | Esc = cancelar")
        hint.setStyleSheet("""
            color: #555;
            font-family: 'Segoe UI';
            font-size: 8px;
            background: transparent;
            border: none;
        """)
        frame_layout.addWidget(hint)

        layout.addWidget(frame)

        # Posicionar encima del overlay
        self._silent_input_window.adjustSize()
        input_width = self._silent_input_window.width()
        overlay_center_x = self.x() + self.width() / 2
        x = int(overlay_center_x - input_width / 2)
        y = self.y() - self._silent_input_window.height() - 10
        self._silent_input_window.move(x, y)

        # Instalar event filter para Escape
        self._silent_input_field.installEventFilter(self)

        # Mostrar y forzar foco
        self._silent_input_window.show()
        self._silent_input_window.raise_()
        self._silent_input_window.activateWindow()
        self._silent_input_field.setFocus()
        self._silent_input_field.activateWindow()
        print("[Silent] Modo silencioso activado - escribe un comando")

    def _on_silent_input_submit(self):
        """Procesa el texto introducido en modo silencioso."""
        if not self._silent_input_field:
            return

        text = self._silent_input_field.text().strip()
        self._hide_silent_input()

        if text and self._on_silent_input_callback:
            print(f"[Silent] Comando: '{text}'")
            self._on_silent_input_callback(text)

    def _hide_silent_input(self):
        """Cierra la ventana de entrada silenciosa."""
        if self._silent_input_window:
            self._silent_input_window.close()
            self._silent_input_window = None
            self._silent_input_field = None

    def eventFilter(self, obj, event):
        """Filtro de eventos para capturar Escape en el campo de texto."""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtCore import Qt as QtCore

        if event.type() == QEvent.Type.KeyPress:
            if event.key() == QtCore.Key.Key_Escape:
                print("[Silent] Cancelado")
                self._hide_silent_input()
                return True
        return super().eventFilter(obj, event)

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

        # Submenú DEBUG para probar animaciones
        debug_menu = menu.addMenu("🔧 Debug Animaciones")

        listening_on = debug_menu.addAction("▶ Listening Mode ON")
        listening_on.triggered.connect(lambda: self._debug_listening(True))

        listening_off = debug_menu.addAction("⏹ Listening Mode OFF")
        listening_off.triggered.connect(lambda: self._debug_listening(False))

        debug_menu.addSeparator()

        trans_dictating = debug_menu.addAction("🔴 IDLE → DICTATING")
        trans_dictating.triggered.connect(self._debug_to_dictating)

        trans_idle = debug_menu.addAction("⚪ DICTATING → IDLE")
        trans_idle.triggered.connect(self._debug_to_idle)

        debug_menu.addSeparator()

        shake_action = debug_menu.addAction("📳 Sacudida")
        shake_action.triggered.connect(self._debug_shake)

        mic_high = debug_menu.addAction("🔊 Mic Alto")
        mic_high.triggered.connect(lambda: self._debug_mic(0.8))

        mic_low = debug_menu.addAction("🔇 Mic Silencio")
        mic_low.triggered.connect(lambda: self._debug_mic(0.0))

        debug_menu.addSeparator()

        reset_action = debug_menu.addAction("↺ Reset")
        reset_action.triggered.connect(self._debug_reset)

        menu.addSeparator()

        # Toggle de auto-ayuda
        auto_help_text = "✓ Auto-ayuda" if self._auto_help else "  Auto-ayuda"
        auto_help_action = menu.addAction(auto_help_text)
        auto_help_action.triggered.connect(self._toggle_auto_help)

        menu.addSeparator()

        # Guardar posición
        save_action = menu.addAction("Guardar posición")
        save_action.triggered.connect(self._save_position)

        # Salir
        quit_action = menu.addAction("Salir")
        quit_action.triggered.connect(self.quit)

        menu.exec(event.globalPos())

    # ========== DEBUG HELPERS ==========

    def _debug_listening(self, on: bool):
        """Debug: activar/desactivar listening mode."""
        print(f"[DEBUG] Listening mode: {on}")
        self._on_listening_change(on)

    def _debug_to_dictating(self):
        """Debug: transición a DICTATING."""
        print("[DEBUG] Transición IDLE -> DICTATING")
        self._prev_state = State.IDLE
        self._state = State.DICTATING
        self._transition_time = 0.0
        self._transition_type = "collapse_then_expand"

    def _debug_to_idle(self):
        """Debug: transición a IDLE."""
        print("[DEBUG] Transición DICTATING -> IDLE")
        self._prev_state = State.DICTATING
        self._state = State.IDLE
        self._transition_time = 0.0
        self._transition_type = "collapse_then_expand"

    def _debug_shake(self):
        """Debug: solo sacudida."""
        print("[DEBUG] Sacudida")
        self._shake_time = self.WAKE_SHAKE_DURATION
        self._shake_intensity = 1.0

    def _debug_mic(self, level: float):
        """Debug: simular nivel de mic."""
        print(f"[DEBUG] Mic: {level}")
        self._mic_level = level

    def _debug_reset(self):
        """Debug: reset a estado inicial."""
        print("[DEBUG] Reset a IDLE")
        self._state = State.IDLE
        self._transition_type = None
        self._bars_deploy = 1.0
        self._circle_color_progress = 1.0
        self._listening_mode = False
        self._shake_time = 0.0
        self._mic_level = 0.0

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

    def _toggle_auto_help(self):
        """Activa/desactiva la auto-ayuda y guarda en config."""
        self._auto_help = not self._auto_help
        config = load_config()
        config["overlay"]["auto_help"] = self._auto_help
        save_config(config)
        status = "activada" if self._auto_help else "desactivada"
        print(f"[UI] Auto-ayuda {status}")

    # ========== HINTS ==========

    def set_hint_callbacks(self, on_listo: Callable, on_cancela: Callable):
        """Configura callbacks para los hints."""
        self._on_listo_callback = on_listo
        self._on_cancela_callback = on_cancela

    def show_hints(self):
        """Muestra los hints de listo/cancela vertical, justo encima del icono."""
        if self._hint_window:
            return

        self._hint_window = QWidget(None, Qt.WindowType.FramelessWindowHint |
                                    Qt.WindowType.WindowStaysOnTopHint |
                                    Qt.WindowType.Tool)
        self._hint_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Layout vertical compacto
        layout = QVBoxLayout(self._hint_window)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        # Botón listo - verde con palabra
        listo_btn = QPushButton("listo")
        listo_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(34, 85, 51, 220);
                color: #b4ffb4;
                border: none;
                border-radius: 4px;
                padding: 3px 10px;
                font-family: 'Segoe UI';
                font-size: 9px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: rgba(45, 110, 65, 230);
            }
        """)
        listo_btn.clicked.connect(self._on_hint_listo)
        layout.addWidget(listo_btn)

        # Botón cancela - rojo con palabra
        cancela_btn = QPushButton("cancela")
        cancela_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(90, 39, 39, 220);
                color: #ffb4b4;
                border: none;
                border-radius: 4px;
                padding: 3px 10px;
                font-family: 'Segoe UI';
                font-size: 9px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: rgba(120, 50, 50, 230);
            }
        """)
        cancela_btn.clicked.connect(self._on_hint_cancela)
        layout.addWidget(cancela_btn)

        # Ajustar tamaño
        self._hint_window.adjustSize()

        # Posicionar justo encima del núcleo
        hint_width = self._hint_window.width()
        overlay_center_x = self.x() + self.width() / 2
        x = int(overlay_center_x - hint_width / 2)
        y = self.y() + self._margin - self._hint_window.height() - 5
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
        layout.setContentsMargins(3, 3, 3, 3)

        # Botón reanuda - dorado con palabra
        reanuda_btn = QPushButton("reanuda")
        reanuda_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(139, 117, 0, 220);
                color: #ffe066;
                border: none;
                border-radius: 4px;
                padding: 3px 10px;
                font-family: 'Segoe UI';
                font-size: 9px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: rgba(180, 150, 0, 230);
            }
        """)
        reanuda_btn.clicked.connect(self._on_hint_reanuda)
        layout.addWidget(reanuda_btn)

        # Ajustar tamaño
        self._paused_hint_window.adjustSize()

        # Posicionar justo encima del núcleo
        hint_width = self._paused_hint_window.width()
        overlay_center_x = self.x() + self.width() / 2
        x = int(overlay_center_x - hint_width / 2)
        y = self.y() + self._margin - self._paused_hint_window.height() - 5
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
