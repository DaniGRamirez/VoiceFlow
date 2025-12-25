"""
Hot reload watcher for custom voice commands.

Monitors config/commands/ directory for JSON file changes and
automatically reloads commands without restarting the application.
"""

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.commands import CommandRegistry
    from ui.overlay import Overlay
    from core.sounds import SoundPlayer


@dataclass
class ReloadResult:
    """Result of a command reload operation."""
    success: bool
    commands_loaded: int
    commands_removed: int
    errors: list[str] = field(default_factory=list)
    files_processed: list[str] = field(default_factory=list)


class CommandWatcher:
    """
    File watcher for custom command JSON files.

    Uses watchdog library to monitor config/commands/ directory.
    Debounces rapid changes (e.g., editor save + backup file).
    Provides atomic reload with rollback on error.
    """

    def __init__(
        self,
        commands_dir: str,
        registry: "CommandRegistry",
        loader_factory: Callable,
        config: dict,
        sounds: Optional["SoundPlayer"] = None,
        overlay: Optional["Overlay"] = None,
        debounce_seconds: float = 0.5
    ):
        """
        Initialize the command watcher.

        Args:
            commands_dir: Path to config/commands/ directory
            registry: CommandRegistry instance
            loader_factory: Function that creates a CustomCommandLoader
            config: Application configuration dict
            sounds: Optional SoundPlayer for feedback
            overlay: Optional Overlay for visual feedback
            debounce_seconds: Wait time after last change before reloading
        """
        self._commands_dir = os.path.abspath(commands_dir)
        self._registry = registry
        self._loader_factory = loader_factory
        self._config = config
        self._sounds = sounds
        self._overlay = overlay
        self._debounce_seconds = debounce_seconds

        self._observer = None
        self._debounce_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._running = False

        # Hot reload config
        hr_config = config.get("custom_commands", {}).get("hot_reload", {})
        self._notify_on_reload = hr_config.get("notify_on_reload", True)
        self._sound_on_success = hr_config.get("sound_on_success", "ding")
        self._sound_on_error = hr_config.get("sound_on_error", "error")

    def start(self) -> bool:
        """
        Start watching for file changes in a background thread.

        Returns:
            True if started successfully, False if watchdog not available
        """
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileSystemEvent
        except ImportError:
            print("[CommandWatcher] watchdog not installed, hot reload disabled")
            return False

        if self._running:
            return True

        # Create event handler
        watcher = self

        class JsonFileHandler(FileSystemEventHandler):
            def on_any_event(self, event: FileSystemEvent):
                # Only react to JSON files
                if event.is_directory:
                    return
                path = event.src_path
                if not path.endswith(".json"):
                    return
                # Ignore underscore-prefixed files
                basename = os.path.basename(path)
                if basename.startswith("_"):
                    return
                watcher._on_file_change(event)

        self._observer = Observer()
        self._observer.schedule(JsonFileHandler(), self._commands_dir, recursive=False)
        self._observer.start()
        self._running = True

        print(f"[CommandWatcher] Monitoring {self._commands_dir} for changes")
        return True

    def stop(self) -> None:
        """Stop the file watcher."""
        if self._observer and self._running:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None
            self._running = False
            print("[CommandWatcher] Stopped")

        # Cancel any pending debounce timer
        with self._lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
                self._debounce_timer = None

    def reload(self) -> ReloadResult:
        """
        Manually trigger a reload of all custom commands.

        Thread-safe. Can be called from any thread.

        Returns:
            ReloadResult with success status, counts, and any errors
        """
        print("[CommandWatcher] Reloading custom commands...")

        # Create a fresh loader
        loader = self._loader_factory()

        # Load and validate all commands without registering
        commands, errors, files = loader.load_all_validated()

        if not commands and errors:
            # All files failed - keep existing commands
            result = ReloadResult(
                success=False,
                commands_loaded=0,
                commands_removed=0,
                errors=errors,
                files_processed=files
            )
            self._notify_result(result)
            return result

        # Atomic swap: unregister old, register new
        removed = self._registry.unregister_by_source("custom")
        loaded = self._registry.register_batch(commands, "custom")

        result = ReloadResult(
            success=True,
            commands_loaded=loaded,
            commands_removed=removed,
            errors=errors,  # Partial errors (some files failed)
            files_processed=files
        )

        self._notify_result(result)
        return result

    def _on_file_change(self, event) -> None:
        """Handler called by watchdog on file system events."""
        with self._lock:
            # Cancel existing timer
            if self._debounce_timer:
                self._debounce_timer.cancel()

            # Start new debounce timer
            self._debounce_timer = threading.Timer(
                self._debounce_seconds,
                self._debounced_reload
            )
            self._debounce_timer.start()

    def _debounced_reload(self) -> None:
        """Called after debounce period expires."""
        with self._lock:
            self._debounce_timer = None

        self.reload()

    def _notify_result(self, result: ReloadResult) -> None:
        """Provide audio/visual feedback on reload result."""
        if not self._notify_on_reload:
            return

        if result.success:
            msg = f"Recargados {result.commands_loaded} comandos"
            if result.errors:
                msg += f" ({len(result.errors)} errores)"
            print(f"[CommandWatcher] {msg}")

            if self._sounds and self._sound_on_success:
                try:
                    self._sounds.play(self._sound_on_success)
                except Exception:
                    pass

            if self._overlay:
                try:
                    self._overlay.show_text(msg, is_command=True)
                except Exception:
                    pass
        else:
            msg = f"Error recargando: {result.errors[0] if result.errors else 'unknown'}"
            print(f"[CommandWatcher] {msg}")

            if self._sounds and self._sound_on_error:
                try:
                    self._sounds.play(self._sound_on_error)
                except Exception:
                    pass

            if self._overlay:
                try:
                    self._overlay.show_text(msg, is_command=False)
                except Exception:
                    pass

    @property
    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._running
