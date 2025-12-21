"""
VoiceFlow Overlay - Rendering Components

Rendering methods for the overlay visual elements:
- Shadow, glow, and nucleus drawing
- Bars visualization for IDLE state
- Circle visualization for DICTATING/PAUSED states
- Spore (pop-up) rendering
"""

import math
from typing import List, TYPE_CHECKING

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPainterPath,
    QRadialGradient, QFont
)

from ui.easing import (
    organic_noise, ease_out_back, micro_vibration,
    squash_stretch, lerp
)
from ui.overlay_animator import perlin_noise_1d, Spore

if TYPE_CHECKING:
    from ui.overlay import Overlay


class OverlayRendererMixin:
    """
    Mixin class providing rendering methods for the Overlay.

    This class is designed to be mixed into the main Overlay class,
    providing all drawing/painting functionality.
    """

    def _blend_colors(self, c1: QColor, c2: QColor, factor: float) -> QColor:
        """Mezcla dos colores."""
        r = int(c1.red() + (c2.red() - c1.red()) * factor)
        g = int(c1.green() + (c2.green() - c1.green()) * factor)
        b = int(c1.blue() + (c2.blue() - c1.blue()) * factor)
        return QColor(r, g, b)

    def _get_circle_color(self: 'Overlay') -> QColor:
        """Calcula el color del circulo segun estado y progreso."""
        from core.state import State

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

        # Mezclar blanco y color destino segun progreso
        return self._blend_colors(white, target_color, self._circle_color_progress)

    def _draw_shadow(self: 'Overlay', painter: QPainter, cx: float, cy: float, radius: float):
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

    def _draw_glow(self: 'Overlay', painter: QPainter, cx: float, cy: float, radius: float,
                   intensity_mult: float = 1.0):
        """Halo difuso en grabacion.

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

    def _draw_nucleus(self: 'Overlay', painter: QPainter, cx: float, cy: float,
                      radius: float, color: QColor):
        """Dibuja el nucleo con deformacion organica y bordes suaves."""
        from core.state import State

        # En IDLE con squash alto o PAUSED, dibujar elipse simple con bordes muy redondeados
        if (self._state == State.IDLE and self._current_squash > 1.5) or self._state == State.PAUSED:
            # Elipse simple - mas limpio y redondeado
            rx = radius * self._current_squash
            ry = radius / self._current_squash

            # En IDLE: el tamano reacciona al microfono (moderado, con limite)
            if self._state == State.IDLE:
                mic_pulse = 1.0 + min(self._smoothed_mic * 0.8, 0.5)  # Maximo 50% mas grande
                rx *= mic_pulse
                ry *= mic_pulse

            # Aplicar respiracion sutil con lava muy suave
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

                # En IDLE: el borde reacciona al microfono (moderado, con limite)
                if self._state == State.IDLE:
                    # Opacidad base + boost por microfono
                    mic_opacity = min(1.0, self._border_opacity + self._smoothed_mic * 0.5)
                    border_color.setAlphaF(mic_opacity)
                    # Grosor varia con el microfono (1.5 a 4px maximo)
                    border_width = 1.5 + min(self._smoothed_mic * 3.0, 2.5)
                    painter.setPen(QPen(border_color, border_width))
                else:
                    border_color.setAlphaF(self._border_opacity)
                    painter.setPen(QPen(border_color, 1.5))
            else:
                painter.setPen(Qt.PenStyle.NoPen)

            painter.drawPath(path)
            return

        # Para otros estados: deformacion organica completa
        num_points = 32

        points = []
        for i in range(num_points):
            angle = (i / num_points) * 2 * math.pi

            # Base: squash/stretch para ovalo
            squash_factor = squash_stretch(angle, self._current_squash)

            # Deformacion segun estado
            if self._state == State.DICTATING:
                # Deformacion moderada con el mic
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

    def _draw_point(self: 'Overlay', painter: QPainter, cx: float, cy: float):
        """
        Dibuja un punto blanco pulsante en el centro.
        Usado durante la fase "hold" de las transiciones.
        """
        # Pulsacion sutil
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

    def _draw_idle_bars(self: 'Overlay', painter: QPainter, cx: float, cy: float,
                        radius: float, color: QColor):
        """
        Dibuja barras de audio visualizer para el estado IDLE.

        Comportamiento:
        - Silencio: onda suave viajando de izquierda a derecha
        - Con mic: barras energeticas con perfil de campana
        - Transicion: barras colapsan/despliegan desde el centro
        - Listening mode: pulso ritmico urgente + sacudida
        - Fondo negro solido fijo, solo las barras escalan
        """
        # Dimensiones del contenedor - crece con energia
        base_container_height = 14  # Altura minima en silencio
        max_container_height = 24   # Altura maxima con volumen
        energy = self._bars_energy

        # Usar _bars_deploy directamente (ya se actualiza en _animate())
        deploy = self._bars_deploy

        # Cuando esta colapsado, usar altura fija para que el "punto" sea visible
        # Altura del punto: similar a cuando hay voz (18px)
        collapsed_container_height = 18
        normal_container_height = base_container_height + (max_container_height - base_container_height) * energy

        # Si deploy < 0.3, usar altura de punto; sino transicion gradual
        if deploy < 0.3:
            container_height = collapsed_container_height
        else:
            transition = (deploy - 0.3) / 0.7
            container_height = lerp(collapsed_container_height, normal_container_height, transition)

        # Ancho del contenedor depende del despliegue
        full_container_width = (self.BAR_COUNT * self.BAR_WIDTH +
                               (self.BAR_COUNT - 1) * self.BAR_GAP)
        # Contraido: punto compacto (25% del ancho - mas pequeno que antes)
        contracted_ratio = 0.25
        contracted_width = full_container_width * contracted_ratio

        # === SACUDIDA (shake) - SUTIL ===
        shake_offset_x = 0
        shake_offset_y = 0
        if self._shake_intensity > 0:
            # Sacudida sutil (valores reducidos a la mitad)
            shake_freq = 17.5  # Frecuencia (era 35)
            shake_amp = 5.0 * self._shake_intensity  # Amplitud maxima 5px (era 10)
            shake_offset_x = math.sin(self._time * shake_freq) * shake_amp
            shake_offset_y = math.cos(self._time * shake_freq * 1.3) * shake_amp * 0.6

        # Ancho del contenedor interpolado segun despliegue
        container_width = lerp(contracted_width, full_container_width, deploy)

        # Posicion del contenedor (centrado, con shake)
        container_x = cx - container_width / 2 + shake_offset_x
        container_y = cy - container_height / 2 + shake_offset_y

        # === FONDO NEGRO SOLIDO (escala con energia) ===
        padding = 5
        bg_rect = QRectF(
            container_x - padding,
            container_y - padding,
            container_width + padding * 2,
            container_height + padding * 2
        )
        painter.setBrush(QBrush(QColor(0, 0, 0)))  # Negro solido
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bg_rect, 6, 6)

        # Alturas base y maxima para barras
        base_height = container_height * self.BAR_BASE_HEIGHT_RATIO
        max_height = container_height * self.BAR_MAX_HEIGHT_RATIO
        height_range = max_height - base_height

        # Centro de las barras (para perfil de campana)
        center_idx = self.BAR_COUNT // 2

        # === DIBUJAR CADA BARRA ===
        # Calcular espaciado contraido (proporcional pero mas junto)
        contracted_bar_width = self.BAR_WIDTH * 0.6  # 60% del ancho normal
        contracted_gap = (contracted_width - self.BAR_COUNT * contracted_bar_width) / max(1, self.BAR_COUNT - 1)

        for i in range(self.BAR_COUNT):
            # === ANIMACION DE DESPLIEGUE ===
            # Aplicar easing al despliegue (ease out back para rebote)
            deploy_eased = ease_out_back(deploy, 1.2) if deploy < 1.0 else 1.0

            # Posicion X desplegada (full width)
            deployed_x = container_x + i * (self.BAR_WIDTH + self.BAR_GAP)
            # Posicion X contraida (mantiene separacion dentro de contracted_width)
            contracted_x = container_x + i * (contracted_bar_width + contracted_gap)

            # Interpolar posicion X entre contraida y desplegada
            bar_x = lerp(contracted_x, deployed_x, deploy_eased)

            # Ancho de barra tambien interpolado
            bar_width = lerp(contracted_bar_width, self.BAR_WIDTH, deploy_eased)

            # === PARAMETROS UNICOS POR BARRA ===
            bar_seed = i * 137.5  # Golden angle
            phase_offset = (i / self.BAR_COUNT) * math.pi * 2
            speed_mult = 0.8 + (perlin_noise_1d(bar_seed) + 1) * 0.2

            # Desplazamiento vertical por onda (se calcula abajo)
            wave_lift = 0.0

            # === MODO LISTENING: Pulso ritmico moderado ===
            if self._listening_mode:
                # Pulso mas lento y menos extremo
                pulse_speed = 2.5  # Mas lento (era 4.0)
                pulse_raw = math.sin(self._listening_time * pulse_speed * math.pi * 2)

                # Suavizar un poco (no tan cuadrado)
                pulse = (math.tanh(pulse_raw * 2) + 1) / 2  # 0-1

                # Variacion minima por barra para que no sea robotico
                pulse_var = perlin_noise_1d(self._listening_time * 2 + bar_seed * 0.1) * 0.03

                # RANGO MODERADO: de pequeno (0.15) a medio-alto (0.7)
                height_factor = 0.15 + pulse * 0.55 + pulse_var
                height_factor = max(0.15, min(0.75, height_factor))

            else:
                # === MODO NORMAL ===

                # === MODO SILENCIO: Barras MICRO (casi invisibles) con onda ping-pong ===
                wave_speed = 2.4  # Doble de rapido (era 1.2)
                wave_width = 2.5  # Estrecha para mas impacto

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
                # Usar potencia para hacer la onda mas "puntiaguda" (mas contraste)
                wave_intensity = math.exp(-(dist_to_wave ** 2) / (2 * (wave_width / 2) ** 2))
                wave_intensity = pow(wave_intensity, 0.7)  # Mas potencia en el pico

                organic_var = perlin_noise_1d(self._time * 0.3 * speed_mult + bar_seed) * 0.003
                # Barras MICRO: base 0.003 (1/3 de antes), onda anade hasta 0.12
                silence_component = 0.003 + wave_intensity * 0.12 + organic_var

                # Desplazamiento vertical por la onda (sube cuando pasa) - mas pronunciado
                # Solo en silencio (energy baja), la onda "levanta" las barras
                wave_lift = wave_intensity * 4.0 * (1.0 - energy)  # Hasta 4px arriba

                # === MODO ENERGETICO: Perfil de campana + ruido ===
                sigma = self.BAR_COUNT / 3.0
                distance_from_center = abs(i - center_idx)
                bell_profile = math.exp(-(distance_from_center ** 2) / (2 * sigma ** 2))

                energy_noise = perlin_noise_1d(self._time * 2.5 * speed_mult + bar_seed * 2) * 0.15
                energy_wave = math.sin(self._time * 3.0 + phase_offset) * 0.1
                energy_component = bell_profile * 0.7 + energy_noise + energy_wave + 0.2

                # Mezclar segun energia
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
                # Transicion gradual: de punto a barra normal
                # Mapear deploy de 0.3-1.0 a 0.0-1.0 para la transicion
                transition = (deploy_eased - 0.3) / 0.7
                point_height = container_height * 0.6
                normal_height = (base_height + height_range * height_factor)
                bar_height = lerp(point_height, normal_height, transition)

            # Posicion Y (centrada verticalmente, con wave_lift hacia arriba)
            # No aplicar wave_lift cuando esta colapsado (todas quietas en el centro)
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

    def _draw_spores(self: 'Overlay', painter: QPainter, cx: float, cy: float):
        """Dibuja los spores (pop-ups organicos) con fondo."""
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

            # Posicion centrada
            x = spore.center_x - bg_width / 2 * spore.scale
            y = spore.y - bg_height / 2 * spore.scale

            painter.save()
            painter.translate(x + bg_width / 2 * spore.scale,
                            y + bg_height / 2 * spore.scale)
            painter.scale(spore.scale, spore.scale)

            # Fondo segun tipo
            if spore.is_command:
                # Verde para comandos aceptados
                bg_color = QColor(34, 85, 51, int(220 * spore.opacity))
            else:
                # Gris oscuro para texto normal
                bg_color = QColor(20, 20, 20, int(200 * spore.opacity))

            painter.setBrush(QBrush(bg_color))
            painter.setPen(Qt.PenStyle.NoPen)

            # Rectangulo redondeado
            bg_rect = QRectF(-bg_width / 2, -bg_height / 2, bg_width, bg_height)
            painter.drawRoundedRect(bg_rect, 6, 6)

            # Color del texto segun tipo
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
