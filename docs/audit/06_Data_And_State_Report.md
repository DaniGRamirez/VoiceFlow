# VoiceFlow - Data and State Report

## Fuentes de Datos

| Fuente | Tipo | Ubicación | Propósito |
|--------|------|-----------|-----------|
| config.json | Archivo JSON | Raíz | Configuración usuario |
| usage.json | Archivo JSON | logs/ | Historial sesiones |
| tailscale_metrics.json | Archivo JSON | logs/ | Métricas latencia |
| Claude transcripts | Archivos JSONL | ~/.claude/projects/ | Monitoreo Claude Code |
| Modelos Vosk/Picovoice | Binarios | models/ | ASR |

---

## Esquema de Datos

### config.json
```json
{
  "engine": "string",                    // Motor ASR
  "model_path": "string",                // Path modelo Vosk
  "dictation_mode": "winh|wispr",

  "picovoice": {
    "access_key": "string",              // API key (SENSIBLE)
    "sensitivity": "number (0-1)",
    "command_window": "number (segundos)"
  },

  "overlay": {
    "size": "number",
    "position": "[x, y]",
    "opacity": "number (0-1)"
  },

  "tailscale": {
    "enabled": "boolean",
    "bearer_token": "string",            // Token auth (SENSIBLE)
    "allowed_ips": "string[]"
  },

  "pushover": {
    "user_key": "string",                // (SENSIBLE)
    "api_token": "string"                // (SENSIBLE)
  }
}
```

### usage.json
```json
{
  "sessions": [
    {
      "id": "string (uuid)",
      "start": "ISO datetime",
      "end": "ISO datetime",
      "duration_seconds": "number",
      "commands": [
        {
          "time": "ISO datetime",
          "command": "string",
          "recognized": "string",
          "model": "string"
        }
      ],
      "ignored": ["string"],
      "active": "boolean"
    }
  ],
  "stats": {
    "total_sessions": "number",
    "total_commands": "number",
    "command_frequency": {"string": "number"},
    "ignored_frequency": {"string": "number"}
  }
}
```

### NotificationState (en memoria)
```python
@dataclass
class NotificationState:
    correlation_id: str
    data: dict
    status: str      # pending, completed, failed, burst_pending
    created_at: float
    executed_at: float
    intent: Optional[str]
    dedup_key: str
```

---

## Estado en Memoria

### StateMachine (Singleton implícito)
```python
# core/state.py
class StateMachine:
    state: State           # IDLE, DICTATING, PAUSED, PROCESSING
    _listeners: List       # Callbacks de cambio
```

**Quién lo muta:** main.py, engines, comandos
**Thread-safe:** No explícitamente

### CommandRegistry (Global)
```python
# core/commands.py
class CommandRegistry:
    _commands: List[Command]    # Inmutable después de init
```

**Quién lo muta:** Solo main.py en startup
**Thread-safe:** Sí (inmutable)

### NotificationManager
```python
# core/notification_manager.py
class NotificationManager:
    _notifications: Dict[str, NotificationState]
    _dedup_cache: Dict[str, tuple]
    _burst_groups: Dict[str, list]
```

**Quién lo muta:** EventServer callbacks, panel signals
**Thread-safe:** Usa QObject signals para thread safety

### EventServer
```python
# core/event_server.py
class EventServer:
    _notifications: Dict[str, dict]    # Copia de notificaciones
    _metrics: List[dict]               # Historial métricas
```

**Quién lo muta:** Endpoints HTTP
**Thread-safe:** FastAPI maneja concurrencia

---

## Persistencia

### Auto-Save

| Dato | Frecuencia | Trigger |
|------|------------|---------|
| usage.json | 60 segundos | Timer |
| usage.json | Inmediato | Comando ejecutado |
| tailscale_metrics.json | Cada 10 requests | Batch |

### Recuperación

```python
# config/settings.py:load_config()
# Si no existe config.json, usa default.json
# No hay migración de versiones
```

---

## Migraciones

**Estado:** No existen migraciones formales.

**Problema:** Si cambia el schema de config.json o usage.json, no hay upgrade path.

**Recomendación:**
```python
# Agregar versión al config
{
  "_version": "1.0.0",
  "engine": "..."
}

# Y migrador
def migrate_config(config: dict) -> dict:
    version = config.get("_version", "0.0.0")
    if version < "1.0.0":
        # aplicar migraciones
    return config
```

---

## Validación de Datos

| Punto | Validación | Ubicación |
|-------|------------|-----------|
| HTTP request body | Pydantic models | `event_server.py:39-96` |
| Config.json | Ninguna formal | `settings.py` |
| Comandos JSON | Schema parcial | `custom_commands.py` |
| usage.json | Ninguna | `logger.py` |

### Puntos de Corrupción Potencial

1. **config.json manual edit** - Usuario puede romper JSON
2. **usage.json crash** - Si crashea durante write, archivo corrupto
3. **transcripts Claude** - Formato puede cambiar sin aviso

---

## Flujo de Datos Principal

```
                    ┌──────────────┐
                    │  config.json │
                    └──────┬───────┘
                           │ load_config()
                           ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Micrófono  │────▶│   Engine     │────▶│   Estado    │
│   (Audio)   │     │   (ASR)      │     │  (Memory)   │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │   Commands   │
                                         │  (Registry)  │
                                         └──────┬───────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
             ┌──────────────┐           ┌──────────────┐           ┌──────────────┐
             │   Actions    │           │  usage.json  │           │   Overlay    │
             │  (Execute)   │           │   (Persist)  │           │    (UI)      │
             └──────────────┘           └──────────────┘           └──────────────┘
```

---

## Recomendaciones

1. **Agregar schema validation** a config.json con jsonschema
2. **Atomic writes** para evitar corrupción (write to temp, rename)
3. **Versionado de schemas** para migraciones futuras
4. **Backup automático** de usage.json antes de write
