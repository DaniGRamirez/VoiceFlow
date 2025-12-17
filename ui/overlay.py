import tkinter as tk
import queue
import math

from core.state import State


class Overlay:
    """Ventana flotante siempre visible"""

    COLORS = {
        State.IDLE: "#666666",       # Gris
        State.DICTATING: "#E74C3C",  # Rojo (grabando)
        State.PROCESSING: "#F5A623", # Amarillo
    }

    SUCCESS_COLOR = "#7ED321"  # Verde
    ERROR_COLOR = "#D0021B"    # Rojo

    # Colores para pulse en idle
    IDLE_COLOR_LIGHT = "#888888"
    IDLE_COLOR_DARK = "#555555"

    # Color para efecto de grabacion
    RECORDING_COLOR_LIGHT = "#FF6B6B"
    RECORDING_COLOR_DARK = "#C0392B"

    def __init__(self, size: int = 40, position: tuple = (1850, 50), opacity: float = 0.9):
        self.size = size
        self.root = tk.Tk()
        self._setup_window(position, opacity)
        self._create_canvas()
        self._state = State.IDLE

        # Drag support
        self._drag_data = {"x": 0, "y": 0}

        # Queue para comunicacion thread-safe
        self._ui_queue = queue.Queue()

        # Animation state
        self._animation_phase = 0.0
        self._mic_level = 0.0
        self._hint_window = None

        # Iniciar animacion
        self._animate()

    def _setup_window(self, position: tuple, opacity: float):
        self.root.overrideredirect(True)  # Sin bordes
        self.root.attributes('-topmost', True)  # Siempre encima
        self.root.attributes('-alpha', opacity)  # Transparencia
        self.root.geometry(f"{self.size}x{self.size}+{position[0]}+{position[1]}")

        # Hacer la ventana draggable
        self.root.bind('<Button-1>', self._start_drag)
        self.root.bind('<B1-Motion>', self._on_drag)

        # Click derecho para menu
        self.root.bind('<Button-3>', self._show_menu)

    def _create_canvas(self):
        self.canvas = tk.Canvas(
            self.root,
            width=self.size,
            height=self.size,
            highlightthickness=0,
            bg='black'
        )
        self.canvas.pack()

        # Circulo principal
        padding = 4
        self.circle = self.canvas.create_oval(
            padding, padding,
            self.size - padding, self.size - padding,
            fill=self.COLORS[State.IDLE],
            outline=""
        )

    def _start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_data["x"]
        y = self.root.winfo_y() + event.y - self._drag_data["y"]
        self.root.geometry(f"+{x}+{y}")

    def _show_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0, bg="#2C2C2C", fg="white",
                      activebackground="#4A4A4A", activeforeground="white",
                      font=("Segoe UI", 9))

        # Estado actual
        state_text = {
            State.IDLE: "🟢 Idle",
            State.DICTATING: "🔴 Dictando",
            State.PROCESSING: "🟡 Procesando"
        }
        menu.add_command(label=state_text.get(self._state, "Estado"), state="disabled")
        menu.add_separator()

        # Opcion de transparencia
        opacity_menu = tk.Menu(menu, tearoff=0, bg="#2C2C2C", fg="white",
                              activebackground="#4A4A4A", activeforeground="white")
        for opacity in [0.5, 0.7, 0.9, 1.0]:
            opacity_menu.add_command(
                label=f"{int(opacity*100)}%",
                command=lambda o=opacity: self.root.attributes('-alpha', o)
            )
        menu.add_cascade(label="Transparencia", menu=opacity_menu)

        # Opcion de tamaño
        size_menu = tk.Menu(menu, tearoff=0, bg="#2C2C2C", fg="white",
                           activebackground="#4A4A4A", activeforeground="white")
        for size in [30, 40, 50, 60]:
            size_menu.add_command(
                label=f"{size}px",
                command=lambda s=size: self._resize(s)
            )
        menu.add_cascade(label="Tamaño", menu=size_menu)

        menu.add_separator()

        # Guardar posicion
        menu.add_command(label="📍 Guardar posición", command=self._save_position)

        menu.add_separator()
        menu.add_command(label="❌ Salir", command=self.quit)

        menu.post(event.x_root, event.y_root)

    def _resize(self, new_size: int):
        """Cambia el tamaño del overlay"""
        self.size = new_size
        self.root.geometry(f"{new_size}x{new_size}")
        self.canvas.config(width=new_size, height=new_size)
        padding = 4
        self.canvas.coords(self.circle, padding, padding, new_size - padding, new_size - padding)

    def _save_position(self):
        """Guarda la posicion actual (placeholder - necesita config manager)"""
        pos = self.get_position()
        print(f"[UI] Posición guardada: {pos}")
        # TODO: Integrar con config.save_config()

    def set_state(self, state: State):
        """Thread-safe: encola cambio de estado"""
        self._ui_queue.put(("state", state))

    def flash(self, color: str, duration_ms: int = 200):
        """Thread-safe: encola flash de color"""
        self._ui_queue.put(("flash", color, duration_ms))

    def flash_success(self):
        self.flash(self.SUCCESS_COLOR)

    def flash_error(self):
        self.flash(self.ERROR_COLOR)

    def _process_queue(self):
        """Procesa comandos de UI en el thread principal"""
        try:
            while True:
                cmd = self._ui_queue.get_nowait()
                if cmd[0] == "state":
                    state = cmd[1]
                    old_state = self._state
                    self._state = state
                    # Mostrar/ocultar hints segun estado
                    if state == State.DICTATING and old_state != State.DICTATING:
                        self.show_hints()
                    elif state != State.DICTATING and old_state == State.DICTATING:
                        self.hide_hints()
                elif cmd[0] == "flash":
                    color, duration_ms = cmd[1], cmd[2]
                    # No interrumpir animacion, solo flash temporal
                    self.canvas.itemconfig(self.circle, fill=color)
                    self.root.after(duration_ms, lambda: None)  # La animacion restaurara el color
                elif cmd[0] == "mic_level":
                    self._mic_level = cmd[1]
        except queue.Empty:
            pass

    def update(self):
        self._process_queue()
        self.root.update()

    def quit(self):
        self.root.quit()

    def get_position(self) -> tuple:
        """Retorna posicion actual para guardar en config"""
        return (self.root.winfo_x(), self.root.winfo_y())

    def _interpolate_color(self, color1: str, color2: str, factor: float) -> str:
        """Interpola entre dos colores hex"""
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)

        r = int(r1 + (r2 - r1) * factor)
        g = int(g1 + (g2 - g1) * factor)
        b = int(b1 + (b2 - b1) * factor)

        return f"#{r:02x}{g:02x}{b:02x}"

    def _animate(self):
        """Animacion continua del overlay"""
        self._animation_phase += 0.05

        if self._state == State.IDLE:
            # Pulso suave y calmado (ciclo de ~3 segundos)
            factor = (math.sin(self._animation_phase * 0.5) + 1) / 2
            color = self._interpolate_color(self.IDLE_COLOR_DARK, self.IDLE_COLOR_LIGHT, factor)
            self.canvas.itemconfig(self.circle, fill=color)

        elif self._state == State.DICTATING:
            # Efecto de grabacion: pulso mas rapido + respuesta a mic
            base_factor = (math.sin(self._animation_phase * 2) + 1) / 2
            # Combinar con nivel de microfono
            combined_factor = min(1.0, base_factor * 0.5 + self._mic_level * 0.5)
            color = self._interpolate_color(self.RECORDING_COLOR_DARK, self.RECORDING_COLOR_LIGHT, combined_factor)
            self.canvas.itemconfig(self.circle, fill=color)

        # Continuar animacion cada 50ms
        self.root.after(50, self._animate)

    def set_mic_level(self, level: float):
        """Thread-safe: actualiza nivel de microfono (0.0 - 1.0)"""
        self._ui_queue.put(("mic_level", min(1.0, max(0.0, level))))

    def show_hints(self):
        """Muestra popup con hints de 'listo' y 'cancela'"""
        if self._hint_window:
            return  # Ya visible

        self._hint_window = tk.Toplevel(self.root)
        self._hint_window.overrideredirect(True)
        self._hint_window.attributes('-topmost', True)
        self._hint_window.attributes('-alpha', 0.95)

        # Posicionar debajo del overlay
        x = self.root.winfo_x()
        y = self.root.winfo_y() + self.size + 5

        frame = tk.Frame(self._hint_window, bg="#2C2C2C", padx=8, pady=6)
        frame.pack()

        # Estilo de hints
        tk.Label(frame, text="🎤 Dictando...", bg="#2C2C2C", fg="#E74C3C", font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(frame, text="", bg="#2C2C2C").pack()  # Spacer

        # Botones de hint
        btn_frame = tk.Frame(frame, bg="#2C2C2C")
        btn_frame.pack()

        listo_btn = tk.Label(btn_frame, text="✓ listo", bg="#27AE60", fg="white",
                            font=("Segoe UI", 9, "bold"), padx=8, pady=2)
        listo_btn.pack(side="left", padx=2)

        cancela_btn = tk.Label(btn_frame, text="✗ cancela", bg="#E74C3C", fg="white",
                              font=("Segoe UI", 9, "bold"), padx=8, pady=2)
        cancela_btn.pack(side="left", padx=2)

        self._hint_window.geometry(f"+{x}+{y}")

    def hide_hints(self):
        """Oculta popup de hints"""
        if self._hint_window:
            self._hint_window.destroy()
            self._hint_window = None
