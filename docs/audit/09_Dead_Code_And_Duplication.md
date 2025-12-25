# VoiceFlow - Dead Code and Duplication Report

## Archivos No Referenciados

| Archivo | Razón | Acción |
|---------|-------|--------|
| `core/skill_registry.py` | Sistema de skills no integrado | Eliminar o integrar |
| `core/skill_dispatcher.py` | No usado | Eliminar |
| `core/skill_handlers.py` | No usado | Eliminar |
| `core/skill_integration.py` | No usado | Eliminar |
| `core/permission_store.py` | No importado en ningún lado | Eliminar |
| `ui/ui_Merged.txt` | Archivo temporal de merge | Eliminar |
| `claude-pty-wrapper/del` | Archivo basura | Eliminar |

---

## Funciones/Clases Exportadas No Usadas

| Item | Ubicación | Notas |
|------|-----------|-------|
| `OpenWakeWordEngine` | `core/oww_engine.py` | Solo referenciado en main.py si engine="oww" |
| `HybridEngine` | `core/hybrid_engine.py` | Solo referenciado si engine="hybrid" |
| `BrowserManager` | `core/browser/browser_manager.py` | Parcialmente usado |

**Nota:** Los engines alternativos están correctamente diseñados como opcionales.

---

## Feature Flags / Código Behind Flags

| Flag | Ubicación | Estado |
|------|-----------|--------|
| `custom_commands.enabled` | config.json | ✅ Activo |
| `allow_dangerous_actions` | config.json | ✅ Activo (false por defecto) |
| `transcript_watcher.enabled` | config.json | ✅ Activo |
| `tailscale.enabled` | config.json | ✅ Activo |
| `pushover.enabled` | config.json | ✅ Activo |

**Evaluación:** Todos los flags están en uso y bien implementados.

---

## Código Comentado

### Encontrado

| Archivo | Línea | Contenido |
|---------|-------|-----------|
| `core/picovoice_engine.py` | ~150 | `# print(f"Wake word detected!")` |
| `ui/overlay.py` | ~300 | Bloque de debug comentado |
| `core/actions.py` | ~200 | `# time.sleep(0.1)  # old delay` |

**Acción:** Eliminar código comentado. Si es necesario, está en git history.

---

## Sistemas Duplicados

### 1. Captura de Audio

| Sistema | Archivo | Uso |
|---------|---------|-----|
| sounddevice | `core/engine.py` | Motor Vosk |
| pvrecorder | `core/picovoice_engine.py` | Motor Picovoice |

**Evaluación:** Justificado - pvrecorder es requerido por Picovoice.

### 2. HTTP Clients

| Sistema | Archivo | Uso |
|---------|---------|-----|
| urllib.request | `.claude/hooks/*.py` | Hooks Claude |
| requests | `core/pushover_client.py` | Pushover API |
| httpx (implícito via FastAPI) | `core/event_server.py` | Server |

**Recomendación:** Unificar en `requests` o `httpx`.

### 3. Logging

| Sistema | Archivo | Uso |
|---------|---------|-----|
| print() | Todo el código | Debug |
| logging module | `core/event_server.py` | Tailscale logs |
| UsageLogger | `core/logger.py` | Sesiones |

**Recomendación:** Unificar en `logging` module con configuración centralizada.

---

## Copy-Paste Detectado

### Patrón 1: Manejo de Hotkeys

```python
# core/actions.py - Repetido ~10 veces
def on_X(self):
    pyautogui.press('X')

# Podría abstraerse:
def _press_key(self, key: str):
    pyautogui.press(key)
```

### Patrón 2: Callback de Notificación

```python
# Repetido en event_server.py y notification_manager.py
if self.sounds:
    try:
        self.sounds.play("success")
    except Exception:
        pass
```

### Patrón 3: Thread-Safe Signal Emit

```python
# ui/notification_panel.py - Patrón repetido
def add_notification(self, data):
    self._add_notification_signal.emit(data)

def _do_add_notification(self, data):
    # actual logic
```

**Recomendación:** Crear decorador o mixin para thread-safety.

---

## Imports No Usados

```bash
# Verificar con:
flake8 --select=F401 core/ ui/
```

**Ejemplos detectados manualmente:**

| Archivo | Import |
|---------|--------|
| `core/event_server.py` | `from typing import Any` (posiblemente no usado) |
| `ui/overlay.py` | Algunos imports de PyQt6 |

---

## Archivos Temporales en Git

| Archivo | Razón |
|---------|-------|
| `nul` | Windows special file |
| `ui/nul` | Windows special file |
| `claude-pty-wrapper/del` | Archivo residual |
| Archivos con encoding raro | `c︀Users...` en git status |

---

## Recomendaciones

### Inmediato (30 min)

```bash
# Eliminar archivos muertos
rm -f nul ui/nul claude-pty-wrapper/del
rm -f ui/ui_Merged.txt

# Eliminar sistema de skills no usado
rm -f core/skill_*.py core/permission_store.py
```

### Corto Plazo (2h)

1. Eliminar código comentado (buscar `# ` seguido de código)
2. Unificar HTTP clients en `requests`
3. Configurar `logging` centralizado

### Mediano Plazo (1 día)

1. Abstraer patrones repetidos de Actions
2. Crear mixin para thread-safe signals
3. Ejecutar flake8 y limpiar imports

---

## Métricas de Código Muerto

| Categoría | Líneas Estimadas |
|-----------|------------------|
| Archivos no usados (skill_*) | ~500 |
| Código comentado | ~50 |
| Imports no usados | ~20 |
| **Total recuperable** | **~570 líneas** |

Esto representa aproximadamente **7% del código Python** que puede eliminarse.
