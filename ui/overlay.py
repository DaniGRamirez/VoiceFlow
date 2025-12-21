"""
VoiceFlow Overlay - El Organismo

Un ente vivo que escucha, reacciona y responde.
No es una interfaz, es una presencia.

This module contains the main Overlay class which provides the visual
feedback for VoiceFlow. Animation, rendering, and debug functionality
are split into separate mixin modules for maintainability.
"""

import sys
from typing import Optional, Callable, List

from PyQt6.QtWidgets import (
    QApplication, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor

from core.state import State
from ui.easing import (
    breathing_factor, lerp_smooth, ease_out_back, lerp
)
from ui.overlay_animator import Spore, Transition
from ui.overlay_renderer import OverlayRendererMixin
from ui.overlay_debug import OverlayDebugMixin


class Overlay(OverlayRendererMixin, OverlayDebugMixin, QWidget):
    """
    El organismo vivo que representa VoiceFlow.

    Estados:
    - IDLE: Ovalo negro pequeno con borde plateado, deformacion tipo lava
    - DICTATING: Circulo rojizo, el mic deforma la forma significativamente
    - PROCESSING: Contraido, micro-vibraciones
    - PAUSED: Circulo amarillo/dorado
    """

    # Signals para comunicacion thread-safe
    state_signal = pyqtSignal(object)
    flash_signal = pyqtSignal(str, int)
    mic_level_signal = pyqtSignal(float)
    spore_signal = pyqtSignal(str, bool)  # texto, es_comando
    help_signal = pyqtSignal(list)  # lista de (comando, descripcion)
    listening_signal = pyqtSignal(bool)  # True = escuchando comando, False = fin

    # Colores
    IDLE_FILL = "#0a0a0a"  # Negro profundo
    IDLE_BORDER = "#8a8a8a"  # Plateado
    DICTATING_FILL = ("#B83227", "#E74C3C")  # Rojo calido
    PROCESSING_FILL = "#1a1a1a"  # Gris muy oscuro
    PAUSED_FILL = "#8B7500"  # Amarillo oscuro/dorado
    PAUSED_BORDER = "#D4AA00"  # Dorado brillante

    SUCCESS_COLOR = "#2D5A27"
    ERROR_COLOR = "#5A2727"

    # Configuracion de barras para IDLE (audio visualizer) - MAS COMPACTO
    BAR_COUNT = 11  # Numero impar para simetria
    BAR_WIDTH = 3  # Ancho de cada barra en px (era 4)
    BAR_GAP = 2  # Espacio entre barras (era 3)
    BAR_CORNER_RADIUS = 1.5  # Radio de esquinas redondeadas
    BAR_BASE_HEIGHT_RATIO = 0.25  # Altura minima (25% del contenedor)
    BAR_MAX_HEIGHT_RATIO = 0.85  # Altura maxima (85% del contenedor)

    # Duraciones de animaciones (segundos)
    TRANSITION_DURATION = 0.35  # Duracion de transiciones entre estados
    COLLAPSE_DURATION = 0.1  # Colapso rapido al centro (muy rapido)
    HOLD_DURATION = 0.5  # Pausa en el centro antes de expandir
    EXPAND_DURATION = 0.25  # Expansion despues del colapso
    WAKE_SHAKE_DURATION = 0.3  # Duracion de la sacudida al detectar wake-word
    LISTENING_PULSE_SPEED = 4.0  # Velocidad del pulso mientras escucha comando

    def __init__(self, size: int = 40, position: tuple = (1850, 50), opacity: float = 0.9, auto_help: bool = True):
        # Crear QApplication si no existe
        if QApplication.instance() is None:
            self._app = QApplication(sys.argv)
        else:
            self._app = QApplication.instance()

        super().__init__()

        # Configuracion base
        self._base_size = size
        self._idle_size = size * 0.5  # Mas pequeno en IDLE (era 0.7)
        self._current_size = float(self._idle_size)
        self._target_size = float(self._idle_size)
        self._display_size = float(self._idle_size)
        self._opacity = opacity
        self._position = position
        self._auto_help = auto_help  # Mostrar ayuda automatica en errores

        # Forma (1.0 = circulo, >1 = ovalo horizontal)
        self._current_squash = 2.2  # Ovalo mas aplanado en IDLE (era 1.6)
        self._target_squash = 2.2

        # Estado del organismo
        self._state = State.IDLE
        self._prev_state = State.IDLE

        # Animacion
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

        # Transicion de estado - momento de cambio visible
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
        self._silent_input_field = None
        self._on_silent_input_callback = None  # Callback para procesar texto

        # Drag
        self._drag_pos = None

        # === SISTEMA DE TRANSICIONES ===
        # Modo visual actual: que elemento se esta mostrando
        self._visual_mode = "bars"  # "bars" | "circle"

        # Transicion activa (None si no hay transicion en curso)
        self._transition: Optional[Transition] = None

        # Despliegue de barras (0 = punto central, 1 = desplegadas)
        self._bars_deploy = 1.0

        # Escala del circulo (0.3 = pequeno para transicion, 1.0 = normal)
        self._circle_scale = 1.0

        # Progreso de color del circulo (0 = blanco, 1 = color destino)
        self._circle_color_progress = 1.0

        # Estado de "escuchando comando" (wake-word detectado, barras como punto pulsante)
        self._listening_mode = False
        self._listening_time = 0.0

        # Sacudida por wake-word
        self._shake_time = 0.0
        self._shake_intensity = 0.0

        # Energia de las barras (basada en nivel de mic)
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

        # Margen amplio para glow, deformacion y spores
        self._margin = 60
        total_size = self._base_size + self._margin * 2
        self.setFixedSize(total_size + 40, total_size + 60)  # Extra para spores
        self.move(self._position[0], self._position[1])

        self.show()

    def _connect_signals(self):
        """Conecta signals para comunicacion thread-safe."""
        self.state_signal.connect(self._on_state_change)
        self.flash_signal.connect(self._on_flash)
        self.mic_level_signal.connect(self._on_mic_level)
        self.spore_signal.connect(self._spawn_spore)
        self.help_signal.connect(self._show_help_popup)
        self.listening_signal.connect(self._on_listening_change)

    def _start_animation(self):
        """Inicia el loop de animacion (60 FPS)."""
        self._timer = QTimer()
        self._timer.timeout.connect(self._animate)
        self._timer.start(16)  # ~60 FPS

    # ========== ANIMACION ==========

    def _animate(self):
        """Loop principal de animacion - el organismo vive."""
        dt = 0.016  # ~60 FPS
        self._time += dt
        self._phase += dt

        # Suavizar nivel de microfono - ASIMETRICO: sube rapido, baja lento
        if self._mic_level > self._smoothed_mic:
            self._smoothed_mic = lerp_smooth(self._smoothed_mic, self._mic_level, 0.7)
        else:
            self._smoothed_mic = lerp_smooth(self._smoothed_mic, self._mic_level, 0.05)

        # === ANIMACION DE TRANSICIONES (usando clase Transition) ===
        if self._transition:
            finished = self._transition.update(dt)

            if self._transition.phase == "collapse":
                # Colapsar elemento origen
                collapse = self._transition.get_collapse_progress()
                if self._transition.from_visual == "bars":
                    self._bars_deploy = 1.0 - collapse
                else:  # circle
                    self._circle_scale = 1.0 - collapse * 0.7  # 1.0 -> 0.3
                    self._circle_color_progress = 1.0 - collapse  # color -> blanco

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
                    self._circle_scale = 0.3 + expand_eased * 0.7  # 0.3 -> 1.0
                    self._circle_color_progress = expand  # blanco -> color
                    self._bars_deploy = 0.0

            # Transicion completada
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
            # pero con animacion de pulsacion (manejado en _draw_idle_bars)
            if not self._transition:
                self._bars_deploy = lerp_smooth(self._bars_deploy, 1.0, 0.1)
        elif self._visual_mode == "bars" and not self._transition:
            # Fuera de listening mode, las barras deben estar desplegadas
            self._bars_deploy = lerp_smooth(self._bars_deploy, 1.0, 0.1)

        # === ENERGIA DE BARRAS ===
        mic_shaped = pow(self._smoothed_mic, 0.5) if self._smoothed_mic > 0 else 0
        target_energy = min(mic_shaped * 1.5, 1.0)

        if target_energy > self._bars_energy:
            self._bars_energy = lerp(self._bars_energy, target_energy, 0.3)
        else:
            self._bars_energy = lerp(self._bars_energy, target_energy, 0.05)

        # Calcular objetivos segun estado
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

        # Interpolacion del tamano
        size_diff = self._target_size - self._current_size
        if size_diff > 0:
            self._size_velocity = self._size_velocity * 0.3 + size_diff * 0.7
        else:
            self._size_velocity = self._size_velocity * 0.9 + size_diff * 0.1
        self._current_size += self._size_velocity

        # Interpolacion del squash
        squash_diff = self._target_squash - self._current_squash
        self._squash_velocity = self._squash_velocity * 0.85 + squash_diff * 0.15
        self._current_squash += self._squash_velocity

        # Respiracion base
        breath = breathing_factor(self._time, rate=0.4, amplitude=0.02)
        self._display_size = self._current_size * breath

        # Transicion de estado vieja (para flash)
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
        """Actualiza el color segun el estado actual."""
        if self._state == State.IDLE:
            target_fill = QColor(self.IDLE_FILL)
            self._border_opacity = lerp_smooth(self._border_opacity, 1.0, 0.1)
        elif self._state == State.DICTATING:
            # Color varia con el mic
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

        # Transicion suave de color
        self._current_color = self._blend_colors(
            self._current_color, target_fill, 0.1
        )

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

        # === LOGICA DE DIBUJO SEGUN TRANSICION ===
        if self._transition:
            # Durante transicion
            if self._transition.phase == "collapse":
                # Colapsar elemento origen
                if self._transition.from_visual == "bars":
                    self._draw_idle_bars(painter, cx, cy, radius, fill_color)
                else:  # circle
                    # Circulo encogiendose y volviendose blanco
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
                    # Circulo creciendo y coloreandose
                    scaled_radius = radius * self._circle_scale
                    circle_color = self._get_circle_color()
                    if self._circle_color_progress > 0.3:
                        self._draw_glow(painter, cx, cy, scaled_radius, self._circle_color_progress)
                    self._draw_nucleus(painter, cx, cy, scaled_radius, circle_color)

        else:
            # Estado estable (sin transicion)
            if self._visual_mode == "bars":
                # Barras (IDLE o listening)
                self._draw_idle_bars(painter, cx, cy, radius, fill_color)
            else:
                # Circulo (DICTATING o PAUSED)
                circle_color = self._get_circle_color()
                if self._state == State.DICTATING:
                    self._draw_glow(painter, cx, cy, radius, 1.0)
                self._draw_nucleus(painter, cx, cy, radius, circle_color)

        # Dibujar spores
        self._draw_spores(painter, cx, cy)

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
        """Thread-safe: actualiza nivel de microfono (0.0 - 1.0)."""
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

            # === CREAR TRANSICION SEGUN ESTADOS ===
            # Determinar visual origen y destino
            from_visual = self._visual_mode

            # Visual destino segun estado
            if state == State.IDLE:
                to_visual = "bars"
            elif state == State.DICTATING:
                to_visual = "circle"
            elif state == State.PAUSED:
                to_visual = "circle"  # PAUSED usa circulo amarillo
            else:
                to_visual = "bars"

            # Crear transicion si hay cambio de visual o cambio de estado significativo
            if from_visual != to_visual or state in (State.DICTATING, State.PAUSED, State.IDLE):
                self._transition = Transition(from_visual, to_visual, state)
            else:
                self._transition = None

            # Mostrar/ocultar hints segun estado
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
            # Iniciar modo listening con transicion bars -> bars
            self._listening_mode = True
            self._listening_time = 0.0
            self._shake_time = self.WAKE_SHAKE_DURATION
            self._shake_intensity = 1.0
            # Crear transicion bars -> bars (colapsa y expande)
            if self._visual_mode == "bars" and not self._transition:
                self._transition = Transition("bars", "bars", self._state)
        elif not listening and self._listening_mode:
            # Salir de listening mode con transicion bars -> bars
            self._listening_mode = False
            self._listening_time = 0.0
            # Crear transicion bars -> bars (colapsa y expande)
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

        # Calcular radio visual real segun estado
        # En IDLE el ovalo es pequeno y aplanado, usar la altura visual
        if self._state == State.IDLE:
            visual_radius = (self._display_size / 2) / self._current_squash
        else:
            visual_radius = self._display_size / 2

        # Calcular la posicion Y basada en spores existentes
        # para evitar overlap (stack vertical)
        spore_height = 24  # Altura aproximada de un spore
        spore_spacing = 4  # Espacio entre spores

        # Comandos salen justo debajo del nucleo, textos mas abajo
        if is_command:
            base_y = cy + visual_radius + 5  # Comandos: muy pegados al nucleo
        else:
            base_y = cy + visual_radius + 25  # Textos: mas abajo

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

        # Calcular posicion Y final
        end_y = base_y + slot * (spore_height + spore_spacing)
        # Empieza en el borde inferior del nucleo
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

        # Anadir cada comando
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

            # Descripcion
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

        # Ajustar tamano
        self._help_window.adjustSize()

        # Posicionar encima del nucleo, centrado
        help_width = self._help_window.width()
        overlay_center_x = self.x() + self.width() / 2
        x = int(overlay_center_x - help_width / 2)
        y = self.y() - self._help_window.height() - 8
        self._help_window.move(x, y)
        self._help_window.show()

        # Auto-cerrar despues de 8 segundos
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

        # Boton listo - verde con palabra
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

        # Boton cancela - rojo con palabra
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

        # Ajustar tamano
        self._hint_window.adjustSize()

        # Posicionar justo encima del nucleo
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

        # Boton reanuda - dorado con palabra
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

        # Ajustar tamano
        self._paused_hint_window.adjustSize()

        # Posicionar justo encima del nucleo
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
