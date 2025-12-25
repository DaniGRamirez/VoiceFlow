# VoiceFlow - Codebase Walkthrough

## Estructura General

```
VoiceFlow/
├── main.py              # Entry point
├── core/                # Lógica de negocio
├── ui/                  # Interfaz PyQt6
├── config/              # Configuración
├── audio/               # Feedback sonoro
├── models/              # Modelos de IA (Vosk, Picovoice)
├── claude-pty-wrapper/  # Wrapper Node.js
├── docs/                # Documentación
├── logs/                # Runtime data
├── scripts/             # Utilidades
└── .claude/             # Hooks Claude Code
```

---

## `/core` - Módulo Principal

**Propósito:** Toda la lógica de negocio del sistema.

### Archivos Críticos

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `state.py` | 28 | Máquina de estados (State enum + StateMachine) |
| `commands.py` | 334 | Command class + CommandRegistry |
| `actions.py` | 500+ | Todas las acciones pyautogui |
| `picovoice_engine.py` | 376 | Motor wake-word Picovoice |
| `event_server.py` | 800+ | Servidor HTTP FastAPI |
| `notification_manager.py` | 477 | Orquestación de notificaciones |
| `transcript_watcher.py` | 334 | Monitor transcripts Claude Code |

### Entry Points del Módulo

- `picovoice_engine.PicovoiceHybridEngine` - Motor principal
- `commands.CommandRegistry` - Registro de comandos
- `actions.Actions` - Ejecutor de acciones
- `event_server.EventServer` - Servidor HTTP
- `notification_manager.NotificationManager` - Gestor notificaciones

### Archivos que NO Deberían Estar

| Archivo | Razón |
|---------|-------|
| `skill_*.py` (5 archivos) | Sistema de skills incompleto/experimental |
| `permission_store.py` | No se usa actualmente |

### Convenciones de Nombrado

- Clases: `PascalCase` (ej: `CommandRegistry`, `StateMachine`)
- Funciones: `snake_case` (ej: `find_chain`, `on_enter`)
- Constantes: `UPPER_SNAKE` (ej: `DEDUP_WINDOW_SECONDS`)
- Archivos: `snake_case.py`
- **Consistente:** Sí

---

## `/ui` - Interfaz de Usuario

**Propósito:** Overlay animado y panel de notificaciones PyQt6.

### Archivos Críticos

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `overlay.py` | 854 | Widget principal overlay |
| `overlay_renderer.py` | 502 | Rendering de formas (barras, círculos) |
| `overlay_animator.py` | 151 | Sistema de animación (Spore, Transition) |
| `overlay_debug.py` | 432 | Controles de debug (keyboard) |
| `notification_panel.py` | 641 | Panel flotante notificaciones |
| `capture_overlay.py` | 242 | Campo de captura Win+H |
| `easing.py` | 248 | Funciones de interpolación |

### Entry Points

- `overlay.Overlay` - Widget principal
- `notification_panel.NotificationPanel` - Panel notificaciones
- `capture_overlay.CaptureManager` - Gestor de captura

### Archivos que NO Deberían Estar

| Archivo | Razón |
|---------|-------|
| `ui_Merged.txt` | Archivo temporal de merge |
| `nul` | Archivo especial Windows creado por error |

---

## `/config` - Configuración

**Propósito:** Settings, aliases y comandos custom.

### Archivos Críticos

| Archivo | Propósito |
|---------|-----------|
| `settings.py` | Cargador de config.json |
| `aliases.py` | Sinónimos de comandos (60+ aliases) |
| `default.json` | Configuración por defecto |

### Subcarpetas

#### `/config/commands/`
Comandos custom en formato JSON.

| Archivo | Comandos | Propósito |
|---------|----------|-----------|
| `ejemplo.json` | 16 | Plantilla con ejemplos |
| `adapta.json` | 1 | Comando /adapta |
| `plan.json` | 1 | Comando /plan |
| `mute.json` | 2 | Control de audio |

#### `/config/prompts/`
Plantillas para comandos con prompts.

| Archivo | Propósito |
|---------|-----------|
| `adapta.json` | Prompt para adaptar planes |
| `plan.json` | Prompt para planificación |
| `resumen.json` | Prompt para resúmenes |

---

## `/audio` - Feedback Sonoro

**Propósito:** Reproducción de sonidos de feedback.

### Archivos

| Archivo | Propósito |
|---------|-----------|
| `feedback.py` | SoundPlayer class |
| `sounds/click.wav` | Click de activación |
| `sounds/ding.wav` | Notificación |
| `sounds/error.wav` | Error |
| `sounds/pop.wav` | Pop genérico |
| `sounds/success.wav` | Éxito |

---

## `/models` - Modelos de IA

**Propósito:** Modelos de reconocimiento de voz.

### Archivos

| Archivo/Carpeta | Tamaño | Propósito |
|-----------------|--------|-----------|
| `vosk-model-small-es-0.42/` | 45 MB | Modelo Vosk pequeño |
| `vosk-model-es-0.42/` | 1.1 GB | Modelo Vosk grande |
| `Claudia_es_windows_v4_0_0.ppn` | 3 KB | Wake-word Picovoice |
| `porcupine_params_es.pv` | 1 MB | Parámetros Picovoice español |

**Nota:** Estos archivos están en `.gitignore` por tamaño.

---

## `/claude-pty-wrapper` - Wrapper Node.js

**Propósito:** Wrapper PTY para Claude Code con integración VoiceFlow.

### Estructura

```
claude-pty-wrapper/
├── src/
│   ├── index.ts           # Entry point
│   ├── pty/               # Pseudoterminal
│   ├── session/           # Correlación sesiones
│   ├── transcript/        # Parser transcripts
│   └── voiceflow/         # Cliente HTTP
├── test/                  # Jest tests
├── dist/                  # Compilado JS
└── shim/                  # Windows CLI shim
```

### Archivos Críticos

| Archivo | Propósito |
|---------|-----------|
| `src/index.ts` | Entry point, CLI |
| `src/transcript/parser.ts` | Parser de transcripts Claude |
| `src/voiceflow/client.ts` | Cliente HTTP a VoiceFlow |

---

## `/.claude` - Hooks Claude Code

**Propósito:** Hooks para integración con Claude Code.

### Estructura

```
.claude/
├── hooks/
│   ├── permission_request_hook.py  # Hook principal permisos
│   ├── pre_tool_notification.py    # Pre-tool notification
│   └── notification_hook.py        # Notificaciones genéricas
├── skills/
│   ├── analyze-voice-patterns.md
│   ├── generate-docs.md
│   └── setup-command.md
└── settings.local.json             # Configuración local
```

### Archivos Críticos

| Archivo | Propósito |
|---------|-----------|
| `hooks/permission_request_hook.py` | Intercepta permisos y envía a VoiceFlow |

---

## `/scripts` - Utilidades

**Propósito:** Scripts de utilidad y testing.

| Archivo | Propósito |
|---------|-----------|
| `claude_hook.py` | Hook para Claude Code (legacy) |
| `test_dedup.py` | Test de deduplicación |
| `test_dedup_unit.py` | Test unitario deduplicación |
| `test_tailscale.py` | Test conectividad Tailscale |

---

## `/logs` - Runtime Data

**Propósito:** Datos de runtime y métricas.

| Archivo | Propósito |
|---------|-----------|
| `usage.json` | Historial de comandos y sesiones |
| `tailscale_metrics.json` | Métricas de latencia remota |
| `hook_debug.log` | Debug de hooks (temporal) |

---

## Archivos Raíz

| Archivo | Propósito |
|---------|-----------|
| `main.py` | Entry point principal |
| `README.md` | Documentación usuario |
| `CLAUDE.md` | Instrucciones para Claude Code |
| `requirements.txt` | Dependencias Python base |
| `requirements-picovoice.txt` | Dependencias Picovoice |
| `config.json` | Configuración usuario (no en git) |
| `.gitignore` | Exclusiones Git |

---

## Navegación Rápida por Tipo de Tarea

### "Quiero agregar un nuevo comando de voz"
1. Agregar alias en `config/aliases.py`
2. Crear handler en `core/actions.py`
3. Registrar en `main.py` (sección de comandos)

### "Quiero modificar el overlay visual"
1. Estados/transiciones: `ui/overlay.py`
2. Rendering de formas: `ui/overlay_renderer.py`
3. Animaciones: `ui/overlay_animator.py`
4. Debug: `ui/overlay_debug.py`

### "Quiero cambiar cómo funcionan las notificaciones"
1. Recepción HTTP: `core/event_server.py`
2. Lógica de dedup/grouping: `core/notification_manager.py`
3. UI del panel: `ui/notification_panel.py`
4. Hook de Claude: `.claude/hooks/permission_request_hook.py`

### "Quiero agregar un nuevo motor de reconocimiento"
1. Crear `core/mi_engine.py` implementando interfaz similar
2. Agregar opción en `main.py` (argparse + inicialización)
3. Actualizar `CLAUDE.md` documentación

### "Quiero cambiar configuración por defecto"
1. Defaults: `config/default.json`
2. Cargador: `config/settings.py`
3. Documentar en `CLAUDE.md`
