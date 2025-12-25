# VoiceFlow - Plan de Mejora Consolidado

## Resumen Ejecutivo

Basado en la auditoría completa, este plan prioriza:
1. **Seguridad** - Eliminar riesgos críticos (tokens expuestos)
2. **Limpieza** - Eliminar ~570 líneas de código muerto
3. **Estabilidad** - Manejo de errores y reconexión
4. **Mantenibilidad** - Split de main.py, tests básicos

**Esfuerzo total estimado:** 40-50 horas (2-3 semanas part-time)

---

## Fase 1: Limpieza Inmediata (2-4 horas)

### 1.1 Eliminar Dead Code

```bash
# Archivos a eliminar
rm -f core/skill_registry.py
rm -f core/skill_dispatcher.py
rm -f core/skill_handlers.py
rm -f core/skill_integration.py
rm -f core/permission_store.py
rm -f ui/ui_Merged.txt
rm -f claude-pty-wrapper/del
```

**Beneficio:** -500 líneas, menos confusión
**Riesgo:** Ninguno

### 1.2 Limpiar Archivos Basura

```bash
# Windows special files
rm -f nul ui/nul

# Archivos con encoding raro (ver git status)
git clean -f "c*test_hook*" "c*test_type*"
```

### 1.3 Actualizar .gitignore

```gitignore
# Agregar
.pytest_cache/
.mypy_cache/
.coverage
coverage.xml
logs/usage.json
*.bak
nul
```

**Commit:** `chore: Remove dead code and clean repository`

---

## Fase 2: Seguridad Crítica (3-4 horas)

### 2.1 Variables de Entorno para Secrets

**Problema:** Tokens en texto plano en config.json

**Solución:**

1. Crear `.env.example`:
```env
PICOVOICE_ACCESS_KEY=your_key_here
VOICEFLOW_BEARER_TOKEN=your_token_here
PUSHOVER_USER_KEY=your_key_here
PUSHOVER_API_TOKEN=your_token_here
```

2. Modificar `config/settings.py`:
```python
import os
from dotenv import load_dotenv

load_dotenv()

def load_config():
    config = _load_json_config()

    # Override sensibles con env vars
    if os.environ.get("PICOVOICE_ACCESS_KEY"):
        config["picovoice"]["access_key"] = os.environ["PICOVOICE_ACCESS_KEY"]
    if os.environ.get("VOICEFLOW_BEARER_TOKEN"):
        config["tailscale"]["bearer_token"] = os.environ["VOICEFLOW_BEARER_TOKEN"]

    return config
```

3. Agregar `python-dotenv` a requirements.txt

**Commit:** `fix(security): Move secrets to environment variables`

### 2.2 Rate Limiting Básico

Agregar a `core/event_server.py`:

```python
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, max_requests=60, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        # Limpiar requests viejos
        self._requests[client_ip] = [
            t for t in self._requests[client_ip]
            if now - t < self.window
        ]
        if len(self._requests[client_ip]) >= self.max_requests:
            return False
        self._requests[client_ip].append(now)
        return True
```

**Commit:** `fix(security): Add basic rate limiting to EventServer`

---

## Fase 3: Estabilidad (6-8 horas)

### 3.1 Manejo de Reconexión de Micrófono

Modificar `core/picovoice_engine.py`:

```python
def _safe_record(self):
    """Intenta grabar con reconexión automática."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return self.recorder.read()
        except Exception as e:
            print(f"[Engine] Error grabando (intento {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
                self._reconnect_recorder()
            else:
                raise

def _reconnect_recorder(self):
    """Reinicializa el grabador."""
    try:
        if self.recorder:
            self.recorder.stop()
            self.recorder.delete()
    except:
        pass
    self.recorder = PvRecorder(device_index=-1, frame_length=512)
    self.recorder.start()
```

**Commit:** `fix(stability): Add microphone reconnection handling`

### 3.2 Cleanup de Notificaciones

Agregar a `core/notification_manager.py`:

```python
MAX_NOTIFICATIONS = 100

def _cleanup_old_notifications(self):
    """Elimina notificaciones antiguas si hay demasiadas."""
    if len(self._notifications) <= MAX_NOTIFICATIONS:
        return

    # Ordenar por created_at y eliminar las más viejas
    sorted_items = sorted(
        self._notifications.items(),
        key=lambda x: x[1].created_at
    )

    to_remove = len(self._notifications) - MAX_NOTIFICATIONS
    for cid, _ in sorted_items[:to_remove]:
        del self._notifications[cid]
        if cid in self._dedup_cache:
            del self._dedup_cache[cid]
```

Llamar al final de `on_notification()`.

**Commit:** `fix(stability): Add automatic cleanup of old notifications`

### 3.3 Timeout en pyautogui

Agregar a `core/actions.py`:

```python
import pyautogui

# Configurar timeout global
pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = True

def _safe_press(self, key: str, timeout: float = 2.0):
    """Press con timeout."""
    try:
        pyautogui.press(key)
    except Exception as e:
        print(f"[Actions] Error pressing {key}: {e}")
```

**Commit:** `fix(stability): Add timeout handling to pyautogui actions`

---

## Fase 4: Mantenibilidad (12-16 horas)

### 4.1 Split main.py

Crear estructura:

```
main.py           # Entry point (~30 líneas)
cli.py            # Argparse (~80 líneas)
bootstrap.py      # Inicialización (~200 líneas)
commands_builtin.py  # Comandos built-in (~250 líneas)
```

**main.py después:**
```python
#!/usr/bin/env python3
"""VoiceFlow - Entry point."""

from cli import parse_args
from bootstrap import create_app

def main():
    args = parse_args()
    app = create_app(args)
    return app.run()

if __name__ == "__main__":
    main()
```

**Commit:** `refactor: Split main.py into cli, bootstrap, and commands modules`

### 4.2 Configurar pytest

1. Crear `tests/conftest.py`:
```python
import pytest
from core.state import StateMachine, State
from core.commands import CommandRegistry, Command

@pytest.fixture
def state_machine():
    return StateMachine()

@pytest.fixture
def registry():
    return CommandRegistry()
```

2. Crear `tests/test_commands.py`:
```python
def test_register_and_find(registry):
    cmd = Command(keywords=["test"], action=lambda: None)
    registry.register(cmd)
    result = registry.find_chain("test", State.IDLE)
    assert len(result) == 1

def test_find_with_alias(registry):
    cmd = Command(keywords=["enter", "aceptar"], action=lambda: None)
    registry.register(cmd)
    result = registry.find_chain("aceptar", State.IDLE)
    assert len(result) == 1
```

3. Crear `pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
```

**Commit:** `test: Add pytest configuration and basic command tests`

### 4.3 Logging Centralizado

Crear `core/log.py`:

```python
import logging
import sys

def setup_logging(level: str = "INFO"):
    """Configura logging centralizado."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="[%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"voiceflow.{name}")
```

Uso:
```python
from core.log import get_logger
logger = get_logger("notification_manager")
logger.info("Nueva notificación: %s", title)
```

**Commit:** `refactor: Add centralized logging system`

---

## Fase 5: Operaciones (4-6 horas)

### 5.1 Health Check Endpoint

Agregar a `core/event_server.py`:

```python
@app.get("/health/deep")
async def deep_health():
    """Health check detallado."""
    return {
        "status": "healthy",
        "uptime_seconds": time.time() - self._start_time,
        "components": {
            "event_server": "running",
            "notifications_pending": len([
                n for n in self._notifications.values()
                if n.get("status") == "pending"
            ]),
            "memory_mb": _get_memory_usage()
        }
    }

def _get_memory_usage():
    import psutil
    process = psutil.Process()
    return round(process.memory_info().rss / 1024 / 1024, 2)
```

**Commit:** `feat(ops): Add deep health check endpoint`

### 5.2 Validación de Config al Startup

Agregar a `config/settings.py`:

```python
def validate_config(config: dict) -> list:
    """Valida configuración y retorna lista de errores."""
    errors = []

    if config.get("engine") == "picovoice":
        if not config.get("picovoice", {}).get("access_key"):
            errors.append("Picovoice access_key requerida")

    if config.get("tailscale", {}).get("enabled"):
        if not config.get("tailscale", {}).get("bearer_token"):
            errors.append("Tailscale bearer_token requerido si enabled=true")

    return errors
```

**Commit:** `feat(ops): Add config validation on startup`

---

## Resumen de Commits

| Fase | Commits | Horas |
|------|---------|-------|
| 1. Limpieza | 1 | 2-4 |
| 2. Seguridad | 2 | 3-4 |
| 3. Estabilidad | 3 | 6-8 |
| 4. Mantenibilidad | 3 | 12-16 |
| 5. Operaciones | 2 | 4-6 |
| **Total** | **11** | **27-38** |

---

## Métricas de Éxito

| Métrica | Antes | Después |
|---------|-------|---------|
| Líneas en main.py | 600+ | <100 |
| Dead code | ~570 | 0 |
| Test coverage | 3% | 25% |
| Secrets hardcodeados | Sí | No |
| Health checks | No | Sí |

---

## Backlog Futuro (Post-Plan)

### Prioridad Alta
- [ ] Aumentar test coverage a 40%
- [ ] Type hints completos en core/
- [ ] CI/CD con GitHub Actions

### Prioridad Media
- [ ] Event bus para desacoplar componentes
- [ ] Plugin system para comandos
- [ ] OpenAPI docs para EventServer

### Prioridad Baja
- [ ] Separar UI de lógica en overlay
- [ ] Performance profiling
- [ ] Sphinx docs generados

---

## Cómo Usar Este Plan

1. **Ejecutar por fases** - No saltar fases
2. **Un commit por tarea** - Facilita rollback
3. **Probar después de cada fase** - `python main.py -d`
4. **Actualizar CHANGELOG** - Al final de cada fase
