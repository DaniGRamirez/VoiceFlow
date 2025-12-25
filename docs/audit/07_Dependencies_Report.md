# VoiceFlow - Dependencies Report

## Python Dependencies (requirements.txt)

| Dependencia | Versión | Propósito | Estado |
|-------------|---------|-----------|--------|
| vosk | >=0.3.45 | ASR continuo | ✅ Activo |
| sounddevice | >=0.4.6 | Captura audio | ✅ Activo |
| pyautogui | >=0.9.54 | Automatización | ✅ Activo |
| pyperclip | >=1.8.2 | Clipboard | ✅ Activo |
| pygame | >=2.5.0 | Audio playback | ✅ Activo |
| pygetwindow | >=0.0.9 | Window management | ✅ Activo |
| playwright | >=1.40.0 | Browser automation | ✅ Activo |
| fastapi | >=0.109.0 | HTTP API | ✅ Activo |
| uvicorn | >=0.27.0 | ASGI server | ✅ Activo |
| PyQt6 | (implícito) | UI framework | ✅ Activo |
| requests | (implícito) | HTTP client | ✅ Activo |

## Picovoice Dependencies (requirements-picovoice.txt)

| Dependencia | Versión | Propósito | Estado |
|-------------|---------|-----------|--------|
| pvporcupine | >=3.0.0 | Wake-word detection | ✅ Activo |
| pvrecorder | >=1.2.0 | Audio recording | ✅ Activo |

---

## Análisis de Dependencias

### Desactualizadas (Major Versions Atrás)

| Dependencia | Actual | Última | Riesgo |
|-------------|--------|--------|--------|
| playwright | 1.40.0 | 1.48.0+ | Bajo - breaking changes menores |

**Nota:** La mayoría usa `>=`, así que se instala la última compatible.

### Vulnerabilidades Conocidas

```bash
# Ejecutar para verificar:
pip-audit
```

**Estado actual:** No evaluado automáticamente. Recomiendo agregar `pip-audit` a CI.

### Dependencias Abandonadas

| Dependencia | Último Commit | Estado |
|-------------|---------------|--------|
| pygetwindow | 2023 | ⚠️ Mantenimiento mínimo |

**Alternativa:** `pywin32` para Windows-specific window management.

### Dependencias Duplicadas/Redundantes

| Redundancia | Descripción |
|-------------|-------------|
| sounddevice + pvrecorder | Ambos capturan audio |
| pygame + sounddevice | pygame también puede capturar |

**Justificación:** pvrecorder es específico para Picovoice, pygame es para playback.

---

## Node.js Dependencies (claude-pty-wrapper)

### Production

| Dependencia | Versión | Propósito |
|-------------|---------|-----------|
| axios | ^1.6.0 | HTTP client |
| chokidar | ^3.5.3 | File watcher |
| commander | ^11.0.0 | CLI framework |
| uuid | ^9.0.0 | UUID generation |

### Development

| Dependencia | Versión | Propósito |
|-------------|---------|-----------|
| typescript | ^5.0.0 | Language |
| @types/node | ^20.0.0 | Type definitions |
| jest | ^29.0.0 | Testing |
| ts-node | ^10.9.0 | TS execution |

---

## Código Vendorizado

| Item | Ubicación | Razón |
|------|-----------|-------|
| Modelos Vosk | models/ | Tamaño (1GB+), no en npm/pip |
| Wake-word Picovoice | models/*.ppn | Modelo custom entrenado |

---

## Lock Files

| Archivo | Existe | Commiteado |
|---------|--------|------------|
| requirements.txt | Sí | Sí (sin hashes) |
| package-lock.json | Sí | Sí |

**Problema:** `requirements.txt` usa `>=` en lugar de versiones exactas.

**Recomendación:**
```bash
# Generar requirements con versiones exactas
pip freeze > requirements.lock.txt
```

---

## Dependencias Transitivas de Alto Riesgo

```bash
# Vosk trae:
numpy       # Computación numérica
cffi        # C bindings

# PyQt6 trae:
PyQt6-sip   # SIP bindings
PyQt6-Qt6   # Qt libraries (grande)

# Playwright trae:
greenlet    # Coroutines
pyee        # Event emitter
```

---

## Tamaño de Dependencias

| Grupo | Tamaño Instalado |
|-------|------------------|
| PyQt6 + Qt | ~150 MB |
| Vosk + modelos | ~1.2 GB |
| Playwright + browsers | ~500 MB |
| Picovoice | ~50 MB |
| Resto | ~100 MB |
| **Total** | **~2 GB** |

---

## Recomendaciones

### Corto Plazo

1. **Agregar pip-audit** a CI para detectar vulnerabilidades
2. **Crear requirements.lock.txt** con versiones exactas
3. **Documentar** versiones mínimas de Python (3.10+)

### Mediano Plazo

1. **Evaluar alternativa a pygetwindow** (bajo mantenimiento)
2. **Unificar captura de audio** (elegir sounddevice o pvrecorder)
3. **Lazy loading de Playwright** (no todos lo usan)

### Largo Plazo

1. **Dependabot** para updates automáticos
2. **Reducir tamaño** con modelos Vosk small por defecto
3. **Opcional: Poetry** para mejor gestión de deps

---

## Comandos Útiles

```bash
# Ver árbol de dependencias
pip show <package> | grep Requires

# Verificar vulnerabilidades
pip-audit

# Ver outdated
pip list --outdated

# Generar lock
pip freeze > requirements.lock.txt

# Node.js
npm audit
npm outdated
```
