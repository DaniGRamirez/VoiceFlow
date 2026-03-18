"""PID file management for single-instance daemon."""
import os
from pathlib import Path

from voiceflow.config import VF_HOME


PID_FILE = VF_HOME / "daemon.pid"


def is_daemon_running() -> bool:
    """Check if a daemon is already running."""
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # Signal 0 = check if process exists
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        PID_FILE.unlink(missing_ok=True)
        return False


def write_pid() -> None:
    """Write current process PID to file."""
    VF_HOME.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def read_pid() -> int | None:
    """Read PID from file."""
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except ValueError:
        return None


def remove_pid() -> None:
    """Remove PID file."""
    PID_FILE.unlink(missing_ok=True)
