"""
EventServer - Servidor HTTP para recibir eventos de Claude Code.

Ejecuta FastAPI en un thread separado para no bloquear PyQt6.
"""

import threading
import uuid
import time
from typing import Callable, Optional, Dict, Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


# ========== MODELOS ==========

if FASTAPI_AVAILABLE:
    class NotificationAction(BaseModel):
        """Acción disponible en una notificación."""
        id: str
        label: str
        hotkey: str = "enter"
        style: str = "secondary"

    class NotificationRequest(BaseModel):
        """Request para crear una notificación."""
        correlation_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
        title: str
        body: str = ""
        type: str = "confirmation"
        actions: list = Field(default_factory=lambda: [
            {"id": "accept", "label": "Aceptar", "hotkey": "enter", "style": "primary"},
            {"id": "cancel", "label": "Cancelar", "hotkey": "escape", "style": "secondary"}
        ])
        source: str = "claude_code"
        timeout_seconds: int = 120

    class IntentRequest(BaseModel):
        """Request para ejecutar un intent."""
        correlation_id: str
        intent: str
        hotkey: Optional[str] = None
        source: str = "external"

    class StatusResponse(BaseModel):
        """Response del estado del servidor."""
        status: str = "running"
        notifications_count: int = 0
        pending_count: int = 0
        uptime_seconds: float = 0


class EventServer:
    """
    Servidor HTTP para recibir eventos de Claude Code.

    Uso:
        server = EventServer(
            host="localhost",
            port=8765,
            on_notification=lambda n: panel.add_notification(n),
            on_intent=lambda i: manager.execute_intent(i)
        )
        server.start()  # Inicia en thread separado
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        on_notification: Optional[Callable[[dict], None]] = None,
        on_intent: Optional[Callable[[dict], None]] = None
    ):
        if not FASTAPI_AVAILABLE:
            raise ImportError("FastAPI no instalado. Ejecuta: pip install fastapi uvicorn")

        self.host = host
        self.port = port
        self.on_notification = on_notification
        self.on_intent = on_intent

        self._start_time = time.time()
        self._notifications: Dict[str, dict] = {}
        self._thread: Optional[threading.Thread] = None
        self._running = False

        self._app = self._create_app()

    def _create_app(self) -> "FastAPI":
        """Crea la aplicación FastAPI."""
        app = FastAPI(
            title="VoiceFlow Event Server",
            description="Servidor para notificaciones de Claude Code",
            version="1.0.0"
        )

        # CORS para permitir requests desde otras fuentes
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # ========== ENDPOINTS ==========

        @app.get("/api/status", response_model=StatusResponse)
        async def get_status():
            """Estado del servidor."""
            pending = sum(1 for n in self._notifications.values() if n.get("status") == "pending")
            return StatusResponse(
                status="running",
                notifications_count=len(self._notifications),
                pending_count=pending,
                uptime_seconds=time.time() - self._start_time
            )

        @app.post("/api/notification")
        async def create_notification(notification: NotificationRequest):
            """Crea una nueva notificación."""
            data = notification.model_dump()
            data["timestamp"] = time.time()
            data["status"] = "pending"

            # Guardar
            self._notifications[data["correlation_id"]] = data

            # Callback
            if self.on_notification:
                try:
                    self.on_notification(data)
                except Exception as e:
                    print(f"[EventServer] Error en callback de notificación: {e}")

            print(f"[EventServer] Nueva notificación: {data['title']}")

            return {
                "success": True,
                "correlation_id": data["correlation_id"],
                "message": "Notificación creada"
            }

        @app.post("/api/intent")
        async def execute_intent(intent: IntentRequest):
            """Ejecuta un intent (respuesta a notificación)."""
            cid = intent.correlation_id

            # Verificar que existe la notificación
            if cid not in self._notifications:
                raise HTTPException(status_code=404, detail="Notificación no encontrada")

            notification = self._notifications[cid]

            # Verificar estado
            if notification.get("status") != "pending":
                raise HTTPException(
                    status_code=400,
                    detail=f"Notificación en estado '{notification.get('status')}', no puede ejecutarse"
                )

            # Actualizar estado
            notification["status"] = "executing"

            # Preparar intent data
            intent_data = intent.model_dump()
            intent_data["notification"] = notification

            # Callback
            if self.on_intent:
                try:
                    self.on_intent(intent_data)
                    notification["status"] = "completed"
                except Exception as e:
                    notification["status"] = "failed"
                    print(f"[EventServer] Error ejecutando intent: {e}")
                    raise HTTPException(status_code=500, detail=str(e))

            print(f"[EventServer] Intent ejecutado: {intent.intent} en {cid}")

            return {
                "success": True,
                "correlation_id": cid,
                "intent": intent.intent,
                "status": notification["status"]
            }

        @app.get("/api/notifications")
        async def list_notifications():
            """Lista todas las notificaciones."""
            return {
                "notifications": list(self._notifications.values()),
                "count": len(self._notifications)
            }

        @app.delete("/api/notification/{correlation_id}")
        async def delete_notification(correlation_id: str):
            """Elimina una notificación."""
            if correlation_id not in self._notifications:
                raise HTTPException(status_code=404, detail="Notificación no encontrada")

            del self._notifications[correlation_id]
            return {"success": True, "message": "Notificación eliminada"}

        @app.get("/")
        async def root():
            """Endpoint raíz para verificar que el servidor está activo."""
            return {
                "service": "VoiceFlow Event Server",
                "status": "running",
                "endpoints": [
                    "GET  /api/status",
                    "POST /api/notification",
                    "POST /api/intent",
                    "GET  /api/notifications",
                    "DELETE /api/notification/{id}"
                ]
            }

        return app

    def start(self):
        """Inicia el servidor en un thread separado."""
        if self._running:
            print("[EventServer] Ya está corriendo")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"[EventServer] Iniciado en http://{self.host}:{self.port}")

    def _run(self):
        """Ejecuta uvicorn (bloquea el thread)."""
        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False
        )
        server = uvicorn.Server(config)
        server.run()

    def stop(self):
        """Detiene el servidor."""
        self._running = False
        # uvicorn no tiene stop graceful fácil, el thread daemon morirá con el proceso

    @property
    def is_running(self) -> bool:
        return self._running

    def update_notification_status(self, correlation_id: str, status: str):
        """Actualiza el estado de una notificación."""
        if correlation_id in self._notifications:
            self._notifications[correlation_id]["status"] = status


# ========== FUNCIÓN DE PRUEBA ==========

def test_server():
    """Prueba básica del servidor."""
    def on_notification(data):
        print(f"[Test] Notificación recibida: {data['title']}")

    def on_intent(data):
        print(f"[Test] Intent recibido: {data['intent']}")

    server = EventServer(
        host="localhost",
        port=8765,
        on_notification=on_notification,
        on_intent=on_intent
    )
    server.start()

    print("Servidor corriendo. Prueba con:")
    print('  curl -X POST http://localhost:8765/api/notification \\')
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"title": "Test", "body": "Hola mundo"}\'')
    print("\nPresiona Ctrl+C para salir...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo...")


if __name__ == "__main__":
    test_server()
