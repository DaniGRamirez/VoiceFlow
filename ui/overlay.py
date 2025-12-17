import tkinter as tk

from core.state import State


class Overlay:
    """Ventana flotante siempre visible"""

    COLORS = {
        State.IDLE: "#666666",       # Gris
        State.DICTATING: "#4A90D9",  # Azul
        State.PROCESSING: "#F5A623", # Amarillo
    }

    SUCCESS_COLOR = "#7ED321"  # Verde
    ERROR_COLOR = "#D0021B"    # Rojo

    def __init__(self, size: int = 40, position: tuple = (1850, 50), opacity: float = 0.9):
        self.size = size
        self.root = tk.Tk()
        self._setup_window(position, opacity)
        self._create_canvas()
        self._state = State.IDLE

        # Drag support
        self._drag_data = {"x": 0, "y": 0}

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
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Salir", command=self.quit)
        menu.post(event.x_root, event.y_root)

    def set_state(self, state: State):
        self._state = state
        self.canvas.itemconfig(self.circle, fill=self.COLORS[state])

    def flash(self, color: str, duration_ms: int = 200):
        """Flash temporal de color"""
        original = self.COLORS[self._state]
        self.canvas.itemconfig(self.circle, fill=color)
        self.root.after(duration_ms, lambda: self.canvas.itemconfig(self.circle, fill=original))

    def flash_success(self):
        self.flash(self.SUCCESS_COLOR)

    def flash_error(self):
        self.flash(self.ERROR_COLOR)

    def update(self):
        self.root.update()

    def quit(self):
        self.root.quit()

    def get_position(self) -> tuple:
        """Retorna posicion actual para guardar en config"""
        return (self.root.winfo_x(), self.root.winfo_y())
