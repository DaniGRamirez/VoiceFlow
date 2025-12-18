import customtkinter as ctk
import queue
import math

from core.state import State
from config.settings import save_config, load_config


# Configurar tema oscuro
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class Overlay:
    """Ventana flotante moderna con CustomTkinter"""

    COLORS = {
        State.IDLE: "#666666",       # Gris
        State.DICTATING: "#E74C3C",  # Rojo (grabando)
        State.PROCESSING: "#F5A623", # Amarillo
    }

    SUCCESS_COLOR = "#7ED321"  # Verde
    ERROR_COLOR = "#D0021B"    # Rojo
    UNKNOWN_COLOR = "#F5A623"  # Amarillo - comando no reconocido

    # Colores para pulse en idle
    IDLE_COLOR_LIGHT = "#888888"
    IDLE_COLOR_DARK = "#555555"

    # Color para efecto de grabacion
    RECORDING_COLOR_LIGHT = "#FF6B6B"
    RECORDING_COLOR_DARK = "#C0392B"

    def __init__(self, size: int = 40, position: tuple = (1850, 50), opacity: float = 0.9):
        self.size = size
        self._opacity = opacity
        self.root = ctk.CTk()
        self._setup_window(position, opacity)
        self._create_indicator()
        self._state = State.IDLE

        # Drag support
        self._drag_data = {"x": 0, "y": 0}

        # Queue para comunicacion thread-safe
        self._ui_queue = queue.Queue()

        # Animation state
        self._animation_phase = 0.0
        self._mic_level = 0.0
        self._hint_window = None
        self._flash_active = False

        # Transicion de estados
        self._transition_progress = 1.0  # 1.0 = transicion completa
        self._prev_state = State.IDLE

        # Callbacks para hints (se configuran desde main.py)
        self._on_listo_callback = None
        self._on_cancela_callback = None

        # Iniciar animacion
        self._animate()

    def _setup_window(self, position: tuple, opacity: float):
        self.root.overrideredirect(True)  # Sin bordes
        self.root.attributes('-topmost', True)  # Siempre encima
        self.root.attributes('-alpha', opacity)  # Transparencia
        self.root.geometry(f"{self.size}x{self.size}+{position[0]}+{position[1]}")

        # Hacer fondo transparente en Windows
        self.root.configure(bg='black')
        self.root.wm_attributes('-transparentcolor', 'black')

        # Hacer la ventana draggable
        self.root.bind('<Button-1>', self._start_drag)
        self.root.bind('<B1-Motion>', self._on_drag)

        # Click derecho para menu
        self.root.bind('<Button-3>', self._show_menu)

        # Tooltip al hover
        self.root.bind('<Enter>', self._show_tooltip)
        self.root.bind('<Leave>', self._hide_tooltip)
        self._tooltip_window = None

    def _create_indicator(self):
        """Crea el indicador circular con canvas para animaciones suaves"""
        self.canvas = ctk.CTkCanvas(
            self.root,
            width=self.size,
            height=self.size,
            highlightthickness=0,
            bg='black'
        )
        self.canvas.pack()

        # Circulo principal con borde suave
        padding = 2
        # Sombra/glow
        self.glow = self.canvas.create_oval(
            padding, padding,
            self.size - padding, self.size - padding,
            fill="#333333",
            outline=""
        )

        # Arco indicador de nivel de mic (solo visible en DICTATING)
        arc_padding = 1
        self.mic_arc = self.canvas.create_arc(
            arc_padding, arc_padding,
            self.size - arc_padding, self.size - arc_padding,
            start=90,
            extent=0,  # Se actualiza dinamicamente
            outline="#E74C3C",
            width=3,
            style="arc"
        )

        # Circulo principal
        padding = 4
        self.circle = self.canvas.create_oval(
            padding, padding,
            self.size - padding, self.size - padding,
            fill=self.COLORS[State.IDLE],
            outline="#222222",
            width=1
        )

    def _show_tooltip(self, event=None):
        """Muestra tooltip con info del estado actual"""
        if self._tooltip_window:
            return

        state_text = {
            State.IDLE: "Listo",
            State.DICTATING: "Dictando...",
            State.PROCESSING: "Procesando..."
        }

        self._tooltip_window = ctk.CTkToplevel(self.root)
        self._tooltip_window.overrideredirect(True)
        self._tooltip_window.attributes('-topmost', True)

        frame = ctk.CTkFrame(self._tooltip_window, fg_color="#1a1a1a", corner_radius=6)
        frame.pack(padx=1, pady=1)

        label = ctk.CTkLabel(
            frame,
            text=f"{state_text.get(self._state, 'VoiceFlow')}\nClick derecho: menu",
            font=("Segoe UI", 9),
            text_color="#cccccc"
        )
        label.pack(padx=8, pady=4)

        # Posicionar a la derecha del overlay
        x = self.root.winfo_x() + self.size + 5
        y = self.root.winfo_y()
        self._tooltip_window.geometry(f"+{x}+{y}")

    def _hide_tooltip(self, event=None):
        """Oculta el tooltip"""
        if self._tooltip_window:
            self._tooltip_window.destroy()
            self._tooltip_window = None

    def _start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        # Ocultar tooltip al empezar a arrastrar
        self._hide_tooltip()

    def _on_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_data["x"]
        y = self.root.winfo_y() + event.y - self._drag_data["y"]
        self.root.geometry(f"+{x}+{y}")

    def _show_menu(self, event):
        # Crear menu contextual moderno
        menu_window = ctk.CTkToplevel(self.root)
        menu_window.overrideredirect(True)
        menu_window.attributes('-topmost', True)
        menu_window.configure(fg_color="#1a1a1a")

        # Frame contenedor con bordes redondeados
        frame = ctk.CTkFrame(menu_window, fg_color="#1a1a1a", corner_radius=10)
        frame.pack(padx=2, pady=2)

        # Estado actual
        state_text = {
            State.IDLE: "Idle",
            State.DICTATING: "Dictando",
            State.PROCESSING: "Procesando"
        }
        state_colors = {
            State.IDLE: "#27AE60",
            State.DICTATING: "#E74C3C",
            State.PROCESSING: "#F5A623"
        }

        state_label = ctk.CTkLabel(
            frame,
            text=f"● {state_text.get(self._state, 'Estado')}",
            font=("Segoe UI", 11, "bold"),
            text_color=state_colors.get(self._state, "#666666")
        )
        state_label.pack(pady=(8, 4), padx=12, anchor="w")

        # Separador
        sep = ctk.CTkFrame(frame, height=1, fg_color="#333333")
        sep.pack(fill="x", padx=8, pady=4)

        # Opciones
        options = [
            ("Transparencia", self._show_opacity_menu),
            ("Tamaño", self._show_size_menu),
        ]

        for text, command in options:
            btn = ctk.CTkButton(
                frame,
                text=text,
                font=("Segoe UI", 10),
                fg_color="transparent",
                hover_color="#333333",
                anchor="w",
                height=28,
                command=lambda c=command, m=menu_window: (m.destroy(), c())
            )
            btn.pack(fill="x", padx=4, pady=1)

        # Separador
        sep2 = ctk.CTkFrame(frame, height=1, fg_color="#333333")
        sep2.pack(fill="x", padx=8, pady=4)

        # Guardar posicion
        save_btn = ctk.CTkButton(
            frame,
            text="📍 Guardar posición",
            font=("Segoe UI", 10),
            fg_color="transparent",
            hover_color="#333333",
            anchor="w",
            height=28,
            command=lambda: (menu_window.destroy(), self._save_position())
        )
        save_btn.pack(fill="x", padx=4, pady=1)

        # Salir
        exit_btn = ctk.CTkButton(
            frame,
            text="❌ Salir",
            font=("Segoe UI", 10),
            fg_color="transparent",
            hover_color="#4a2020",
            text_color="#E74C3C",
            anchor="w",
            height=28,
            command=lambda: (menu_window.destroy(), self.quit())
        )
        exit_btn.pack(fill="x", padx=4, pady=(1, 8))

        # Posicionar menu
        menu_window.geometry(f"+{event.x_root}+{event.y_root}")

        # Cerrar al perder foco
        menu_window.bind('<FocusOut>', lambda e: menu_window.destroy())
        menu_window.focus_set()

    def _show_opacity_menu(self):
        """Muestra submenu de transparencia"""
        menu = ctk.CTkToplevel(self.root)
        menu.overrideredirect(True)
        menu.attributes('-topmost', True)

        frame = ctk.CTkFrame(menu, fg_color="#1a1a1a", corner_radius=8)
        frame.pack(padx=2, pady=2)

        ctk.CTkLabel(frame, text="Transparencia", font=("Segoe UI", 10, "bold")).pack(pady=(8, 4))

        for opacity in [0.5, 0.7, 0.9, 1.0]:
            btn = ctk.CTkButton(
                frame,
                text=f"{int(opacity*100)}%",
                font=("Segoe UI", 10),
                fg_color="transparent",
                hover_color="#333333",
                height=28,
                width=80,
                command=lambda o=opacity: (self._set_opacity(o), menu.destroy())
            )
            btn.pack(pady=1, padx=4)

        frame.pack_propagate(False)
        menu.geometry(f"+{self.root.winfo_x() + self.size + 5}+{self.root.winfo_y()}")
        menu.bind('<FocusOut>', lambda e: menu.destroy())
        menu.focus_set()

    def _show_size_menu(self):
        """Muestra submenu de tamaño"""
        menu = ctk.CTkToplevel(self.root)
        menu.overrideredirect(True)
        menu.attributes('-topmost', True)

        frame = ctk.CTkFrame(menu, fg_color="#1a1a1a", corner_radius=8)
        frame.pack(padx=2, pady=2)

        ctk.CTkLabel(frame, text="Tamaño", font=("Segoe UI", 10, "bold")).pack(pady=(8, 4))

        for size in [30, 40, 50, 60]:
            btn = ctk.CTkButton(
                frame,
                text=f"{size}px",
                font=("Segoe UI", 10),
                fg_color="transparent",
                hover_color="#333333",
                height=28,
                width=80,
                command=lambda s=size: (self._resize(s), menu.destroy())
            )
            btn.pack(pady=1, padx=4)

        menu.geometry(f"+{self.root.winfo_x() + self.size + 5}+{self.root.winfo_y()}")
        menu.bind('<FocusOut>', lambda e: menu.destroy())
        menu.focus_set()

    def _resize(self, new_size: int):
        """Cambia el tamaño del overlay"""
        self.size = new_size
        self.root.geometry(f"{new_size}x{new_size}")
        self.canvas.configure(width=new_size, height=new_size)

        # Actualizar circulos
        padding = 2
        self.canvas.coords(self.glow, padding, padding, new_size - padding, new_size - padding)
        # Actualizar arco de mic
        arc_padding = 1
        self.canvas.coords(self.mic_arc, arc_padding, arc_padding, new_size - arc_padding, new_size - arc_padding)
        padding = 4
        self.canvas.coords(self.circle, padding, padding, new_size - padding, new_size - padding)

    def _set_opacity(self, opacity: float):
        """Cambia la opacidad del overlay"""
        self._opacity = opacity
        self.root.attributes('-alpha', opacity)

    def _save_position(self):
        """Guarda la posicion, tamaño y opacidad en config.json"""
        pos = self.get_position()
        config = load_config()
        config["overlay"]["position"] = list(pos)
        config["overlay"]["size"] = self.size
        config["overlay"]["opacity"] = self._opacity
        save_config(config)
        print(f"[UI] Configuración guardada: pos={pos}, size={self.size}, opacity={self._opacity}")

    def set_hint_callbacks(self, on_listo, on_cancela):
        """Configura callbacks para los botones de hints"""
        self._on_listo_callback = on_listo
        self._on_cancela_callback = on_cancela

    def _on_hint_listo(self):
        """Handler para boton listo en hints"""
        if self._on_listo_callback:
            self._on_listo_callback()

    def _on_hint_cancela(self):
        """Handler para boton cancela en hints"""
        if self._on_cancela_callback:
            self._on_cancela_callback()

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

    def flash_unknown(self):
        """Flash amarillo para comando no reconocido"""
        self.flash(self.UNKNOWN_COLOR, 150)

    def _end_flash(self):
        """Termina el flash y permite que la animacion retome el control"""
        self._flash_active = False

    def _process_queue(self):
        """Procesa comandos de UI en el thread principal"""
        try:
            while True:
                cmd = self._ui_queue.get_nowait()
                if cmd[0] == "state":
                    state = cmd[1]
                    old_state = self._state
                    if state != old_state:
                        # Iniciar transicion de estado
                        self._prev_state = old_state
                        self._state = state
                        self._transition_progress = 0.0
                    # Mostrar/ocultar hints segun estado
                    if state == State.DICTATING and old_state != State.DICTATING:
                        self.show_hints()
                    elif state != State.DICTATING and old_state == State.DICTATING:
                        self.hide_hints()
                elif cmd[0] == "flash":
                    color, duration_ms = cmd[1], cmd[2]
                    self._flash_active = True
                    self.canvas.itemconfig(self.circle, fill=color)
                    self.root.after(duration_ms, self._end_flash)
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

    def _get_state_base_color(self, state: State) -> str:
        """Obtiene el color base para un estado"""
        if state == State.IDLE:
            return self.IDLE_COLOR_DARK
        elif state == State.DICTATING:
            return self.RECORDING_COLOR_DARK
        elif state == State.PROCESSING:
            return "#D4A500"
        return self.IDLE_COLOR_DARK

    def _animate(self):
        """Animacion continua del overlay"""
        self._animation_phase += 0.05

        # Avanzar transicion de estado
        if self._transition_progress < 1.0:
            self._transition_progress = min(1.0, self._transition_progress + 0.1)

        # No animar si hay un flash activo
        if self._flash_active:
            self.root.after(50, self._animate)
            return

        # Calcular color objetivo segun estado actual
        if self._state == State.IDLE:
            # Pulso suave y calmado
            factor = (math.sin(self._animation_phase * 0.5) + 1) / 2
            target_color = self._interpolate_color(self.IDLE_COLOR_DARK, self.IDLE_COLOR_LIGHT, factor)
            target_glow = self._interpolate_color("#222222", "#444444", factor)
            # Ocultar arco de mic en IDLE
            self.canvas.itemconfig(self.mic_arc, extent=0)

        elif self._state == State.DICTATING:
            # Efecto de grabacion: pulso mas rapido + respuesta a mic
            base_factor = (math.sin(self._animation_phase * 2) + 1) / 2
            combined_factor = min(1.0, base_factor * 0.5 + self._mic_level * 0.5)
            target_color = self._interpolate_color(self.RECORDING_COLOR_DARK, self.RECORDING_COLOR_LIGHT, combined_factor)
            target_glow = self._interpolate_color("#331111", "#662222", combined_factor)
            # Actualizar arco indicador de nivel de mic (360 grados = nivel maximo)
            arc_extent = -self._mic_level * 360  # Negativo para sentido horario
            arc_color = self._interpolate_color("#E74C3C", "#FF6B6B", self._mic_level)
            self.canvas.itemconfig(self.mic_arc, extent=arc_extent, outline=arc_color)

        elif self._state == State.PROCESSING:
            # Pulso amarillo
            factor = (math.sin(self._animation_phase * 3) + 1) / 2
            target_color = self._interpolate_color("#D4A500", "#FFD700", factor)
            target_glow = "#333333"

        else:
            target_color = self.IDLE_COLOR_DARK
            target_glow = "#333333"

        # Aplicar transicion suave si esta en progreso
        if self._transition_progress < 1.0:
            prev_base = self._get_state_base_color(self._prev_state)
            target_color = self._interpolate_color(prev_base, target_color, self._transition_progress)

        self.canvas.itemconfig(self.circle, fill=target_color)
        self.canvas.itemconfig(self.glow, fill=target_glow)

        # Continuar animacion cada 50ms
        self.root.after(50, self._animate)

    def set_mic_level(self, level: float):
        """Thread-safe: actualiza nivel de microfono (0.0 - 1.0)"""
        self._ui_queue.put(("mic_level", min(1.0, max(0.0, level))))

    def show_hints(self):
        """Muestra popup moderno con hints de 'listo' y 'cancela'"""
        if self._hint_window:
            return

        self._hint_window = ctk.CTkToplevel(self.root)
        self._hint_window.overrideredirect(True)
        self._hint_window.attributes('-topmost', True)
        self._hint_window.attributes('-alpha', 0.95)

        # Posicionar debajo del overlay
        x = self.root.winfo_x()
        y = self.root.winfo_y() + self.size + 8

        frame = ctk.CTkFrame(self._hint_window, fg_color="#1a1a1a", corner_radius=12)
        frame.pack(padx=2, pady=2)

        # Titulo
        title = ctk.CTkLabel(
            frame,
            text="🎤 Dictando...",
            font=("Segoe UI", 11, "bold"),
            text_color="#E74C3C"
        )
        title.pack(pady=(10, 8), padx=12)

        # Botones de hint
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=(0, 10), padx=12)

        listo_btn = ctk.CTkButton(
            btn_frame,
            text="✓ listo",
            font=("Segoe UI", 10, "bold"),
            fg_color="#27AE60",
            hover_color="#2ECC71",
            corner_radius=6,
            height=28,
            width=70,
            command=self._on_hint_listo
        )
        listo_btn.pack(side="left", padx=2)

        cancela_btn = ctk.CTkButton(
            btn_frame,
            text="✗ cancela",
            font=("Segoe UI", 10, "bold"),
            fg_color="#E74C3C",
            hover_color="#C0392B",
            command=self._on_hint_cancela,
            corner_radius=6,
            height=28,
            width=70
        )
        cancela_btn.pack(side="left", padx=2)

        self._hint_window.geometry(f"+{x}+{y}")

    def hide_hints(self):
        """Oculta popup de hints"""
        if self._hint_window:
            self._hint_window.destroy()
            self._hint_window = None
