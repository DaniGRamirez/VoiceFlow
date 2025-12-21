"""
EventServer - Servidor HTTP para recibir eventos de Claude Code.

Ejecuta FastAPI en un thread separado para no bloquear PyQt6.
"""

import threading
import uuid
import time
import json
import os
import logging
from datetime import datetime
from typing import Callable, Optional, Dict, Any, List

try:
    from fastapi import FastAPI, HTTPException, Request, Header, Depends
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# Logger para Tailscale
_tailscale_logger = logging.getLogger("voiceflow.tailscale")


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

    class CommandRequest(BaseModel):
        """Request para ejecutar un comando de voz."""
        command: str  # Texto del comando (ej: "enter", "aceptar", "dictado")
        source: str = "iphone"

    class StatusResponse(BaseModel):
        """Response del estado del servidor."""
        status: str = "running"
        notifications_count: int = 0
        pending_count: int = 0
        uptime_seconds: float = 0

    class HealthResponse(BaseModel):
        """Response del health check."""
        status: str = "healthy"
        service: str = "VoiceFlow"
        tailscale_enabled: bool = False
        uptime_seconds: float = 0

    class PingResponse(BaseModel):
        """Response del ping (latencia)."""
        pong: bool = True
        server_time: str
        server_timestamp_ms: int

    class MetricsStats(BaseModel):
        """Estadísticas de métricas."""
        count: int = 0
        median_ms: float = 0
        p95_ms: float = 0
        min_ms: float = 0
        max_ms: float = 0

    class MetricsResponse(BaseModel):
        """Response de métricas."""
        stats: MetricsStats
        recent: List[dict] = []


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
        on_intent: Optional[Callable[[dict], None]] = None,
        on_dismiss: Optional[Callable[[str], None]] = None,
        tailscale_config: Optional[dict] = None,
        execute_action: Optional[Callable[[dict], bool]] = None,
        on_command: Optional[Callable[[str], dict]] = None
    ):
        if not FASTAPI_AVAILABLE:
            raise ImportError("FastAPI no instalado. Ejecuta: pip install fastapi uvicorn")

        self.host = host
        self.port = port
        self.on_notification = on_notification
        self.on_intent = on_intent
        self.on_dismiss = on_dismiss
        self.execute_action = execute_action  # Para ejecutar hotkeys directamente
        self.on_command = on_command  # Para ejecutar comandos de voz via HTTP

        self._start_time = time.time()
        self._notifications: Dict[str, dict] = {}
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Configuración Tailscale
        self._tailscale = tailscale_config or {}
        self._tailscale_enabled = self._tailscale.get("enabled", False)
        self._bearer_token = self._tailscale.get("bearer_token", "")
        self._allowed_ips = set(self._tailscale.get("allowed_ips", []))
        self._log_requests = self._tailscale.get("log_requests", True)
        self._metrics_file = self._tailscale.get("metrics_file", "logs/tailscale_metrics.json")
        self._metrics: List[dict] = []

        self._app = self._create_app()

    def _create_auth_dependency(self):
        """Crea dependencia de autenticación Bearer para endpoints remotos."""

        async def verify_token(
            request: Request,
            authorization: Optional[str] = Header(None)
        ):
            # Obtener IP remota
            client_ip = request.client.host if request.client else "unknown"

            # Localhost siempre permitido sin auth
            if client_ip in ("127.0.0.1", "localhost", "::1"):
                return True

            # Si Tailscale no está habilitado, permitir todo (modo local)
            if not self._tailscale_enabled:
                return True

            # Lista blanca de IPs (si está configurada)
            if self._allowed_ips and client_ip not in self._allowed_ips:
                self._log_metric(request, 403, 0)
                raise HTTPException(status_code=403, detail="IP not allowed")

            # Verificar Bearer token
            if not authorization:
                self._log_metric(request, 401, 0)
                raise HTTPException(status_code=401, detail="Authorization header required")

            if not authorization.startswith("Bearer "):
                self._log_metric(request, 401, 0)
                raise HTTPException(status_code=401, detail="Bearer token required")

            token = authorization[7:]
            if token != self._bearer_token:
                self._log_metric(request, 401, 0)
                raise HTTPException(status_code=401, detail="Invalid token")

            return True

        return verify_token

    def _log_metric(self, request: Request, status_code: int, latency_ms: float):
        """Registra métrica de request."""
        if not self._log_requests:
            return

        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")

        entry = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": str(request.url.path),
            "method": request.method,
            "remote_ip": client_ip,
            "latency_ms": round(latency_ms, 2),
            "status_code": status_code,
            "user_agent": user_agent[:100]  # Truncar UA largo
        }

        self._metrics.append(entry)

        # Log a consola
        _tailscale_logger.info(
            f"[{client_ip}] {request.method} {request.url.path} "
            f"-> {status_code} ({latency_ms:.1f}ms)"
        )

        # Guardar a archivo periódicamente (cada 10 entries)
        if len(self._metrics) >= 10:
            self._flush_metrics()

    def _flush_metrics(self):
        """Guarda métricas a archivo JSON."""
        if not self._metrics:
            return

        try:
            # Asegurar que el directorio existe
            metrics_dir = os.path.dirname(self._metrics_file)
            if metrics_dir and not os.path.exists(metrics_dir):
                os.makedirs(metrics_dir, exist_ok=True)

            # Leer existentes
            existing = []
            if os.path.exists(self._metrics_file):
                with open(self._metrics_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)

            # Agregar nuevas
            existing.extend(self._metrics)

            # Mantener solo últimas 1000
            existing = existing[-1000:]

            # Guardar
            with open(self._metrics_file, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)

            self._metrics.clear()
        except Exception as e:
            _tailscale_logger.error(f"Error saving metrics: {e}")

    def _calculate_stats(self, latencies: List[float]) -> dict:
        """Calcula estadísticas de latencias."""
        if not latencies:
            return {"count": 0, "median_ms": 0, "p95_ms": 0, "min_ms": 0, "max_ms": 0}

        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)

        return {
            "count": n,
            "median_ms": latencies_sorted[n // 2],
            "p95_ms": latencies_sorted[int(n * 0.95)] if n > 1 else latencies_sorted[0],
            "min_ms": min(latencies_sorted),
            "max_ms": max(latencies_sorted)
        }

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

        # Crear dependencia de autenticación
        verify_auth = self._create_auth_dependency()

        # ========== ENDPOINTS TAILSCALE ==========

        @app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check para verificar conectividad (sin auth)."""
            return HealthResponse(
                status="healthy",
                service="VoiceFlow",
                tailscale_enabled=self._tailscale_enabled,
                uptime_seconds=time.time() - self._start_time
            )

        @app.get("/ping", response_model=PingResponse)
        async def ping(request: Request, _: bool = Depends(verify_auth)):
            """Mide latencia roundtrip. Devuelve timestamps."""
            start_time = time.time()

            response = PingResponse(
                pong=True,
                server_time=datetime.now().isoformat(),
                server_timestamp_ms=int(time.time() * 1000)
            )

            # Log métrica
            latency = (time.time() - start_time) * 1000
            self._log_metric(request, 200, latency)

            return response

        @app.get("/api/metrics")
        async def get_metrics(request: Request, _: bool = Depends(verify_auth)):
            """Devuelve métricas de latencia (requiere auth)."""
            # Flush pendientes
            self._flush_metrics()

            try:
                if os.path.exists(self._metrics_file):
                    with open(self._metrics_file, 'r', encoding='utf-8') as f:
                        metrics = json.load(f)

                    # Calcular estadísticas
                    latencies = [m["latency_ms"] for m in metrics if m.get("latency_ms")]
                    stats = self._calculate_stats(latencies)

                    return {
                        "stats": stats,
                        "recent": metrics[-20:]  # Últimos 20
                    }
            except Exception as e:
                _tailscale_logger.error(f"Error reading metrics: {e}")

            return {"stats": {"count": 0}, "recent": []}

        # ========== ENDPOINTS EXISTENTES ==========

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
        async def execute_intent(
            intent: IntentRequest,
            request: Request,
            _: bool = Depends(verify_auth)
        ):
            """Ejecuta un intent (respuesta a notificación). Requiere auth si Tailscale está habilitado."""
            start_time = time.time()
            cid = intent.correlation_id

            # Verificar que existe la notificación
            if cid not in self._notifications:
                self._log_metric(request, 404, (time.time() - start_time) * 1000)
                raise HTTPException(status_code=404, detail="Notificación no encontrada")

            notification = self._notifications[cid]

            # Verificar estado
            if notification.get("status") != "pending":
                self._log_metric(request, 400, (time.time() - start_time) * 1000)
                raise HTTPException(
                    status_code=400,
                    detail=f"Notificación en estado '{notification.get('status')}', no puede ejecutarse"
                )

            # Actualizar estado
            notification["status"] = "executing"

            # Preparar intent data
            intent_data = intent.model_dump()
            intent_data["notification"] = notification
            intent_data["remote_ip"] = request.client.host if request.client else "unknown"

            # Callback
            if self.on_intent:
                try:
                    self.on_intent(intent_data)
                    notification["status"] = "completed"
                except Exception as e:
                    notification["status"] = "failed"
                    self._log_metric(request, 500, (time.time() - start_time) * 1000)
                    print(f"[EventServer] Error ejecutando intent: {e}")
                    raise HTTPException(status_code=500, detail=str(e))

            latency = (time.time() - start_time) * 1000
            self._log_metric(request, 200, latency)
            print(f"[EventServer] Intent ejecutado: {intent.intent} en {cid[:12]}... ({latency:.1f}ms)")

            return {
                "success": True,
                "correlation_id": cid,
                "intent": intent.intent,
                "status": notification["status"],
                "processing_ms": round(latency, 2)
            }

        # ========== ENDPOINTS CONVENIENCE (para Shortcuts) ==========

        def _get_latest_pending(self) -> tuple:
            """Obtiene la última notificación pendiente."""
            pending = [
                (cid, n) for cid, n in self._notifications.items()
                if n.get("status") == "pending"
            ]
            if not pending:
                return None, None
            # Ordenar por timestamp (más reciente primero)
            pending.sort(key=lambda x: x[1].get("timestamp", ""), reverse=True)
            return pending[0]

        @app.post("/api/accept")
        async def accept_latest(
            request: Request,
            _: bool = Depends(verify_auth)
        ):
            """
            Acepta/confirma desde iPhone.

            Si hay notificación pendiente -> la procesa
            Si NO hay notificación -> ejecuta Enter en VSCode directamente

            Ideal para iOS Shortcuts.
            """
            start_time = time.time()
            client_ip = request.client.host if request.client else "unknown"

            cid, notification = _get_latest_pending(self)

            if cid and notification:
                # Hay notificación pendiente -> procesar normalmente
                notification["status"] = "executing"
                intent_data = {
                    "correlation_id": cid,
                    "intent": "accept",
                    "hotkey": "enter",
                    "source": "shortcut",
                    "notification": notification,
                    "remote_ip": client_ip
                }

                if self.on_intent:
                    try:
                        self.on_intent(intent_data)
                        notification["status"] = "completed"
                    except Exception as e:
                        notification["status"] = "failed"
                        self._log_metric(request, 500, (time.time() - start_time) * 1000)
                        raise HTTPException(status_code=500, detail=str(e))

                latency = (time.time() - start_time) * 1000
                self._log_metric(request, 200, latency)
                print(f"[EventServer] Accept via shortcut: {cid[:12]}... ({latency:.1f}ms)")

                return {
                    "success": True,
                    "correlation_id": cid,
                    "intent": "accept",
                    "title": notification.get("title", ""),
                    "processing_ms": round(latency, 2),
                    "mode": "notification"
                }
            else:
                # NO hay notificación pendiente -> ejecutar hotkey directamente
                if self.execute_action:
                    try:
                        action = {"id": "accept", "hotkey": "enter", "label": "Accept (global)"}
                        self.execute_action(action)

                        latency = (time.time() - start_time) * 1000
                        self._log_metric(request, 200, latency)
                        print(f"[EventServer] Accept global (sin notificación) desde {client_ip} ({latency:.1f}ms)")

                        return {
                            "success": True,
                            "correlation_id": None,
                            "intent": "accept",
                            "title": "Comando global",
                            "processing_ms": round(latency, 2),
                            "mode": "global"
                        }
                    except Exception as e:
                        self._log_metric(request, 500, (time.time() - start_time) * 1000)
                        raise HTTPException(status_code=500, detail=str(e))
                else:
                    self._log_metric(request, 404, (time.time() - start_time) * 1000)
                    raise HTTPException(status_code=404, detail="No hay notificaciones pendientes y no hay callback de ejecución")

        @app.post("/api/reject")
        async def reject_latest(
            request: Request,
            _: bool = Depends(verify_auth)
        ):
            """
            Rechaza/cancela desde iPhone.

            Si hay notificación pendiente -> la procesa
            Si NO hay notificación -> ejecuta Escape en VSCode directamente

            Ideal para iOS Shortcuts.
            """
            start_time = time.time()
            client_ip = request.client.host if request.client else "unknown"

            cid, notification = _get_latest_pending(self)

            if cid and notification:
                # Hay notificación pendiente -> procesar normalmente
                notification["status"] = "executing"
                intent_data = {
                    "correlation_id": cid,
                    "intent": "reject",
                    "hotkey": "escape",
                    "source": "shortcut",
                    "notification": notification,
                    "remote_ip": client_ip
                }

                if self.on_intent:
                    try:
                        self.on_intent(intent_data)
                        notification["status"] = "completed"
                    except Exception as e:
                        notification["status"] = "failed"
                        self._log_metric(request, 500, (time.time() - start_time) * 1000)
                        raise HTTPException(status_code=500, detail=str(e))

                latency = (time.time() - start_time) * 1000
                self._log_metric(request, 200, latency)
                print(f"[EventServer] Reject via shortcut: {cid[:12]}... ({latency:.1f}ms)")

                return {
                    "success": True,
                    "correlation_id": cid,
                    "intent": "reject",
                    "title": notification.get("title", ""),
                    "processing_ms": round(latency, 2),
                    "mode": "notification"
                }
            else:
                # NO hay notificación pendiente -> ejecutar hotkey directamente
                if self.execute_action:
                    try:
                        action = {"id": "reject", "hotkey": "escape", "label": "Reject (global)"}
                        self.execute_action(action)

                        latency = (time.time() - start_time) * 1000
                        self._log_metric(request, 200, latency)
                        print(f"[EventServer] Reject global (sin notificación) desde {client_ip} ({latency:.1f}ms)")

                        return {
                            "success": True,
                            "correlation_id": None,
                            "intent": "reject",
                            "title": "Comando global",
                            "processing_ms": round(latency, 2),
                            "mode": "global"
                        }
                    except Exception as e:
                        self._log_metric(request, 500, (time.time() - start_time) * 1000)
                        raise HTTPException(status_code=500, detail=str(e))
                else:
                    self._log_metric(request, 404, (time.time() - start_time) * 1000)
                    raise HTTPException(status_code=404, detail="No hay notificaciones pendientes y no hay callback de ejecución")

        # ========== ENDPOINT COMANDO GENÉRICO ==========

        @app.post("/api/command")
        async def execute_command(
            cmd: CommandRequest,
            request: Request,
            _: bool = Depends(verify_auth)
        ):
            """
            Ejecuta un comando de voz desde iPhone.

            Equivalente a decir el comando por voz.
            Ejemplos: "enter", "aceptar", "dictado", "escape", "tab"

            Body JSON:
                {"command": "enter"}
                {"command": "aceptar"}
            """
            start_time = time.time()
            client_ip = request.client.host if request.client else "unknown"
            command_text = cmd.command.strip().lower()

            if not self.on_command:
                self._log_metric(request, 501, (time.time() - start_time) * 1000)
                raise HTTPException(status_code=501, detail="Comandos no configurados")

            try:
                result = self.on_command(command_text)

                latency = (time.time() - start_time) * 1000
                self._log_metric(request, 200, latency)

                print(f"[EventServer] Comando '{command_text}' desde {client_ip} ({latency:.1f}ms)")

                return {
                    "success": result.get("success", False),
                    "command": command_text,
                    "executed": result.get("executed", []),
                    "processing_ms": round(latency, 2),
                    "source": cmd.source
                }

            except Exception as e:
                self._log_metric(request, 500, (time.time() - start_time) * 1000)
                print(f"[EventServer] Error comando '{command_text}': {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/api/notifications")
        async def list_notifications():
            """Lista todas las notificaciones."""
            return {
                "notifications": list(self._notifications.values()),
                "count": len(self._notifications)
            }

        @app.delete("/api/notification/{correlation_id}")
        async def delete_notification(correlation_id: str):
            """Elimina una notificación (dismiss)."""
            # Eliminar de nuestra lista interna si existe
            if correlation_id in self._notifications:
                del self._notifications[correlation_id]

            # Callback para notificar al panel
            if self.on_dismiss:
                try:
                    self.on_dismiss(correlation_id)
                except Exception as e:
                    print(f"[EventServer] Error en callback de dismiss: {e}")

            print(f"[EventServer] Dismiss: {correlation_id[:12]}...")
            return {"success": True, "message": "Notificación eliminada"}

        @app.get("/")
        async def root():
            """Endpoint raíz para verificar que el servidor está activo."""
            endpoints = [
                "GET  /health              - Health check (sin auth)",
                "GET  /ping                - Medir latencia (requiere auth)",
                "GET  /api/status          - Estado del servidor",
                "GET  /api/metrics         - Métricas de latencia (requiere auth)",
                "POST /api/notification    - Crear notificación",
                "POST /api/intent          - Ejecutar intent (requiere auth)",
                "POST /api/accept          - Aceptar/Enter global (Shortcut)",
                "POST /api/reject          - Rechazar/Escape global (Shortcut)",
                "POST /api/command         - Ejecutar comando de voz (requiere auth)",
                "GET  /api/notifications   - Listar notificaciones",
                "DELETE /api/notification/{id} - Eliminar notificación"
            ]
            return {
                "service": "VoiceFlow Event Server",
                "status": "running",
                "tailscale_enabled": self._tailscale_enabled,
                "endpoints": endpoints
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
        """Detiene el servidor y guarda métricas pendientes."""
        self._flush_metrics()  # Guardar métricas pendientes
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
