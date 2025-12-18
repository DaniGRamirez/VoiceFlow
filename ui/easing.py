"""
Funciones de easing orgánicas para animaciones fluidas.
Basadas en curvas naturales, no mecánicas.
"""

import math
import random


def ease_out_elastic(t: float, overshoot: float = 0.3) -> float:
    """
    Overshoot sutil, como una gota que se asienta.
    Ideal para transiciones de estado.
    """
    if t == 0 or t == 1:
        return t
    p = 0.4
    s = p / 4
    return pow(2, -10 * t) * math.sin((t - s) * (2 * math.pi) / p) * overshoot + 1


def ease_out_back(t: float, overshoot: float = 1.2) -> float:
    """
    Para pop-ups emergiendo - pasa del objetivo y vuelve.
    """
    c1 = overshoot
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


def ease_in_quad(t: float) -> float:
    """Aceleración suave - para desapariciones."""
    return t * t


def ease_out_quad(t: float) -> float:
    """Desaceleración suave - para apariciones."""
    return 1 - (1 - t) * (1 - t)


def ease_in_out_sine(t: float) -> float:
    """Transición muy suave, ideal para respiración."""
    return -(math.cos(math.pi * t) - 1) / 2


def lerp(a: float, b: float, t: float) -> float:
    """Interpolación lineal básica."""
    return a + (b - a) * t


def lerp_smooth(current: float, target: float, factor: float) -> float:
    """
    Interpolación suave con factor de suavizado.
    Factor típico: 0.1 - 0.3 (más bajo = más suave)
    """
    return current + (target - current) * factor


def lerp_elastic(current: float, target: float, factor: float,
                 velocity: float = 0.0, damping: float = 0.8) -> tuple:
    """
    Interpolación con física elástica (overshoot natural).
    Retorna (nuevo_valor, nueva_velocidad)
    """
    diff = target - current
    velocity = velocity * damping + diff * factor
    new_value = current + velocity
    return new_value, velocity


# Ruido Perlin simplificado para deformaciones orgánicas
def _fade(t: float) -> float:
    """Curva de suavizado para Perlin."""
    return t * t * t * (t * (t * 6 - 15) + 10)


def _lerp_noise(a: float, b: float, t: float) -> float:
    return a + t * (b - a)


# Tabla de gradientes para ruido 1D
_GRADIENTS = [1, -1, 1, -1, 1, -1, 1, -1]
_PERM = list(range(256))
random.seed(42)  # Semilla fija para consistencia
random.shuffle(_PERM)
_PERM = _PERM + _PERM  # Duplicar para evitar overflow


def perlin_noise_1d(x: float) -> float:
    """
    Ruido Perlin 1D simplificado.
    Retorna valor entre -1 y 1.
    Útil para deformaciones orgánicas del borde.
    """
    xi = int(x) & 255
    xf = x - int(x)

    u = _fade(xf)

    g0 = _GRADIENTS[_PERM[xi] & 7]
    g1 = _GRADIENTS[_PERM[xi + 1] & 7]

    n0 = g0 * xf
    n1 = g1 * (xf - 1)

    return _lerp_noise(n0, n1, u)


def organic_noise(angle: float, time: float, scale: float = 2.0,
                  amplitude: float = 0.02) -> float:
    """
    Genera ruido orgánico para deformación de círculos.

    Args:
        angle: Ángulo en radianes (0 a 2π)
        time: Tiempo actual (para animación)
        scale: Escala del ruido (más alto = más detalle)
        amplitude: Amplitud de la deformación (0.02 = ±2%)

    Returns:
        Factor de deformación (ej: 0.98 a 1.02)
    """
    noise_val = perlin_noise_1d(angle * scale + time * 0.5)
    return 1.0 + noise_val * amplitude


def breathing_factor(time: float, rate: float = 0.5, amplitude: float = 0.03) -> float:
    """
    Genera factor de respiración.

    Args:
        time: Tiempo actual
        rate: Velocidad de respiración (0.5 = ciclo de ~12s)
        amplitude: Amplitud de la respiración (0.03 = ±3%)

    Returns:
        Factor multiplicador (ej: 0.97 a 1.03)
    """
    return 1.0 + math.sin(time * rate) * amplitude


def micro_vibration(amplitude: float = 0.5) -> float:
    """
    Genera micro-vibración aleatoria para estado PENSANDO.

    Args:
        amplitude: Amplitud en píxeles

    Returns:
        Offset aleatorio en píxeles
    """
    return random.uniform(-amplitude, amplitude)
