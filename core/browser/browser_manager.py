"""
BrowserManager - Singleton para conexión CDP a Chrome.

Permite conectarse a un Chrome existente via Chrome DevTools Protocol
y encontrar pestañas específicas por URL.
"""

from typing import Optional

try:
    from playwright.sync_api import sync_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = None
    Page = None


class BrowserManager:
    """
    Singleton que gestiona la conexión CDP a Chrome.

    Uso:
        manager = BrowserManager.get_instance()
        manager.connect(port=9222)
        page = manager.find_tab("claude.ai")
    """

    _instance: Optional['BrowserManager'] = None
    _browser: Optional[Browser] = None
    _playwright = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'BrowserManager':
        """Obtiene la instancia singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def connect(self, port: int = 9222) -> bool:
        """
        Conecta a Chrome via CDP.

        Args:
            port: Puerto de debugging de Chrome (default: 9222)

        Returns:
            True si la conexión fue exitosa
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("[Browser] Playwright no instalado. Ejecuta: pip install playwright && playwright install chromium")
            return False

        if self._browser:
            return True

        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(
                f"http://localhost:{port}"
            )
            print(f"[Browser] Conectado a Chrome en puerto {port}")
            return True
        except Exception as e:
            print(f"[Browser] Error conectando a Chrome: {e}")
            print(f"[Browser] Asegúrate de lanzar Chrome con: --remote-debugging-port={port}")
            return False

    def find_tab(self, url_contains: str) -> Optional[Page]:
        """
        Encuentra una pestaña por URL parcial.

        Args:
            url_contains: Substring a buscar en la URL

        Returns:
            Page si se encuentra, None si no
        """
        if not self._browser:
            print("[Browser] No conectado. Llama connect() primero.")
            return None

        for context in self._browser.contexts:
            for page in context.pages:
                if url_contains.lower() in page.url.lower():
                    print(f"[Browser] Encontrada pestaña: {page.url[:60]}...")
                    return page

        print(f"[Browser] No se encontró pestaña con '{url_contains}'")
        return None

    def get_all_tabs(self) -> list:
        """Retorna lista de URLs de todas las pestañas."""
        if not self._browser:
            return []

        tabs = []
        for context in self._browser.contexts:
            for page in context.pages:
                tabs.append(page.url)
        return tabs

    def is_connected(self) -> bool:
        """Verifica si hay conexión activa."""
        return self._browser is not None

    def disconnect(self):
        """Cierra la conexión CDP."""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        print("[Browser] Desconectado")
