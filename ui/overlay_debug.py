"""
VoiceFlow Overlay - Debug Components

Debug functionality for testing overlay animations:
- Keyboard shortcuts (keys 1-9, 0) for testing state transitions
- Context menu with debug options
- Silent input mode for keyboard command entry
"""

from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import QWidget, QMenu, QVBoxLayout, QLabel, QLineEdit
from PyQt6.QtCore import Qt, QTimer, QEvent

from core.state import State
from config.settings import save_config, load_config

if TYPE_CHECKING:
    from ui.overlay import Overlay


class OverlayDebugMixin:
    """
    Mixin class providing debug functionality for the Overlay.

    This class is designed to be mixed into the main Overlay class,
    providing keyboard shortcuts, context menu, and silent input mode.
    """

    # ========== TECLAS DE PRUEBA (DEBUG) ==========

    def keyPressEvent(self: 'Overlay', event):
        """Teclas para probar animaciones manualmente."""
        from PyQt6.QtCore import Qt as QtCore

        key = event.key()

        # 1 = Activar listening mode (sacudida + pulso)
        if key == QtCore.Key.Key_1:
            print("[DEBUG] Tecla 1: Activando listening mode")
            self._on_listening_change(True)

        # 2 = Desactivar listening mode
        elif key == QtCore.Key.Key_2:
            print("[DEBUG] Tecla 2: Desactivando listening mode")
            self._on_listening_change(False)

        # 3 = Transicion IDLE -> DICTATING
        elif key == QtCore.Key.Key_3:
            print("[DEBUG] Tecla 3: Transicion IDLE -> DICTATING")
            self._on_state_change(State.DICTATING)

        # 4 = Transicion DICTATING -> IDLE
        elif key == QtCore.Key.Key_4:
            print("[DEBUG] Tecla 4: Transicion DICTATING -> IDLE")
            self._on_state_change(State.IDLE)

        # 5 = Solo sacudida (sin listening)
        elif key == QtCore.Key.Key_5:
            print("[DEBUG] Tecla 5: Sacudida")
            self._shake_time = self.WAKE_SHAKE_DURATION
            self._shake_intensity = 1.0

        # 6 = Simular mic alto
        elif key == QtCore.Key.Key_6:
            print("[DEBUG] Tecla 6: Mic alto (0.8)")
            self._mic_level = 0.8

        # 7 = Simular mic silencio
        elif key == QtCore.Key.Key_7:
            print("[DEBUG] Tecla 7: Mic silencio (0.0)")
            self._mic_level = 0.0

        # 8 = Transicion DICTATING -> PAUSED
        elif key == QtCore.Key.Key_8:
            print("[DEBUG] Tecla 8: Transicion DICTATING -> PAUSED")
            self._on_state_change(State.PAUSED)

        # 9 = Transicion PAUSED -> DICTATING
        elif key == QtCore.Key.Key_9:
            print("[DEBUG] Tecla 9: Transicion PAUSED -> DICTATING")
            self._on_state_change(State.DICTATING)

        # 0 = Reset a estado inicial
        elif key == QtCore.Key.Key_0:
            print("[DEBUG] Tecla 0: Reset a IDLE")
            self._state = State.IDLE
            self._visual_mode = "bars"
            self._transition = None
            self._bars_deploy = 1.0
            self._circle_scale = 1.0
            self._circle_color_progress = 1.0
            self._listening_mode = False
            self._shake_time = 0.0
            self._mic_level = 0.0

        # ESPACIO = Modo silencioso (entrada de texto por teclado)
        elif key == QtCore.Key.Key_Space:
            self._show_silent_input()

    # ========== MODO SILENCIOSO ==========

    def set_silent_input_callback(self: 'Overlay', callback: Callable):
        """Configura el callback para procesar texto del modo silencioso."""
        self._on_silent_input_callback = callback

    def _show_silent_input(self: 'Overlay'):
        """Muestra ventana de entrada de texto para modo silencioso."""
        # Cerrar si ya existe
        if self._silent_input_window:
            self._silent_input_window.close()
            self._silent_input_window = None

        # Crear ventana
        self._silent_input_window = QWidget(None, Qt.WindowType.FramelessWindowHint |
                                            Qt.WindowType.WindowStaysOnTopHint |
                                            Qt.WindowType.Tool)
        self._silent_input_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self._silent_input_window)
        layout.setContentsMargins(0, 0, 0, 0)

        # Frame contenedor
        frame = QWidget()
        frame.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 20, 240);
                border-radius: 8px;
                border: 1px solid #E74C3C;
            }
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)
        frame_layout.setSpacing(6)

        # Label
        label = QLabel("Modo silencioso - Escribe comando:")
        label.setStyleSheet("""
            color: #888;
            font-family: 'Segoe UI';
            font-size: 9px;
            background: transparent;
            border: none;
        """)
        frame_layout.addWidget(label)

        # Campo de texto
        self._silent_input_field = QLineEdit()
        self._silent_input_field.setStyleSheet("""
            QLineEdit {
                background-color: rgba(40, 40, 40, 200);
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 10px;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #E74C3C;
            }
        """)
        self._silent_input_field.setPlaceholderText("ej: bloquear, captura, ayuda...")
        self._silent_input_field.returnPressed.connect(self._on_silent_input_submit)
        frame_layout.addWidget(self._silent_input_field)

        # Hint
        hint = QLabel("Enter = ejecutar | Esc = cancelar")
        hint.setStyleSheet("""
            color: #555;
            font-family: 'Segoe UI';
            font-size: 8px;
            background: transparent;
            border: none;
        """)
        frame_layout.addWidget(hint)

        layout.addWidget(frame)

        # Posicionar encima del overlay
        self._silent_input_window.adjustSize()
        input_width = self._silent_input_window.width()
        overlay_center_x = self.x() + self.width() / 2
        x = int(overlay_center_x - input_width / 2)
        y = self.y() - self._silent_input_window.height() - 10
        self._silent_input_window.move(x, y)

        # Instalar event filter para Escape
        self._silent_input_field.installEventFilter(self)

        # Mostrar y forzar foco
        self._silent_input_window.show()
        self._silent_input_window.raise_()
        self._silent_input_window.activateWindow()
        self._silent_input_field.setFocus()
        self._silent_input_field.activateWindow()
        print("[Silent] Modo silencioso activado - escribe un comando")

    def _on_silent_input_submit(self: 'Overlay'):
        """Procesa el texto introducido en modo silencioso."""
        if not self._silent_input_field:
            return

        text = self._silent_input_field.text().strip()

        # Guardar callback antes de cerrar la ventana
        callback = self._on_silent_input_callback

        # Ocultar primero pero usar deleteLater para evitar crash
        self._hide_silent_input()

        if text and callback:
            print(f"[Silent] Comando: '{text}'", flush=True)
            try:
                # Ejecutar callback despues de que Qt procese el cierre
                QTimer.singleShot(10, lambda: self._execute_silent_callback(callback, text))
            except Exception as e:
                print(f"[Silent ERROR] {type(e).__name__}: {e}", flush=True)
                import traceback
                traceback.print_exc()

    def _execute_silent_callback(self: 'Overlay', callback: Callable, text: str):
        """Ejecuta el callback del modo silencioso de forma segura."""
        try:
            print(f"[Silent] Ejecutando callback para: '{text}'", flush=True)
            callback(text)
            print(f"[Silent] Callback completado", flush=True)
        except Exception as e:
            print(f"[Silent CALLBACK ERROR] {type(e).__name__}: {e}", flush=True)
            import traceback
            traceback.print_exc()

    def _hide_silent_input(self: 'Overlay'):
        """Cierra la ventana de entrada silenciosa de forma segura."""
        if self._silent_input_window:
            # Usar deleteLater para evitar crash al cerrar durante callback
            window = self._silent_input_window
            self._silent_input_window = None
            self._silent_input_field = None
            window.hide()
            window.deleteLater()

    def eventFilter(self: 'Overlay', obj, event):
        """Filtro de eventos para capturar Escape en el campo de texto."""
        from PyQt6.QtCore import Qt as QtCore

        if event.type() == QEvent.Type.KeyPress:
            if event.key() == QtCore.Key.Key_Escape:
                print("[Silent] Cancelado")
                self._hide_silent_input()
                return True
        return super().eventFilter(obj, event)

    # ========== MENU CONTEXTUAL ==========

    def contextMenuEvent(self: 'Overlay', event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1a1a1a;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 8px;
            }
            QMenu::item {
                padding: 8px 24px;
                color: #888;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2a2a2a;
                color: #ccc;
            }
            QMenu::separator {
                height: 1px;
                background: #333;
                margin: 4px 8px;
            }
        """)

        # Estado actual
        state_names = {
            State.IDLE: "Esperando",
            State.DICTATING: "Absorbiendo",
            State.PROCESSING: "Pensando",
            State.PAUSED: "Pausado"
        }
        state_action = menu.addAction(f"* {state_names.get(self._state, 'Unknown')}")
        state_action.setEnabled(False)

        menu.addSeparator()

        # Submenu transparencia
        opacity_menu = menu.addMenu("Transparencia")
        for val in [0.5, 0.7, 0.9, 1.0]:
            action = opacity_menu.addAction(f"{int(val*100)}%")
            action.triggered.connect(lambda checked, v=val: self._set_opacity(v))

        # Submenu tamano
        size_menu = menu.addMenu("Tamano")
        for size in [30, 40, 50, 60]:
            action = size_menu.addAction(f"{size}px")
            action.triggered.connect(lambda checked, s=size: self._set_size(s))

        menu.addSeparator()

        # Submenu DEBUG para probar animaciones
        debug_menu = menu.addMenu("Debug Animaciones")

        listening_on = debug_menu.addAction("Listening Mode ON")
        listening_on.triggered.connect(lambda: self._debug_listening(True))

        listening_off = debug_menu.addAction("Listening Mode OFF")
        listening_off.triggered.connect(lambda: self._debug_listening(False))

        debug_menu.addSeparator()

        trans_dictating = debug_menu.addAction("IDLE -> DICTATING")
        trans_dictating.triggered.connect(self._debug_to_dictating)

        trans_idle = debug_menu.addAction("DICTATING -> IDLE")
        trans_idle.triggered.connect(self._debug_to_idle)

        debug_menu.addSeparator()

        shake_action = debug_menu.addAction("Sacudida")
        shake_action.triggered.connect(self._debug_shake)

        mic_high = debug_menu.addAction("Mic Alto")
        mic_high.triggered.connect(lambda: self._debug_mic(0.8))

        mic_low = debug_menu.addAction("Mic Silencio")
        mic_low.triggered.connect(lambda: self._debug_mic(0.0))

        debug_menu.addSeparator()

        reset_action = debug_menu.addAction("Reset")
        reset_action.triggered.connect(self._debug_reset)

        menu.addSeparator()

        # Toggle de auto-ayuda
        auto_help_text = "Auto-ayuda (ON)" if self._auto_help else "Auto-ayuda (OFF)"
        auto_help_action = menu.addAction(auto_help_text)
        auto_help_action.triggered.connect(self._toggle_auto_help)

        menu.addSeparator()

        # Guardar posicion
        save_action = menu.addAction("Guardar posicion")
        save_action.triggered.connect(self._save_position)

        # Salir
        quit_action = menu.addAction("Salir")
        quit_action.triggered.connect(self.quit)

        menu.exec(event.globalPos())

    # ========== DEBUG HELPERS ==========

    def _debug_listening(self: 'Overlay', on: bool):
        """Debug: activar/desactivar listening mode."""
        print(f"[DEBUG] Listening mode: {on}")
        self._on_listening_change(on)

    def _debug_to_dictating(self: 'Overlay'):
        """Debug: transicion a DICTATING."""
        print("[DEBUG] Transicion IDLE -> DICTATING")
        self._prev_state = State.IDLE
        self._state = State.DICTATING
        self._transition_time = 0.0
        self._transition_type = "collapse_then_expand"

    def _debug_to_idle(self: 'Overlay'):
        """Debug: transicion a IDLE."""
        print("[DEBUG] Transicion DICTATING -> IDLE")
        self._prev_state = State.DICTATING
        self._state = State.IDLE
        self._transition_time = 0.0
        self._transition_type = "collapse_then_expand"

    def _debug_shake(self: 'Overlay'):
        """Debug: solo sacudida."""
        print("[DEBUG] Sacudida")
        self._shake_time = self.WAKE_SHAKE_DURATION
        self._shake_intensity = 1.0

    def _debug_mic(self: 'Overlay', level: float):
        """Debug: simular nivel de mic."""
        print(f"[DEBUG] Mic: {level}")
        self._mic_level = level

    def _debug_reset(self: 'Overlay'):
        """Debug: reset a estado inicial."""
        print("[DEBUG] Reset a IDLE")
        self._state = State.IDLE
        self._transition_type = None
        self._bars_deploy = 1.0
        self._circle_color_progress = 1.0
        self._listening_mode = False
        self._shake_time = 0.0
        self._mic_level = 0.0

    def _set_opacity(self: 'Overlay', opacity: float):
        self._opacity = opacity
        self.setWindowOpacity(opacity)

    def _set_size(self: 'Overlay', size: int):
        self._base_size = size
        self._idle_size = size * 0.7
        if self._state == State.IDLE:
            self._current_size = float(self._idle_size)
            self._target_size = float(self._idle_size)

    def _save_position(self: 'Overlay'):
        """Guarda la posicion actual en config.json."""
        pos = (self.x(), self.y())
        config = load_config()
        config["overlay"]["position"] = list(pos)
        config["overlay"]["size"] = self._base_size
        config["overlay"]["opacity"] = self._opacity
        save_config(config)
        print(f"[UI] Configuracion guardada: pos={pos}, size={self._base_size}")

    def _toggle_auto_help(self: 'Overlay'):
        """Activa/desactiva la auto-ayuda y guarda en config."""
        self._auto_help = not self._auto_help
        config = load_config()
        config["overlay"]["auto_help"] = self._auto_help
        save_config(config)
        status = "activada" if self._auto_help else "desactivada"
        print(f"[UI] Auto-ayuda {status}")
