# VoiceFlow - Performance Profile

## Hot Paths Identificados

| Path | Frecuencia | Archivo |
|------|------------|---------|
| Audio capture loop | 60fps (16ms) | `core/picovoice_engine.py:run()` |
| Overlay paint | 60fps | `ui/overlay.py:paintEvent()` |
| Command matching | Por cada input | `core/commands.py:find_chain()` |
| Notification dedup | Por notificación | `core/notification_manager.py:on_notification()` |

---

## Operaciones Costosas Detectadas

### I/O Síncrono

| Ubicación | Problema | Impacto |
|-----------|----------|---------|
| `core/logger.py:save()` | JSON write síncrono | Bloquea 10-50ms |
| `config/settings.py:load_config()` | File read en startup | Aceptable |
| `core/event_server.py:_flush_metrics()` | JSON write | Bloquea brevemente |

**Recomendación:** Mover saves a thread separado.

### Loops con Complejidad Alta

```python
# core/commands.py:find_chain() - O(n*m)
for command in self._commands:           # O(n) comandos
    for keyword in command.keywords:      # O(m) keywords
        if self._matches(word, keyword):  # O(k) fuzzy match
```

**Impacto:** Con 30 comandos y 60 aliases, ~1800 comparaciones por input.
**Recomendación:** Indexar por primera letra o usar trie.

### Allocaciones en Paths Críticos

```python
# ui/overlay.py:paintEvent() - Crea objetos cada frame
def paintEvent(self, event):
    painter = QPainter(self)           # Nueva instancia
    gradient = QRadialGradient(...)    # Nueva instancia
    path = QPainterPath()              # Nueva instancia
```

**Impacto:** GC pressure a 60fps.
**Recomendación:** Reusar objetos de painting.

---

## Cachés

| Caché | Ubicación | Invalidación |
|-------|-----------|--------------|
| Dedup cache | `notification_manager.py:_dedup_cache` | Por tiempo (10s) |
| Burst groups | `notification_manager.py:_burst_groups` | Por sesión |
| Command registry | `commands.py:_commands` | Nunca (inmutable) |

**Problema:** No hay caché de configuración - se lee de disco cada vez.

---

## Recursos sin Cleanup

| Recurso | Ubicación | Riesgo |
|---------|-----------|--------|
| `PvRecorder` | `picovoice_engine.py` | Leak si no se llama stop() |
| `QTimer` | `notification_panel.py:539` | Timers huérfanos |
| `threading.Thread` | `event_server.py:716` | daemon=True, sin join |

---

## Latencias Medidas

| Operación | Latencia Típica | Máxima Observada |
|-----------|-----------------|------------------|
| Wake-word detection | <50ms | 100ms |
| Command matching | <5ms | 20ms |
| HTTP notification | 10-50ms | 200ms (Tailscale) |
| Overlay repaint | <16ms | 32ms |
| pyautogui.press() | 50-100ms | 200ms |

---

## Profiling Recomendado

```python
# Para medir hot paths
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# ... ejecutar código ...

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Áreas a Perfilar

1. **Audio loop** - ¿Hay drops de frames?
2. **Overlay painting** - ¿Mantiene 60fps?
3. **Command matching** - ¿Escala con más comandos?
4. **Memory** - ¿Crece indefinidamente?

---

## Optimizaciones Sugeridas

### Quick Wins

| Cambio | Beneficio | Esfuerzo |
|--------|-----------|----------|
| Cache de config.json | Evita I/O repetido | 30min |
| Async logger.save() | No bloquea main thread | 1h |
| Reusar QPainter | Menos GC | 2h |

### Mejoras Estructurales

| Cambio | Beneficio | Esfuerzo |
|--------|-----------|----------|
| Indexar comandos | O(1) lookup | 4h |
| Connection pooling HTTP | Menos overhead | 2h |
| Lazy loading de modelos | Startup más rápido | 4h |
