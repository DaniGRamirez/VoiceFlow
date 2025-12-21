"""
BrowserActionExecutor - Ejecutor de acciones de navegador.

Ejecuta pipelines de acciones sobre páginas web usando Playwright.
Soporta: connect, find_tab, wait_for, fill, click, paste, press.
"""

from typing import Optional
import pyperclip

from .browser_manager import BrowserManager


class BrowserActionExecutor:
    """
    Ejecuta acciones de navegador en un pipeline.

    Acciones soportadas:
        connect    - Conecta a Chrome via CDP
        find_tab   - Busca pestaña por URL
        wait_for   - Espera selector en DOM
        fill       - Escribe texto en input
        click      - Click en elemento
        paste      - Pega contenido del clipboard
        press      - Pulsa tecla
        clear      - Limpia contenido de un elemento
        count_messages       - Guarda número actual de mensajes
        wait_for_new_message - Espera mensaje nuevo
        click_last_menu_item - Click en menú del último mensaje
    """

    def __init__(self):
        self.manager = BrowserManager.get_instance()
        self.current_page = None
        self.message_count_before = 0  # Para tracking de mensajes nuevos
        self.last_error = None  # Último error descriptivo

    def execute(self, actions: list, command_name: str = "browser") -> bool:
        """
        Ejecuta lista de acciones browser.

        Args:
            actions: Lista de dicts con acciones
            command_name: Nombre del comando (para logs)

        Returns:
            True si todas las acciones se ejecutaron OK
        """
        for i, action in enumerate(actions):
            action_type = action.get("action", "unknown")
            try:
                print(f"[Browser] {command_name} - paso {i+1}: {action_type}")
                success = self._execute_one(action)
                if not success:
                    print(f"[Browser] Acción '{action_type}' falló")
                    return False
            except Exception as e:
                print(f"[Browser] ERROR en paso {i+1} ({action_type}): {e}")
                return False
        return True

    def _execute_one(self, action: dict) -> bool:
        """Ejecuta una sola acción."""
        action_type = action.get("action")

        if action_type == "connect":
            port = action.get("port", 9222)
            return self.manager.connect(port)

        elif action_type == "find_tab":
            url_contains = action.get("url_contains", "")
            self.current_page = self.manager.find_tab(url_contains)
            if not self.current_page:
                # Mensaje de error específico según la URL buscada
                if "chatgpt" in url_contains.lower() or "chat.openai" in url_contains.lower():
                    self.last_error = "ChatGPT no está listo. Abre chat.openai.com en Edge."
                elif "claude" in url_contains.lower():
                    self.last_error = "Claude no está listo. Abre claude.ai en Edge."
                else:
                    self.last_error = f"No se encontró pestaña con '{url_contains}' en Edge."
                print(f"[Browser] {self.last_error}")
                return False
            self.current_page.bring_to_front()
            return True

        elif action_type == "wait_for":
            if not self.current_page:
                print("[Browser] No hay página activa")
                return False
            selector = action.get("selector", "")
            timeout = action.get("timeout", 5) * 1000  # segundos a ms
            try:
                self.current_page.wait_for_selector(selector, timeout=timeout)
                return True
            except Exception as e:
                print(f"[Browser] Timeout esperando '{selector}': {e}")
                return False

        elif action_type == "fill":
            if not self.current_page:
                return False
            selector = action.get("selector", "")
            text = action.get("text", "")
            # Interpolar {clipboard}
            text = text.replace("{clipboard}", pyperclip.paste() or "")
            self.current_page.fill(selector, text)
            return True

        elif action_type == "click":
            if not self.current_page:
                return False
            selector = action.get("selector", "")
            self.current_page.click(selector)
            return True

        elif action_type == "paste":
            if not self.current_page:
                return False
            selector = action.get("selector", "")
            content = pyperclip.paste() or ""
            if not content:
                print("[Browser] Clipboard vacío")
                return False
            # Enfocar elemento y escribir
            element = self.current_page.locator(selector)
            element.focus()
            self.current_page.keyboard.insert_text(content)
            return True

        elif action_type == "press":
            if not self.current_page:
                return False
            key = action.get("key", "Enter")
            self.current_page.keyboard.press(key)
            return True

        elif action_type == "clear":
            if not self.current_page:
                return False
            selector = action.get("selector", "")
            # Triple click para seleccionar todo + delete
            self.current_page.click(selector, click_count=3)
            self.current_page.keyboard.press("Delete")
            return True

        elif action_type == "clear_textarea":
            # Limpia un textarea usando Ctrl+A + Delete
            if not self.current_page:
                return False
            selector = action.get("selector", "")
            try:
                element = self.current_page.locator(selector).first
                element.click()
                self.current_page.keyboard.press("Control+a")
                self.current_page.keyboard.press("Delete")
                return True
            except Exception as e:
                print(f"[Browser] Error limpiando textarea: {e}")
                return False

        elif action_type == "wait":
            import time
            seconds = action.get("seconds", 0.5)
            time.sleep(seconds)
            return True

        elif action_type == "focus_window":
            # Trae la ventana del navegador al frente
            try:
                import pygetwindow as gw
                # Buscar por título (Edge, Chrome, etc.)
                title = action.get("title", "Edge")
                windows = gw.getWindowsWithTitle(title)
                if windows:
                    win = windows[0]
                    if win.isMinimized:
                        win.restore()
                    win.activate()
                    print(f"[Browser] Ventana activada: {win.title[:50]}")
                    return True
                else:
                    print(f"[Browser] No se encontró ventana con título '{title}'")
                    return False
            except Exception as e:
                print(f"[Browser] Error activando ventana: {e}")
                return False

        elif action_type == "count_messages":
            # Guarda el número actual de mensajes para detectar nuevos
            if not self.current_page:
                return False
            try:
                turns = self.current_page.locator('[data-testid^="conversation-turn"]').all()
                self.message_count_before = len(turns)
                print(f"[Browser] Mensajes actuales: {self.message_count_before}")
                return True
            except Exception as e:
                print(f"[Browser] Error contando mensajes: {e}")
                return False

        elif action_type == "wait_for_new_message":
            # Espera hasta que aparezca un mensaje nuevo (respuesta de ChatGPT)
            if not self.current_page:
                return False
            timeout = action.get("timeout", 120)
            import time
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    turns = self.current_page.locator('[data-testid^="conversation-turn"]').all()
                    current_count = len(turns)

                    # Necesitamos al menos 2 mensajes nuevos (el nuestro + la respuesta)
                    if current_count >= self.message_count_before + 2:
                        # Verificar que el último mensaje tiene el botón "Más acciones" (respuesta completa)
                        last_turn = turns[-1]
                        more_actions = last_turn.locator('button[aria-label="Más acciones"]')
                        if more_actions.count() > 0:
                            print(f"[Browser] Mensaje nuevo detectado (total: {current_count})")
                            return True

                    time.sleep(0.5)
                except Exception:
                    time.sleep(0.5)

            print(f"[Browser] Timeout esperando mensaje nuevo")
            return False

        elif action_type == "click_last_menu_item":
            # Click en un item del menú del ÚLTIMO mensaje
            if not self.current_page:
                return False
            menu_button = action.get("menu_button", "Más acciones")
            item_text = action.get("item_text", "")
            try:
                # Obtener el último conversation-turn
                last_turn = self.current_page.locator('[data-testid^="conversation-turn"]').last

                # Click en el botón del menú dentro de ese turn
                btn = last_turn.locator(f'button[aria-label="{menu_button}"]')
                btn.click()

                import time
                time.sleep(0.3)

                # Click en el item del menú
                menu_item = self.current_page.locator(f'[role="menuitem"]:has-text("{item_text}")')
                menu_item.click()
                print(f"[Browser] Clicked en último mensaje: {menu_button} -> {item_text}")
                return True
            except Exception as e:
                print(f"[Browser] Error en menú del último mensaje: {e}")
                return False

        elif action_type == "wait_for_idle":
            # DEPRECATED: usar count_messages + wait_for_new_message
            if not self.current_page:
                return False
            timeout = action.get("timeout", 60) * 1000
            try:
                self.current_page.wait_for_selector(
                    'button[aria-label="Más acciones"]',
                    timeout=timeout,
                    state="visible"
                )
                print("[Browser] ChatGPT terminó de responder")
                return True
            except Exception as e:
                print(f"[Browser] Timeout esperando respuesta: {e}")
                return False

        elif action_type == "click_menu_item":
            # DEPRECATED: usar click_last_menu_item
            if not self.current_page:
                return False
            menu_button = action.get("menu_button", "")
            item_text = action.get("item_text", "")
            try:
                btn = self.current_page.locator(f'button[aria-label="{menu_button}"]').last
                btn.click()
                import time
                time.sleep(0.3)
                menu_item = self.current_page.locator(f'[role="menuitem"]:has-text("{item_text}")')
                menu_item.click()
                print(f"[Browser] Clicked: {menu_button} -> {item_text}")
                return True
            except Exception as e:
                print(f"[Browser] Error en menú: {e}")
                return False

        else:
            print(f"[Browser] Acción desconocida: {action_type}")
            return False
