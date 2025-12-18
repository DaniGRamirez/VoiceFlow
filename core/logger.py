"""
Sistema de logging para VoiceFlow.

Guarda estadísticas de uso:
- Comandos ejecutados (con timestamp)
- Textos reconocidos que NO fueron comandos (útil para mejorar aliases)
- Sesiones de uso

El logger guarda automáticamente cada cierto intervalo para evitar
pérdida de datos si la aplicación se cierra abruptamente.
"""

import json
import os
import threading
from datetime import datetime
from typing import Optional
from config.settings import BASE_DIR


LOG_FILE = os.path.join(BASE_DIR, "logs", "usage.json")
AUTO_SAVE_INTERVAL = 60  # Guardar cada 60 segundos


ATTEMPT_WINDOW_SECONDS = 5  # Ventana para detectar intentos fallidos antes de éxito


class UsageLogger:
    def __init__(self, auto_save_interval: int = AUTO_SAVE_INTERVAL):
        self._session_start = datetime.now()
        self._commands_executed = []  # [(timestamp, command, recognized_text)]
        self._ignored_texts = []  # [(timestamp, text)] - palabras no reconocidas
        self._recent_ignored = []  # Buffer temporal de ignorados recientes (para detectar intentos)
        self._last_saved_commands = 0  # Para saber si hay cambios
        self._last_saved_ignored = 0
        self._auto_save_interval = auto_save_interval
        self._auto_save_timer = None
        self._get_model_name = None  # Callback para obtener nombre del modelo actual
        self._ensure_log_dir()
        self._start_auto_save()

    def set_model_callback(self, callback):
        """Configura callback para obtener el nombre del modelo actual."""
        self._get_model_name = callback

    def _ensure_log_dir(self):
        """Crea el directorio de logs si no existe."""
        log_dir = os.path.dirname(LOG_FILE)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def _start_auto_save(self):
        """Inicia el timer de auto-guardado."""
        self._auto_save_timer = threading.Timer(
            self._auto_save_interval,
            self._auto_save_tick
        )
        self._auto_save_timer.daemon = True
        self._auto_save_timer.start()

    def _auto_save_tick(self):
        """Ejecuta el auto-guardado si hay cambios."""
        has_changes = (
            len(self._commands_executed) > self._last_saved_commands or
            len(self._ignored_texts) > self._last_saved_ignored
        )

        if has_changes:
            self._save_incremental()

        # Reiniciar timer
        self._start_auto_save()

    def _save_incremental(self):
        """Guarda los datos actuales sin marcar como sesión finalizada."""
        data = self._load_existing()

        # Buscar si ya existe una sesión activa (misma fecha de inicio)
        session_id = self._session_start.isoformat()
        existing_session = None
        for i, session in enumerate(data["sessions"]):
            if session.get("start") == session_id:
                existing_session = i
                break

        # Crear/actualizar entrada de sesión
        session = {
            "start": session_id,
            "end": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - self._session_start).total_seconds(),
            "commands": self._commands_executed,
            "ignored": self._ignored_texts,
            "active": True  # Marca que la sesión aún está activa
        }

        if existing_session is not None:
            data["sessions"][existing_session] = session
        else:
            data["sessions"].append(session)

        # Actualizar estadísticas
        self._update_stats(data)

        # Guardar
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._last_saved_commands = len(self._commands_executed)
            self._last_saved_ignored = len(self._ignored_texts)
            # Auto-guardado silencioso (solo un punto para indicar actividad)
        except Exception as e:
            print(f"[Log] Error en auto-guardado: {e}")

    def stop_auto_save(self):
        """Detiene el timer de auto-guardado."""
        if self._auto_save_timer:
            self._auto_save_timer.cancel()
            self._auto_save_timer = None

    def log_command(self, command: str, recognized_text: str):
        """Registra un comando ejecutado."""
        now = datetime.now()

        # Buscar intentos fallidos recientes (dentro de la ventana de tiempo)
        attempts = []
        remaining_ignored = []

        for item in self._recent_ignored:
            item_time = datetime.fromisoformat(item["time"])
            elapsed = (now - item_time).total_seconds()

            if elapsed <= ATTEMPT_WINDOW_SECONDS:
                # Este ignorado fue un intento fallido de este comando
                attempts.append(item["text"])
            else:
                # Muy antiguo, ya no cuenta como intento
                remaining_ignored.append(item)

        self._recent_ignored = []  # Limpiar buffer

        # Si hubo intentos fallidos, marcarlos en el comando
        cmd_entry = {
            "time": now.isoformat(),
            "command": command,
            "recognized": recognized_text
        }

        # Añadir modelo si está disponible
        if self._get_model_name:
            try:
                model = self._get_model_name()
                if model:
                    # Solo guardar nombre corto (sin ruta completa)
                    short = model.replace("vosk-model-", "").replace("-es-0.42", "")
                    # "small" queda como "small", "" (large) queda como "large"
                    cmd_entry["model"] = short if short else "large"
            except Exception:
                pass

        if attempts:
            cmd_entry["attempts"] = attempts
            print(f"   [Log] Intentos previos: {attempts}")

        self._commands_executed.append(cmd_entry)

    def log_ignored(self, text: str):
        """Registra texto reconocido pero ignorado (no es comando)."""
        now = datetime.now()
        entry = {
            "time": now.isoformat(),
            "text": text
        }

        # Añadir al buffer de recientes (para detectar intentos)
        self._recent_ignored.append(entry)

        # Limpiar intentos muy antiguos del buffer (más de 10 segundos)
        cutoff = now.timestamp() - 10
        self._recent_ignored = [
            item for item in self._recent_ignored
            if datetime.fromisoformat(item["time"]).timestamp() > cutoff
        ]

        # Añadir a la lista general de ignorados
        self._ignored_texts.append(entry)

    def save(self):
        """Guarda el log de la sesión al archivo (llamado al cerrar)."""
        # Detener auto-guardado
        self.stop_auto_save()

        # Cargar log existente
        data = self._load_existing()

        # Buscar si ya existe una sesión activa (del auto-guardado)
        session_id = self._session_start.isoformat()
        existing_session = None
        for i, session in enumerate(data["sessions"]):
            if session.get("start") == session_id:
                existing_session = i
                break

        # Crear entrada de sesión final (sin marca de active)
        session = {
            "start": session_id,
            "end": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - self._session_start).total_seconds(),
            "commands": self._commands_executed,
            "ignored": self._ignored_texts
        }

        # Actualizar o añadir sesión
        if existing_session is not None:
            data["sessions"][existing_session] = session
        else:
            data["sessions"].append(session)

        # Actualizar estadísticas globales
        self._update_stats(data)

        # Guardar
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n[LOG] ✓ Sesión guardada correctamente")
            print(f"[LOG]   Archivo: {LOG_FILE}")
            print(f"[LOG]   Comandos: {len(self._commands_executed)}, Ignorados: {len(self._ignored_texts)}")
        except Exception as e:
            print(f"\n[LOG] ✗ ERROR guardando sesión: {e}")

    def _load_existing(self) -> dict:
        """Carga el log existente o crea uno nuevo."""
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Estructura inicial
        return {
            "sessions": [],
            "stats": {
                "total_sessions": 0,
                "total_commands": 0,
                "total_ignored": 0,
                "command_frequency": {},  # comando -> count
                "ignored_frequency": {}   # texto -> count (para detectar aliases potenciales)
            }
        }

    def _update_stats(self, data: dict):
        """Actualiza las estadísticas globales."""
        stats = data["stats"]
        stats["total_sessions"] = len(data["sessions"])

        # Contar comandos
        total_cmds = 0
        cmd_freq = {}
        for session in data["sessions"]:
            for cmd in session.get("commands", []):
                total_cmds += 1
                name = cmd["command"]
                cmd_freq[name] = cmd_freq.get(name, 0) + 1

        stats["total_commands"] = total_cmds
        # Ordenar por frecuencia
        stats["command_frequency"] = dict(
            sorted(cmd_freq.items(), key=lambda x: x[1], reverse=True)
        )

        # Contar ignorados
        total_ignored = 0
        ignored_freq = {}
        for session in data["sessions"]:
            for item in session.get("ignored", []):
                total_ignored += 1
                text = item["text"]
                ignored_freq[text] = ignored_freq.get(text, 0) + 1

        stats["total_ignored"] = total_ignored
        # Ordenar por frecuencia (top 50 para no crecer infinito)
        stats["ignored_frequency"] = dict(
            sorted(ignored_freq.items(), key=lambda x: x[1], reverse=True)[:50]
        )

    def get_session_summary(self) -> str:
        """Retorna un resumen de la sesión actual."""
        duration = (datetime.now() - self._session_start).total_seconds()
        mins = int(duration // 60)
        secs = int(duration % 60)

        # Contar comandos más usados esta sesión
        cmd_counts = {}
        total_attempts = 0
        for cmd in self._commands_executed:
            name = cmd["command"]
            cmd_counts[name] = cmd_counts.get(name, 0) + 1
            if "attempts" in cmd:
                total_attempts += len(cmd["attempts"])

        top_cmds = sorted(cmd_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        summary = f"\n{'=' * 40}\n"
        summary += f"  Sesión: {mins}m {secs}s\n"
        summary += f"  Comandos: {len(self._commands_executed)}\n"
        summary += f"  Ignorados: {len(self._ignored_texts)}\n"

        if total_attempts > 0:
            summary += f"  Intentos fallidos: {total_attempts}\n"

        if top_cmds:
            summary += f"  Top comandos:\n"
            for cmd, count in top_cmds:
                summary += f"    {cmd}: {count}\n"

        summary += f"{'=' * 40}"
        return summary


# Instancia global
_logger: Optional[UsageLogger] = None


def get_logger() -> UsageLogger:
    """Obtiene o crea el logger global."""
    global _logger
    if _logger is None:
        _logger = UsageLogger()
    return _logger
