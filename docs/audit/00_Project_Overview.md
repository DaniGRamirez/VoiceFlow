# VoiceFlow - Project Overview

## Qué Problema Resuelve

VoiceFlow es un sistema de control por voz para Windows que permite interacción hands-free con VSCode y Claude Code. Elimina la necesidad de usar teclado/mouse para tareas repetitivas de desarrollo, permitiendo dictar código, ejecutar comandos y aprobar permisos de Claude Code mediante voz o control remoto desde iPhone.

## Público Objetivo

- Desarrolladores que usan Claude Code y quieren aprobar permisos sin tocar el teclado
- Usuarios con movilidad reducida que necesitan alternativas al mouse/teclado
- Developers que quieren experimentar con interfaces de voz para coding

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| UI | PyQt6 (overlay animado, panel notificaciones) |
| ASR | Vosk (continuo) + Picovoice Porcupine (wake-word) |
| Automatización | pyautogui + Playwright |
| Audio | sounddevice + pygame |
| API | FastAPI + Uvicorn (puerto 8765) |
| Remoto | Tailscale + Pushover |
| CLI Wrapper | Node.js + TypeScript |

## Flujo General de Uso

```
1. Usuario dice "Claudia" (wake-word)
2. Sistema activa Win+H para dictado
3. Usuario dicta comando o texto
4. Sistema ejecuta acción (hotkey, tipo texto, shell, etc.)
5. Si Claude Code pide permiso → notificación en overlay
6. Usuario dice "Aceptar" o toca botón en iPhone
```

## Mapa de Módulos

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                               │
│                    (Entry Point + Wiring)                    │
└─────────────────────────────────────────────────────────────┘
            │
    ┌───────┴───────┬───────────────┬──────────────┐
    ▼               ▼               ▼              ▼
┌────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐
│ core/  │    │   ui/    │    │ config/ │    │  audio/  │
│        │    │          │    │         │    │          │
│ State  │    │ Overlay  │    │ Settings│    │ Sounds   │
│ Command│    │ Panel    │    │ Aliases │    │ Feedback │
│ Actions│    │ Capture  │    │ Custom  │    │          │
│ Server │    │ Animator │    │ Commands│    │          │
│ Engine │    │          │    │         │    │          │
└────────┘    └──────────┘    └─────────┘    └──────────┘
```

## Qué Hace Único al Sistema

1. **Wake-word en español** - "Claudia" entrenado con Picovoice para español
2. **Integración Claude Code** - Hooks que interceptan permisos y los muestran en overlay
3. **Control remoto iOS** - Aprobar/rechazar desde iPhone via Tailscale + Shortcuts
4. **Deduplicación inteligente** - Agrupa ráfagas de notificaciones de Claude
5. **Overlay no intrusivo** - Siempre visible pero no interfiere con trabajo

## Dependencias Externas Críticas

| Dependencia | Propósito | Criticidad |
|-------------|-----------|------------|
| Picovoice | Wake-word detection | Alta (requiere API key) |
| Vosk | ASR continuo | Media (backup) |
| pyautogui | Automatización | Alta (core) |
| FastAPI | Servidor HTTP | Alta (notificaciones) |
| PyQt6 | UI | Alta (overlay) |
| Tailscale | Acceso remoto | Baja (opcional) |
| Pushover | Push notifications | Baja (opcional) |

## Métricas del Proyecto

- **~8,000 líneas Python** en core + ui + config
- **~1,500 líneas TypeScript** en claude-pty-wrapper
- **30+ comandos built-in** + custom JSON
- **4 motores de reconocimiento** intercambiables
- **Puerto 8765** para API HTTP
