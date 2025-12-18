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


def lava_deformation(angle: float, time: float, num_blobs: int = 3) -> float:
    """
    Deformación tipo lámpara de lava - burbujas que se mueven lentamente.

    Args:
        angle: Ángulo en radianes (0 a 2π)
        time: Tiempo actual
        num_blobs: Número de "burbujas" de deformación

    Returns:
        Factor de deformación (0.85 a 1.15 típicamente)
    """
    deformation = 0.0

    for i in range(num_blobs):
        # Cada burbuja tiene su propia frecuencia y fase
        freq = 0.3 + i * 0.15  # Frecuencias diferentes
        phase_offset = i * 2.094  # ~120° de separación

        # Posición angular de la burbuja (se mueve con el tiempo)
        blob_angle = time * freq + phase_offset

        # Distancia angular entre el punto y la burbuja
        diff = angle - blob_angle
        # Normalizar a [-π, π]
        while diff > math.pi:
            diff -= 2 * math.pi
        while diff < -math.pi:
            diff += 2 * math.pi

        # Gaussian falloff - la burbuja tiene un radio de influencia
        width = 0.8 + 0.3 * math.sin(time * 0.5 + i)  # Ancho variable
        influence = math.exp(-(diff * diff) / (2 * width * width))

        # Amplitud de la burbuja (varía con el tiempo)
        amplitude = 0.08 + 0.04 * math.sin(time * 0.7 + i * 1.5)

        deformation += influence * amplitude

    return 1.0 + deformation


def blob_merge(angle: float, time: float) -> float:
    """
    Simula burbujas que se fusionan y separan.
    Más dramático que lava_deformation.

    Returns:
        Factor de deformación
    """
    # Dos burbujas principales que orbitan
    blob1_angle = time * 0.4
    blob2_angle = time * 0.4 + math.pi + math.sin(time * 0.2) * 0.5

    # Distancias a cada burbuja
    d1 = abs(angle - blob1_angle) % (2 * math.pi)
    if d1 > math.pi:
        d1 = 2 * math.pi - d1
    d2 = abs(angle - blob2_angle) % (2 * math.pi)
    if d2 > math.pi:
        d2 = 2 * math.pi - d2

    # Metaballs - suma de influencias
    influence1 = 0.12 / (0.3 + d1 * d1)
    influence2 = 0.12 / (0.3 + d2 * d2)

    return 1.0 + min(influence1 + influence2, 0.25)  # Cap para evitar picos extremos


def squash_stretch(angle: float, horizontal_factor: float = 1.5) -> float:
    """
    Deforma un círculo en un óvalo horizontal.

    Args:
        angle: Ángulo en radianes
        horizontal_factor: Factor de estiramiento horizontal (>1 = más ancho)

    Returns:
        Factor de radio para ese ángulo
    """
    # Ecuación de elipse en coordenadas polares
    # r = ab / sqrt((b*cos(θ))² + (a*sin(θ))²)
    # donde a = horizontal_factor, b = 1/horizontal_factor para mantener área
    a = horizontal_factor
    b = 1.0 / horizontal_factor

    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    denominator = math.sqrt((b * cos_a) ** 2 + (a * sin_a) ** 2)
    if denominator < 0.001:
        return 1.0

    return (a * b) / denominator
