"""
PushoverClient - Cliente para enviar notificaciones push via Pushover API.

Pushover API: https://pushover.net/api
"""

import urllib.request
import urllib.parse
import json
import threading
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class PushoverConfig:
    """Configuración de Pushover."""
    enabled: bool = False
    user_key: str = ""
    api_token: str = ""
    device: str = ""
    priority: int = 1
    sound: str = "pushover"
    url_title: str = "Responder"
    expire: int = 300
    retry: int = 30


class PushoverClient:
    """
    Cliente para enviar notificaciones push a iPhone via Pushover.

    Uso:
        client = PushoverClient(config)
        client.send_notification(
            title="Claude Code",
            message="¿Ejecutar comando?",
            url="http://100.x.x.x:8765/api/intent",
            correlation_id="abc123"
        )
    """

    API_URL = "https://api.pushover.net/1/messages.json"

    def __init__(self, config: dict):
        """
        Inicializa el cliente Pushover.

        Args:
            config: Dict con configuración pushover
        """
        self._config = PushoverConfig(
            enabled=config.get("enabled", False),
            user_key=config.get("user_key", ""),
            api_token=config.get("api_token", ""),
            device=config.get("device", ""),
            priority=config.get("priority", 1),
            sound=config.get("sound", "pushover"),
            url_title=config.get("url_title", "Responder"),
            expire=config.get("expire", 300),
            retry=config.get("retry", 30)
        )

        self._callback: Optional[Callable[[bool, str], None]] = None

    @property
    def enabled(self) -> bool:
        """True si Pushover está habilitado y configurado."""
        return (
            self._config.enabled and
            bool(self._config.user_key) and
            bool(self._config.api_token)
        )

    def send_notification(
        self,
        title: str,
        message: str,
        url: Optional[str] = None,
        correlation_id: Optional[str] = None,
        priority: Optional[int] = None,
        sound: Optional[str] = None,
        callback: Optional[Callable[[bool, str], None]] = None
    ) -> bool:
        """
        Envía una notificación push.

        Args:
            title: Título de la notificación
            message: Cuerpo del mensaje
            url: URL a abrir al tocar (opcional)
            correlation_id: ID para tracking (se añade a URL)
            priority: Override de prioridad (-2 a 2)
            sound: Override de sonido
            callback: Función a llamar con resultado (success, response)

        Returns:
            True si se envió correctamente
        """
        if not self.enabled:
            print("[Pushover] No habilitado o sin credenciales")
            return False

        # Construir payload
        data = {
            "token": self._config.api_token,
            "user": self._config.user_key,
            "title": title,
            "message": message,
            "priority": priority if priority is not None else self._config.priority,
            "sound": sound or self._config.sound,
            "html": 1  # Permitir formato HTML básico
        }

        # Dispositivo específico
        if self._config.device:
            data["device"] = self._config.device

        # URL con correlation_id
        if url:
            if correlation_id:
                # Añadir correlation_id como parámetro
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}correlation_id={correlation_id}"
            data["url"] = url
            data["url_title"] = self._config.url_title

        # Priority 2 requiere expire y retry
        if data["priority"] == 2:
            data["expire"] = self._config.expire
            data["retry"] = self._config.retry

        # Enviar en thread separado para no bloquear
        def send():
            success, response = self._do_send(data)
            if callback:
                callback(success, response)

        thread = threading.Thread(target=send, daemon=True)
        thread.start()

        return True

    def _do_send(self, data: dict) -> tuple[bool, str]:
        """
        Realiza el envío HTTP a Pushover API.

        Returns:
            (success, response_text)
        """
        try:
            # Codificar datos
            encoded_data = urllib.parse.urlencode(data).encode("utf-8")

            # Crear request
            req = urllib.request.Request(
                self.API_URL,
                data=encoded_data,
                method="POST"
            )
            req.add_header("Content-Type", "application/x-www-form-urlencoded")

            # Enviar
            with urllib.request.urlopen(req, timeout=10) as response:
                result = response.read().decode("utf-8")

                # Parsear respuesta
                try:
                    json_result = json.loads(result)
                    if json_result.get("status") == 1:
                        print(f"[Pushover] Enviado: {data.get('title', 'Sin título')}")
                        return True, result
                    else:
                        errors = json_result.get("errors", ["Unknown error"])
                        print(f"[Pushover] Error API: {errors}")
                        return False, result
                except json.JSONDecodeError:
                    return True, result

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else str(e)
            print(f"[Pushover] HTTP Error {e.code}: {error_body}")
            return False, error_body

        except urllib.error.URLError as e:
            print(f"[Pushover] Connection Error: {e.reason}")
            return False, str(e.reason)

        except Exception as e:
            print(f"[Pushover] Error: {e}")
            return False, str(e)

    def send_test(self) -> bool:
        """
        Envía una notificación de prueba.

        Returns:
            True si se envió correctamente
        """
        return self.send_notification(
            title="VoiceFlow Test",
            message="Si ves esto, Pushover está funcionando correctamente.",
            priority=0,
            sound="pushover"
        )


# Función de conveniencia para uso global
_client: Optional[PushoverClient] = None


def init_pushover(config: dict) -> PushoverClient:
    """Inicializa el cliente Pushover global."""
    global _client
    _client = PushoverClient(config)
    return _client


def get_pushover() -> Optional[PushoverClient]:
    """Obtiene el cliente Pushover global."""
    return _client


def send_push(
    title: str,
    message: str,
    url: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> bool:
    """
    Envía una notificación push usando el cliente global.

    Convenience function para uso rápido.
    """
    if _client:
        return _client.send_notification(title, message, url, correlation_id)
    return False
