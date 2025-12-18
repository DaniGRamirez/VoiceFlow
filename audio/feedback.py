import os

# Usar pygame.mixer para sonidos (mas robusto)
PYGAME_AVAILABLE = False
pygame = None

try:
    import pygame as _pygame
    pygame = _pygame
    PYGAME_AVAILABLE = True
except ImportError:
    pass


class SoundPlayer:
    def __init__(self, sounds_dir: str, enabled: bool = True, volume: float = 0.5):
        self.sounds_dir = sounds_dir
        self.enabled = enabled
        self.volume = volume
        self._sounds: dict = {}
        self._initialized = False

        if PYGAME_AVAILABLE:
            self._init_mixer()
            self._load_sounds()

    def _init_mixer(self):
        """Inicializa pygame mixer de forma segura."""
        if self._initialized:
            return
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._initialized = True
            print("[Audio] pygame.mixer inicializado")
        except Exception as e:
            print(f"[Audio] Error inicializando mixer: {e}")

    def _load_sounds(self):
        if not self._initialized:
            return

        sound_files = {
            "pop": "pop.wav",
            "ding": "ding.wav",
            "success": "success.wav",
            "error": "error.wav",
            "click": "click.wav",
        }
        loaded = 0
        for name, filename in sound_files.items():
            path = os.path.join(self.sounds_dir, filename)
            if os.path.exists(path):
                try:
                    self._sounds[name] = pygame.mixer.Sound(path)
                    self._sounds[name].set_volume(self.volume)
                    loaded += 1
                except Exception as e:
                    print(f"[Audio] Error cargando {filename}: {e}")
            else:
                print(f"[Audio] Archivo no encontrado: {path}")

        print(f"[Audio] {loaded}/{len(sound_files)} sonidos cargados")

    def play(self, name: str):
        if not self.enabled or not PYGAME_AVAILABLE or not self._initialized:
            return
        if name in self._sounds:
            try:
                self._sounds[name].play()
            except Exception as e:
                print(f"[Audio] Error reproduciendo {name}: {e}")

    def set_volume(self, volume: float):
        self.volume = volume
        for sound in self._sounds.values():
            sound.set_volume(volume)

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
