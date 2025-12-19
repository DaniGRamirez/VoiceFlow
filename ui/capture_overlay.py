"""
Capture Overlay - Campo de texto oculto para capturar dictado de Win+H.

Win+H de Windows necesita un campo de texto enfocado para escribir.
Este overlay crea una ventana temporal con un campo de texto que:
1. Aparece brevemente para capturar el foco
2. Win+H escribe en él
3. Extraemos el texto y cerramos
"""

import sys
import time
from typing import Optional, Callable
from PyQt6.QtWidgets import QApplication, QWidget, QTextEdit, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont


class CaptureOverlay(QWidget):
    """
    Ventana temporal para capturar dictado de Win+H.

    Flujo:
    1. show_and_capture() - muestra ventana, activa Win+H
    2. Win+H escribe en el campo de texto
    3. Después del timeout, extrae texto y cierra
    4. Llama callback con el texto capturado
    """

    # Signal para resultado thread-safe
    capture_done = pyqtSignal(str)
    # Signal para iniciar captura desde otro thread
    _start_capture_signal = pyqtSignal(float)
    # Signal emitido cuando el overlay está listo para recibir input
    ready_signal = pyqtSignal()

    def __init__(self, timeout: float = 5.0, overlay_position: tuple = None):
        """
        Args:
            timeout: Segundos para esperar dictado antes de cerrar
            overlay_position: Posición (x, y) del overlay principal para posicionar encima
        """
        # Usar QApplication existente si hay
        self._app = QApplication.instance()
        if self._app is None:
            self._app = QApplication(sys.argv)

        super().__init__()

        self._timeout = timeout
        self._callback: Optional[Callable[[str], None]] = None
        self._captured_text = ""
        self._overlay_position = overlay_position  # Posición del overlay principal

        self._setup_ui()

        # Conectar signal para captura thread-safe
        self._start_capture_signal.connect(self._do_capture)

    def _setup_ui(self):
        """Configura la UI compacta."""
        # Ventana sin bordes, siempre encima
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        # Fondo semi-transparente oscuro
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 20, 230);
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Campo de texto compacto donde Win+H escribirá
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("...")
        self._text_edit.setFont(QFont("Segoe UI", 10))
        self._text_edit.setStyleSheet("""
            QTextEdit {
                background-color: rgba(30, 30, 30, 200);
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px;
            }
            QTextEdit:focus {
                border-color: #E74C3C;
            }
        """)
        self._text_edit.setMinimumSize(180, 50)
        self._text_edit.setMaximumHeight(50)
        layout.addWidget(self._text_edit)

        # Tamaño compacto
        self.setFixedSize(200, 70)

    def set_overlay_position(self, position: tuple):
        """Actualiza la posición del overlay principal."""
        self._overlay_position = position

    def _position_above_overlay(self):
        """Posiciona la ventana justo encima del overlay principal."""
        if self._overlay_position:
            # Posicionar encima del overlay principal
            overlay_x, overlay_y = self._overlay_position
            x = overlay_x + 40 - self.width() // 2  # Centrado sobre el icono (40 es ~mitad del overlay)
            y = overlay_y - self.height() - 10  # 10px encima
            self.move(x, y)
        else:
            # Fallback: centrar en pantalla
            screen = self._app.primaryScreen().geometry()
            x = (screen.width() - self.width()) // 2
            y = (screen.height() - self.height()) // 2
            self.move(x, y)

    def capture(self, callback: Callable[[str], None], timeout: Optional[float] = None):
        """
        Muestra la ventana y espera dictado.
        Thread-safe: puede llamarse desde cualquier thread.

        Args:
            callback: Función a llamar con el texto capturado
            timeout: Segundos a esperar (None = usar default)
        """
        self._callback = callback
        # Emitir signal para ejecutar en thread Qt
        self._start_capture_signal.emit(timeout or self._timeout)

    def _do_capture(self, timeout: float):
        """Ejecuta la captura (debe llamarse desde thread Qt)."""
        print(f"[CaptureOverlay] === Iniciando captura ({timeout}s) ===")
        self._captured_text = ""
        self._text_edit.clear()
        self._timeout_ms = int(timeout * 1000)
        self._text_detected_time = None  # Momento en que se detectó texto
        self._last_text = ""  # Último texto detectado (para detectar cambios)
        self._start_time = time.time()  # Para logs de elapsed time

        # Posicionar encima del overlay antes de mostrar
        self._position_above_overlay()

        # Mostrar y tomar foco
        self.show()
        self.raise_()
        self.activateWindow()
        self._text_edit.setFocus()

        # Forzar procesamiento de eventos Qt para que el foco se aplique
        self._app.processEvents()

        print("[CaptureOverlay] Overlay visible, emitiendo ready_signal...")
        self.ready_signal.emit()

        # Iniciar polling para detectar texto temprano
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._check_for_text)
        self._poll_timer.start(200)  # Revisar cada 200ms

        # Timer de seguridad para cerrar después del timeout máximo
        QTimer.singleShot(self._timeout_ms, self._finish_capture)

    def _check_for_text(self):
        """Revisa si hay texto y lo valida inmediatamente."""
        current_text = self._text_edit.toPlainText().strip()
        elapsed = time.time() - self._start_time if hasattr(self, '_start_time') else 0

        if current_text:
            # Texto detectado - validar inmediatamente
            print(f"[CaptureOverlay] Texto detectado: '{current_text}' (a los {elapsed:.2f}s) - finalizando")
            self._poll_timer.stop()
            self._finish_capture()

    def _finish_capture(self):
        """Extrae el texto y cierra."""
        # Evitar llamadas múltiples
        if not self.isVisible():
            print("[CaptureOverlay] _finish_capture llamado pero overlay no visible (ya cerrado)")
            return

        # Detener polling
        if hasattr(self, '_poll_timer') and self._poll_timer.isActive():
            self._poll_timer.stop()

        elapsed = time.time() - self._start_time if hasattr(self, '_start_time') else 0
        self._captured_text = self._text_edit.toPlainText().strip()
        print(f"[CaptureOverlay] === Captura finalizada ({elapsed:.1f}s): '{self._captured_text}' ===")
        self.hide()

        if self._callback:
            self._callback(self._captured_text)

    def get_text(self) -> str:
        """Retorna el último texto capturado."""
        return self._captured_text


class CaptureManager:
    """
    Gestor singleton para captura de dictado.

    Uso desde cualquier thread:
        CaptureManager.capture(callback, timeout)
    """

    _instance: Optional['CaptureManager'] = None
    _overlay: Optional[CaptureOverlay] = None

    @classmethod
    def get_instance(cls) -> 'CaptureManager':
        if cls._instance is None:
            cls._instance = CaptureManager()
        return cls._instance

    @classmethod
    def capture(cls, callback: Callable[[str], None], timeout: float = 5.0):
        """
        Inicia captura de dictado.

        Args:
            callback: Función a llamar con texto capturado
            timeout: Segundos a esperar
        """
        instance = cls.get_instance()

        # Crear overlay si no existe
        if instance._overlay is None:
            instance._overlay = CaptureOverlay(timeout)

        instance._overlay.capture(callback, timeout)

    @classmethod
    def close(cls):
        """Cierra el overlay si existe."""
        if cls._overlay:
            cls._overlay.close()
            cls._overlay = None
