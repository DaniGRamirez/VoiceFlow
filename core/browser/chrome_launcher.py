"""
BrowserLauncher - Helper para lanzar navegadores Chromium con debugging.

Soporta Chrome, Edge y Chromium con --remote-debugging-port para CDP.
"""

import subprocess
import os
from typing import Optional, Tuple

# Rutas conocidas de navegadores en Windows
BROWSER_PATHS = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "chromium": [
        os.path.expandvars(r"%LOCALAPPDATA%\Chromium\Application\chrome.exe"),
    ],
}


def find_browser(preferred: str = "auto") -> Tuple[Optional[str], str]:
    """
    Busca un navegador Chromium instalado.

    Args:
        preferred: "chrome", "edge", "chromium", o "auto" (busca cualquiera)

    Returns:
        Tupla (ruta_ejecutable, nombre_navegador) o (None, "")
    """
    if preferred == "auto":
        # Orden de preferencia: Edge (preinstalado), Chrome, Chromium
        search_order = ["edge", "chrome", "chromium"]
    else:
        search_order = [preferred]

    for browser_name in search_order:
        paths = BROWSER_PATHS.get(browser_name, [])
        for path in paths:
            if os.path.exists(path):
                return path, browser_name

    return None, ""


def find_chrome() -> Optional[str]:
    """Legacy: Busca Chrome específicamente."""
    path, _ = find_browser("chrome")
    return path


def launch_browser_debug(
    port: int = 9222,
    browser: str = "auto",
    user_data_dir: Optional[str] = None
) -> bool:
    """
    Lanza un navegador Chromium con puerto de debugging habilitado.

    Args:
        port: Puerto para Chrome DevTools Protocol (default: 9222)
        browser: "chrome", "edge", "chromium", o "auto"
        user_data_dir: Directorio de perfil (default: temporal)

    Returns:
        True si el navegador se lanzó exitosamente
    """
    browser_path, browser_name = find_browser(browser)

    if not browser_path:
        print(f"[Browser] No se encontró navegador Chromium instalado")
        return False

    if user_data_dir is None:
        user_data_dir = os.path.join(
            os.environ.get("TEMP", "C:/temp"),
            f"{browser_name}-debug"
        )

    args = [
        browser_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
    ]

    try:
        subprocess.Popen(args)
        print(f"[Browser] {browser_name.capitalize()} iniciado con puerto {port}")
        print(f"[Browser] Perfil: {user_data_dir}")
        return True
    except Exception as e:
        print(f"[Browser] Error lanzando {browser_name}: {e}")
        return False


def launch_chrome_debug(port: int = 9222, user_data_dir: Optional[str] = None) -> bool:
    """Legacy: Lanza Chrome específicamente."""
    return launch_browser_debug(port, "chrome", user_data_dir)


def is_chrome_debug_running(port: int = 9222) -> bool:
    """
    Verifica si Chrome está escuchando en el puerto de debugging.

    Args:
        port: Puerto a verificar

    Returns:
        True si Chrome está disponible
    """
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result == 0
    except Exception:
        return False


if __name__ == "__main__":
    # Uso directo: python chrome_launcher.py [browser]
    import sys
    browser = sys.argv[1] if len(sys.argv) > 1 else "auto"

    if is_chrome_debug_running():
        print("[Browser] Ya hay un navegador corriendo con debugging en puerto 9222")
    else:
        launch_browser_debug(browser=browser)
