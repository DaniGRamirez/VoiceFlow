# VoiceFlow - Refactor Opportunities

## Quick Wins (≤2h cada uno)

| Cambio | Archivo(s) | Beneficio | Riesgo |
|--------|------------|-----------|--------|
| Eliminar archivos skill_*.py no usados | `core/skill_*.py` | -500 líneas, menos confusión | Ninguno |
| Eliminar archivos basura (nul, del) | Varios | Repo más limpio | Ninguno |
| Agregar type hints a state.py | `core/state.py` | Mejor IDE support | Ninguno |
| Mover constantes a constants.py | `core/notification_manager.py` | Configuración centralizada | Bajo |
| Extraer HTTP client común | Hooks + pushover | Menos duplicación | Bajo |
| Configurar logging centralizado | Nuevo `core/log.py` | Debug más fácil | Bajo |

---

## Refactors Medianos (1-2 días)

| Cambio | Módulo | Beneficio | Dependencias | Riesgo |
|--------|--------|-----------|--------------|--------|
| Split main.py en módulos | `main.py` | Más mantenible, testeable | cli.py, bootstrap.py | Medio |
| Abstraer Actions comunes | `core/actions.py` | Menos duplicación | Ninguna | Bajo |
| Unificar logging | Todo | Consistencia | logging module | Bajo |
| Agregar pytest + fixtures | Nuevo `tests/` | Regresiones detectadas | pytest | Bajo |
| Type hints en commands.py | `core/commands.py` | Mejor tooling | mypy | Bajo |

### Detalle: Split main.py

**Problema actual:**
```python
# main.py - 600+ líneas con todo mezclado
def main():
    # Parse args (50 líneas)
    # Load config (30 líneas)
    # Init engines (100 líneas)
    # Register 30+ commands (200 líneas)
    # Setup UI (50 líneas)
    # Setup server (50 líneas)
    # Main loop (50 líneas)
```

**Propuesta:**
```
main.py              # Entry point mínimo (30 líneas)
cli.py               # Argparse
bootstrap.py         # Inicialización de componentes
commands_builtin.py  # Registro de comandos built-in
```

---

## Cambios Estructurales (Requieren Planificación)

### 1. Separar UI de Lógica

**Descripción:** Actualmente overlay.py mezcla rendering con lógica de estado.

**Por qué es necesario:**
- Testing de UI es imposible sin mocks complejos
- Cambios visuales afectan lógica y viceversa

**Qué se rompe durante transición:**
- Referencias directas entre Overlay y StateMachine
- Callbacks que asumen acceso a ambos

**Estrategia sugerida:**
1. Crear `OverlayViewModel` con solo datos
2. Mover lógica de animación a AnimationController
3. Overlay solo renderiza ViewModel
4. Conectar via signals

**Esfuerzo:** 2-3 días

---

### 2. Event Bus Centralizado

**Descripción:** Reemplazar callbacks directos por event bus.

**Por qué es necesario:**
- Callbacks crean acoplamiento fuerte
- Difícil agregar nuevos listeners
- Testing requiere mock de toda la cadena

**Qué se rompe:**
- Todas las conexiones de callbacks
- Orden de ejecución puede cambiar

**Estrategia:**
```python
# Nuevo: core/events.py
class EventBus:
    def emit(self, event: str, data: Any): ...
    def on(self, event: str, handler: Callable): ...

# Uso
bus.emit("command.executed", {"command": "enter"})
bus.on("command.executed", logger.log_command)
```

**Esfuerzo:** 3-4 días

---

### 3. Plugin System para Commands

**Descripción:** Hacer que comandos sean plugins cargables.

**Por qué es necesario:**
- Agregar comandos requiere modificar main.py
- No hay forma de desactivar comandos individuales
- Usuarios no pueden agregar comandos sin código

**Estrategia:**
```python
# config/commands/enter.py
class EnterCommand(CommandPlugin):
    name = "enter"
    keywords = ["enter", "aceptar"]

    def execute(self, context):
        pyautogui.press('enter')

# Auto-discovery
for plugin in load_plugins("config/commands/*.py"):
    registry.register(plugin)
```

**Esfuerzo:** 1 semana

---

## Refactors NO Recomendados

| Cambio | Razón para NO hacerlo |
|--------|----------------------|
| Reescribir en TypeScript | Proyecto funciona, no hay beneficio claro |
| Migrar de PyQt6 a Electron | Complejidad sin beneficio |
| Usar async/await everywhere | Overhead no justificado para el uso actual |
| Microservicios | Over-engineering para proyecto personal |

---

## Orden Recomendado

### Fase 1 - Limpieza (1 semana)

```
Día 1-2: Quick wins (eliminar dead code, archivos basura)
Día 3-4: Configurar pytest básico
Día 5: Type hints en core/state.py y core/commands.py
```

### Fase 2 - Estructura (2 semanas)

```
Semana 1: Split main.py en módulos
Semana 2: Abstraer Actions + unificar logging
```

### Fase 3 - Arquitectura (Si es necesario)

```
Solo si el proyecto crece significativamente:
- Event bus
- Plugin system
- UI/Logic separation
```

---

## Métricas de Éxito

| Métrica | Actual | Objetivo |
|---------|--------|----------|
| Líneas en main.py | 600+ | <100 |
| Test coverage | ~3% | 40% |
| Type coverage | ~20% | 60% |
| Dead code | ~570 líneas | 0 |
| Tiempo de onboarding | 1 día | 2 horas |

---

## Riesgos de Refactoring

| Riesgo | Mitigación |
|--------|------------|
| Romper funcionalidad existente | Tests antes de refactor |
| Over-engineering | Solo refactorizar lo que duele |
| Scope creep | Definir límites claros |
| Regresiones | CI con tests automáticos |
