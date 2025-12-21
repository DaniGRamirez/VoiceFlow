"""
VoiceFlow Overlay - Animation Components

Animation classes for the overlay:
- Spore: Organic pop-up that emerges from the nucleus
- Transition: Manages visual transitions between states
- perlin_noise_1d: Simple 1D Perlin-like noise for organic animation
"""

import math

from ui.easing import ease_out_back


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
    """Pop-up organico que emerge del nucleo."""

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

        # Tiempos de cada fase - comandos mas rapidos, textos mas lentos
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

        # Fase de aparicion (crecer + mover hacia abajo)
        if self.age < self.appear_time:
            t = self.age / self.appear_time
            self.scale = ease_out_back(t, 1.3)
            self.opacity = t
            # Mover de start_y a end_y durante aparicion
            self.y = self.start_y + (self.end_y - self.start_y) * ease_out_back(t, 1.0)

        # Fase estable (quieto, visible)
        elif self.age < self.appear_time + self.hold_time:
            self.scale = 1.0
            self.opacity = 1.0
            self.y = self.end_y  # Quedarse en posicion final

        # Fase de desvanecimiento (solo fade, sin mover)
        else:
            fade_t = (self.age - self.appear_time - self.hold_time) / self.fade_time
            self.scale = 1.0  # Mantener tamano
            self.opacity = 1.0 - fade_t
            self.y = self.end_y  # No moverse

        return True


class Transition:
    """
    Gestiona una transicion entre estados visuales.

    Las transiciones tienen 3 fases:
    1. COLLAPSE: El elemento origen colapsa hacia el centro
    2. HOLD: Pausa breve mostrando un punto blanco
    3. EXPAND: El elemento destino se expande desde el centro
    """

    def __init__(self, from_visual: str, to_visual: str, to_state):
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
        self.collapse_duration = 0.1   # Colapso rapido
        self.hold_duration = 0.3       # Pausa en el centro
        self.expand_duration = 0.25    # Expansion con rebote

    @property
    def total_duration(self) -> float:
        return self.collapse_duration + self.hold_duration + self.expand_duration

    def update(self, dt: float) -> bool:
        """
        Actualiza la transicion.

        Returns:
            True si la transicion ha terminado
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
        Progreso de la expansion (0 = no expandido, 1 = totalmente expandido).
        """
        if self.phase != "expand":
            return 0.0
        expand_time = self.time - self.collapse_duration - self.hold_duration
        return min(1.0, expand_time / self.expand_duration)
