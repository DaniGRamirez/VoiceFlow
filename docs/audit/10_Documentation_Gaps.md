# VoiceFlow - Documentation Gaps

## Estado Actual de Documentación

| Documento | Existe | Actualizado | Suficiente |
|-----------|--------|-------------|------------|
| README.md | ✅ | ✅ | ⚠️ Parcial |
| CLAUDE.md | ✅ | ✅ | ✅ Bueno |
| TAILSCALE_SETUP.md | ✅ | ✅ | ✅ Bueno |
| Docstrings | ⚠️ Parcial | - | ❌ Inconsistente |
| API docs | ❌ No | - | - |
| ADRs | ❌ No | - | - |
| Runbooks | ❌ No | - | - |

---

## README.md Analysis

### Lo que tiene
- Descripción general ✅
- Quick start ✅
- Comandos CLI ✅
- Arquitectura básica ✅

### Lo que falta
- Badges (CI, versión, license)
- GIF/screenshot del overlay en acción
- Tabla de comandos de voz completa
- Troubleshooting común
- Contributing guidelines
- Changelog

---

## CLAUDE.md Analysis

**Estado:** Excelente para su propósito.

Incluye:
- Comandos principales ✅
- Arquitectura de componentes ✅
- Data flow ✅
- Debug controls ✅
- Key files ✅

**Mejora sugerida:** Agregar sección de "Pitfalls comunes".

---

## Docstrings en Código

### Cobertura por Módulo

| Módulo | Funciones con Docstring | Total | % |
|--------|-------------------------|-------|---|
| core/state.py | 2/2 | 2 | 100% |
| core/commands.py | 6/8 | 8 | 75% |
| core/actions.py | 5/30+ | 30+ | ~15% |
| core/event_server.py | 10/15 | 15 | 67% |
| core/notification_manager.py | 12/15 | 15 | 80% |
| ui/overlay.py | 5/20 | 20 | 25% |

### Ejemplos de Buenos Docstrings

```python
# core/notification_manager.py
def on_notification(self, data: dict) -> bool:
    """
    Callback cuando llega una notificación del servidor.

    Args:
        data: Dict con datos de la notificación

    Returns:
        True si la notificación fue aceptada, False si era duplicada
    """
```

### Ejemplos de Docstrings Faltantes

```python
# core/actions.py
def on_enter(self):  # ❌ Sin docstring
    pyautogui.press('enter')

# Debería tener:
def on_enter(self) -> None:
    """Simula tecla Enter para confirmar acciones."""
    pyautogui.press('enter')
```

---

## APIs Internas No Documentadas

### EventServer Endpoints

| Endpoint | Documentado |
|----------|-------------|
| GET /health | ❌ Solo en código |
| POST /api/notification | ❌ Solo en código |
| POST /api/intent | ❌ Solo en código |
| POST /api/accept | ❌ Solo en código |
| POST /api/reject | ❌ Solo en código |
| POST /api/command | ❌ Solo en código |

**Necesita:** OpenAPI/Swagger docs o markdown manual.

### Command Registration API

```python
# No documentado cómo registrar comandos custom programáticamente
registry.register(Command(
    keywords=["mi_comando"],
    action=mi_funcion,
    allowed_states=[State.IDLE],
    sound="success"
))
```

---

## Decisiones de Diseño (ADRs Faltantes)

| Decisión | Documentada |
|----------|-------------|
| Por qué Picovoice sobre otras opciones | ❌ |
| Por qué PyQt6 sobre tkinter/electron | ❌ |
| Por qué Win+H para dictado | ❌ |
| Estrategia de deduplicación | ❌ |
| Formato de comandos JSON | ❌ |

### Template ADR Sugerido

```markdown
# ADR-001: Uso de Picovoice para Wake-Word

## Estado
Aceptado

## Contexto
Necesitamos wake-word detection en español con baja latencia.

## Decisión
Usar Picovoice Porcupine porque:
- Soporta español
- Wake-word custom ("Claudia")
- Baja latencia (<100ms)
- Funciona offline

## Consecuencias
- Requiere API key (costo)
- Modelo custom debe entrenarse online
```

---

## Runbooks Operacionales Faltantes

| Escenario | Runbook |
|-----------|---------|
| Micrófono no detectado | ❌ |
| Picovoice API key inválida | ❌ |
| Puerto 8765 ocupado | ❌ |
| Overlay no visible | ❌ |
| Claude Code no recibe notificaciones | ❌ |
| Tailscale no conecta | ⚠️ TAILSCALE_SETUP.md |

---

## Documentación Prioritaria a Crear

### Alta Prioridad

1. **API.md** - Documentación de endpoints HTTP
```markdown
# VoiceFlow HTTP API

## Base URL
http://localhost:8765

## Endpoints

### POST /api/notification
Crea una notificación en el panel.

**Body:**
{
  "title": "string",
  "body": "string",
  "actions": [...]
}

**Response:**
{
  "success": true,
  "correlation_id": "uuid"
}
```

2. **COMMANDS.md** - Lista completa de comandos de voz
```markdown
# Comandos de Voz

## Navegación
| Comando | Aliases | Acción |
|---------|---------|--------|
| enter | aceptar, ok, dale | Presiona Enter |
| escape | cancelar, salir | Presiona Escape |
```

3. **TROUBLESHOOTING.md** - Problemas comunes

### Media Prioridad

4. **CONTRIBUTING.md** - Guía para contribuidores
5. **ADRs/** - Decisiones arquitectónicas
6. **CHANGELOG.md** - Historial de cambios

### Baja Prioridad

7. **Sphinx/MkDocs** - Documentación generada de código
8. **Diagrams as code** - Mermaid en markdown

---

## Comentarios en Código

### Útiles (Mantener)

```python
# core/notification_manager.py:174
# Detectar ráfaga: si llega dentro de BURST_WINDOW_MS de la anterior
# y es de la misma sesión, agrupar
```

### Ruido (Eliminar)

```python
# TODO: refactorizar esto
# FIXME: esto está mal
# NOTE: no sé por qué funciona
```

### Obvios (Eliminar)

```python
# Incrementar contador
counter += 1

# Retornar resultado
return result
```

---

## Plan de Documentación

### Semana 1
- [ ] Crear API.md con todos los endpoints
- [ ] Crear COMMANDS.md con tabla de comandos
- [ ] Agregar badges a README

### Semana 2
- [ ] Crear TROUBLESHOOTING.md
- [ ] Agregar docstrings a core/actions.py
- [ ] Crear ADR-001 (Picovoice)

### Semana 3
- [ ] Crear CONTRIBUTING.md
- [ ] Agregar GIF demo a README
- [ ] Documentar JSON command format

### Semana 4
- [ ] CHANGELOG.md
- [ ] Runbooks básicos
- [ ] Revisar y limpiar comentarios
