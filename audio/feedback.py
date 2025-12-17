import os

# Usar pygame.mixer para sonidos (mas robusto)
try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class SoundPlayer:
    def __init__(self, sounds_dir: str, enabled: bool = True, volume: float = 0.5):
        self.sounds_dir = sounds_dir
        self.enabled = enabled
        self.volume = volume
        self._sounds: dict = {}

        if PYGAME_AVAILABLE:
            self._load_sounds()

    def _load_sounds(self):
        sound_files = {
            "pop": "pop.wav",
            "ding": "ding.wav",
            "success": "success.wav",
            "error": "error.wav",
            "click": "click.wav",
        }
        for name, filename in sound_files.items():
            path = os.path.join(self.sounds_dir, filename)
            if os.path.exists(path):
                self._sounds[name] = pygame.mixer.Sound(path)
                self._sounds[name].set_volume(self.volume)

    def play(self, name: str):
        if not self.enabled or not PYGAME_AVAILABLE:
            return
        if name in self._sounds:
            self._sounds[name].play()

    def set_volume(self, volume: float):
        self.volume = volume
        for sound in self._sounds.values():
            sound.set_volume(volume)

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
