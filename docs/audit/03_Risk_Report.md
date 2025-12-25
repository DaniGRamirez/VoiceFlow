# VoiceFlow - Risk Report

## Resumen de Riesgos

| Categoría | Críticos | Altos | Medios | Bajos |
|-----------|----------|-------|--------|-------|
| Seguridad | 2 | 2 | 1 | 0 |
| Estabilidad | 0 | 2 | 3 | 1 |
| Escalabilidad | 0 | 0 | 2 | 1 |
| Mantenibilidad | 0 | 2 | 3 | 2 |
| Operaciones | 0 | 1 | 2 | 1 |

---

## Seguridad

| Prioridad | Problema | Impacto | Archivo | Esfuerzo |
|-----------|----------|---------|---------|----------|
| **CRÍTICO** | Tokens en texto plano en config.json | API keys expuestas si se comparte config | `config.json` | 2h - Usar variables de entorno |
| **CRÍTICO** | Bearer token Tailscale hardcodeado | Acceso remoto comprometido | `config.json` | 1h - Mover a .env |
| **ALTO** | `shell=True` en ActionExecutor | Ejecución de código arbitrario | `core/action_executor.py:89` | 4h - Sanitizar inputs |
| **ALTO** | Sin rate limiting en EventServer | DoS potencial | `core/event_server.py` | 2h - Agregar middleware |
| **MEDIO** | Validación mínima de inputs HTTP | Injection potencial | `core/event_server.py:360` | 3h - Validar con Pydantic estricto |

### Detalle Críticos

**1. Tokens en texto plano**
```json
// config.json - EXPUESTO
{
  "picovoice": {
    "access_key": "REAL_API_KEY_HERE"  // ❌ Expuesto
  },
  "tailscale": {
    "bearer_token": "SECRET_TOKEN"     // ❌ Expuesto
  }
}
```

**Solución recomendada:**
```python
# Usar variables de entorno
import os
access_key = os.environ.get("PICOVOICE_ACCESS_KEY")
bearer_token = os.environ.get("VOICEFLOW_BEARER_TOKEN")
```

**2. Shell=True vulnerable**
```python
# core/action_executor.py:89
subprocess.run(command, shell=True)  # ❌ Permite injection
```

---

## Estabilidad

| Prioridad | Problema | Impacto | Archivo | Esfuerzo |
|-----------|----------|---------|---------|----------|
| **ALTO** | Sin manejo de reconexión en engines | App crashea si micrófono se desconecta | `core/picovoice_engine.py` | 4h |
| **ALTO** | Threads sin cleanup apropiado | Memory leaks en ejecución larga | `core/event_server.py:716` | 3h |
| **MEDIO** | Excepciones silenciadas en callbacks | Errores ocultos | `core/notification_manager.py:98` | 2h |
| **MEDIO** | Sin timeout en pyautogui | UI freeze si ventana no responde | `core/actions.py` | 2h |
| **MEDIO** | Estado global mutable | Race conditions potenciales | `core/state.py` | 4h |
| **BAJO** | Logs sin rotación | Disco lleno eventualmente | `logs/usage.json` | 1h |

### Detalle Alto

**1. Sin reconexión de micrófono**
```python
# core/picovoice_engine.py - Si el micrófono se desconecta, crashea
self.recorder = PvRecorder(device_index=-1, frame_length=512)
# No hay try/except ni lógica de reconexión
```

**2. Threads sin cleanup**
```python
# core/event_server.py:716
self._thread = threading.Thread(target=self._run, daemon=True)
# daemon=True significa que no hay cleanup graceful
```

---

## Escalabilidad

| Prioridad | Problema | Impacto | Archivo | Esfuerzo |
|-----------|----------|---------|---------|----------|
| **MEDIO** | Dict de notificaciones sin límite | Memoria crece indefinidamente | `core/notification_manager.py:79` | 1h |
| **MEDIO** | Logs JSON sin paginación | Lectura lenta con historial largo | `core/logger.py:100` | 2h |
| **BAJO** | Búsqueda lineal de comandos | O(n) por cada input | `core/commands.py:180` | 4h |

### Detalle

**Dict sin límite**
```python
# core/notification_manager.py:79
self._notifications: Dict[str, NotificationState] = {}
# Crece indefinidamente, nunca se limpia automáticamente
```

**Solución:**
```python
# Agregar cleanup periódico
if len(self._notifications) > 100:
    # Eliminar las más antiguas
    self._cleanup_old_notifications()
```

---

## Mantenibilidad

| Prioridad | Problema | Impacto | Archivo | Esfuerzo |
|-----------|----------|---------|---------|----------|
| **ALTO** | main.py con 600+ líneas | Difícil de entender y modificar | `main.py` | 8h - Split en módulos |
| **ALTO** | Sin tests unitarios | Regresiones frecuentes | Todo el proyecto | 16h - Agregar pytest |
| **MEDIO** | Código comentado obsoleto | Confusión | Varios archivos | 2h - Limpiar |
| **MEDIO** | Docstrings inconsistentes | Difícil onboarding | `core/` | 4h |
| **MEDIO** | Magic numbers hardcodeados | Difícil de configurar | `ui/overlay.py:45` | 3h |
| **BAJO** | Imports no ordenados | Estilo inconsistente | Varios | 30min - isort |
| **BAJO** | Type hints parciales | IDE support limitado | `core/actions.py` | 4h |

### Detalle Alto

**1. main.py monolítico**
```python
# main.py - 600+ líneas con:
# - Argparse
# - Inicialización de todos los componentes
# - Registro de 30+ comandos
# - Lógica de wiring
# - Callbacks
```

**Solución:** Split en:
- `cli.py` - Argparse
- `bootstrap.py` - Inicialización
- `commands_builtin.py` - Comandos built-in

**2. Sin tests**
```
$ find . -name "*test*.py" -not -path "./venv/*"
./scripts/test_dedup.py        # Solo tests manuales
./scripts/test_dedup_unit.py   # Test unitario simple
./scripts/test_tailscale.py    # Test de conectividad
```

---

## Operaciones

| Prioridad | Problema | Impacto | Archivo | Esfuerzo |
|-----------|----------|---------|---------|----------|
| **ALTO** | Sin health checks | No se detectan fallos silenciosos | N/A | 2h |
| **MEDIO** | Logs sin nivel configurable | Debug difícil en producción | `core/logger.py` | 2h |
| **MEDIO** | Sin métricas de performance | No se detectan degradaciones | N/A | 4h |
| **BAJO** | Startup sin validación | Falla tarde si falta config | `main.py` | 2h |

### Detalle

**Sin health checks**
```python
# No existe endpoint para verificar estado de:
# - Micrófono conectado
# - Motor ASR funcionando
# - PyQt6 respondiendo
```

**Solución:**
```python
@app.get("/health/deep")
async def deep_health():
    return {
        "microphone": check_microphone(),
        "engine": check_engine(),
        "overlay": check_overlay()
    }
```

---

## Riesgos No Evaluables

| Área | Razón |
|------|-------|
| Performance ASR | Requiere profiling con carga real |
| Latencia remota | Depende de red Tailscale |
| Memoria largo plazo | Requiere monitoreo en producción |
| Compatibilidad Windows | Solo probado en Windows 10/11 |

---

## Priorización Recomendada

### Semana 1 - Seguridad Crítica
1. Mover tokens a variables de entorno
2. Agregar rate limiting básico

### Semana 2 - Estabilidad
1. Manejo de reconexión micrófono
2. Cleanup de threads

### Semana 3 - Mantenibilidad
1. Split de main.py
2. Agregar tests básicos

### Semana 4 - Operaciones
1. Health checks
2. Logging mejorado
