# VoiceFlow - Onboarding Guide

## Objetivo

Que un desarrollador nuevo sea productivo en menos de 1 día.

---

## 1. Prerrequisitos

### Software Requerido

| Software | Versión | Verificar |
|----------|---------|-----------|
| Windows | 10/11 | - |
| Python | 3.10+ | `python --version` |
| Git | 2.x | `git --version` |
| VSCode | Latest | Para usar Claude Code |

### Opcional

| Software | Propósito |
|----------|-----------|
| Node.js 18+ | Para claude-pty-wrapper |
| Picovoice Account | Para wake-word (gratis tier disponible) |

### Accesos Requeridos

- [ ] Clonar el repositorio (GitHub)
- [ ] API key de Picovoice (https://console.picovoice.ai/)
- [ ] (Opcional) Tailscale si usas remoto
- [ ] (Opcional) Pushover si quieres push notifications

---

## 2. Setup Inicial

### Clonar Repositorio

```bash
git clone https://github.com/DaniGRamirez/VoiceFlow.git
cd VoiceFlow
```

### Crear Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
```

### Instalar Dependencias Base

```bash
pip install -r requirements.txt
```

### Instalar Picovoice (Recomendado)

```bash
pip install -r requirements-picovoice.txt
```

### Descargar Modelos Vosk

```bash
# Modelo pequeño (45MB) - Recomendado para empezar
# Descargar de: https://alphacephei.com/vosk/models
# Extraer en: models/vosk-model-small-es-0.42/

# Modelo grande (1.1GB) - Mejor precisión
# models/vosk-model-es-0.42/
```

### Configurar Picovoice

1. Ir a https://console.picovoice.ai/
2. Crear cuenta (gratis)
3. Copiar Access Key
4. Ejecutar VoiceFlow una vez para crear config.json
5. Editar config.json y agregar access_key

```json
{
  "picovoice": {
    "access_key": "TU_ACCESS_KEY_AQUI"
  }
}
```

---

## 3. Ejecutar el Proyecto

### Modo Básico (Picovoice)

```bash
python main.py -e picovoice
```

Deberías ver:
- Overlay blanco animado en esquina de pantalla
- Mensaje en consola: "VoiceFlow iniciado"
- Di "Claudia" para activar

### Modo Debug (Sin reconocimiento)

```bash
python main.py -d
```

Usa teclas numéricas para simular estados:
- `1` - Activar listening
- `2` - Desactivar
- `3` - Simular DICTATING
- `4` - Volver a IDLE
- `Space` - Escribir comando manualmente

### Modo Vosk (ASR continuo)

```bash
python main.py -e vosk -m small
```

---

## 4. Ejecutar Tests

### Tests Unitarios

```bash
python scripts/test_dedup_unit.py
```

### Tests de Integración (requiere VoiceFlow corriendo)

```bash
# En terminal 1:
python main.py -d

# En terminal 2:
python scripts/test_dedup.py
```

---

## 5. Hacer un Cambio Trivial

### Agregar un nuevo alias de comando

1. Abrir `config/aliases.py`
2. Agregar alias a un comando existente:

```python
# Antes
ENTER_ALIASES = ["aceptar", "confirmar", "dale", "ok"]

# Después
ENTER_ALIASES = ["aceptar", "confirmar", "dale", "ok", "listo"]
```

3. Reiniciar VoiceFlow
4. Probar diciendo "listo" - debería ejecutar Enter

### Verificar que funciona

```bash
# Ejecutar en modo debug
python main.py -d

# Presionar Space, escribir "listo", Enter
# Debería aparecer en consola: "Ejecutando: enter"
```

---

## 6. Estructura Mental del Proyecto

### ¿Qué tocar según el tipo de tarea?

| Tarea | Archivos |
|-------|----------|
| Agregar comando de voz | `config/aliases.py` + `core/actions.py` + `main.py` |
| Modificar overlay visual | `ui/overlay*.py` |
| Cambiar notificaciones | `core/notification_manager.py` + `ui/notification_panel.py` |
| Modificar API HTTP | `core/event_server.py` |
| Cambiar hooks Claude | `.claude/hooks/*.py` |
| Agregar configuración | `config/settings.py` + `config/default.json` |

### Flujo de Datos (Recordar)

```
Micrófono → Engine → Texto → CommandRegistry → Action → pyautogui
```

---

## 7. Ownership de Áreas

| Área | Owner | Contacto |
|------|-------|----------|
| Core Engine | @DaniGRamirez | GitHub Issues |
| UI/Overlay | @DaniGRamirez | GitHub Issues |
| Claude Integration | @DaniGRamirez | GitHub Issues |

Para preguntas: Abrir issue en GitHub o consultar CLAUDE.md.

---

## 8. Errores Comunes y Soluciones

### "No module named 'pvporcupine'"

```bash
pip install -r requirements-picovoice.txt
```

### "Picovoice access key inválida"

1. Verificar que copiaste la key completa
2. Verificar que no hay espacios extra
3. Regenerar key en console.picovoice.ai

### "Puerto 8765 ya en uso"

```bash
# Windows - encontrar proceso
netstat -ano | findstr :8765

# Matar proceso
taskkill /PID <pid> /F
```

### Overlay no aparece

1. Verificar que PyQt6 está instalado: `pip show PyQt6`
2. Verificar posición en config.json (puede estar fuera de pantalla)
3. Ejecutar en modo debug: `python main.py -d`

### Micrófono no detectado

1. Verificar permisos de micrófono en Windows
2. Verificar dispositivo por defecto en Settings
3. Probar: `python -c "import sounddevice; print(sounddevice.query_devices())"`

### Claude Code no recibe notificaciones

1. Verificar que EventServer está corriendo (puerto 8765)
2. Verificar hook en `.claude/hooks/permission_request_hook.py`
3. Verificar logs: `hook_debug.log`

---

## 9. Comandos Útiles

```bash
# Ver estado del servidor
curl http://localhost:8765/api/status

# Enviar notificación de prueba
curl -X POST http://localhost:8765/api/notification \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "body": "Hola"}'

# Ver logs de uso
type logs\usage.json

# Limpiar cache Python
del /s /q __pycache__

# Reinstalar dependencias
pip install -r requirements.txt --force-reinstall
```

---

## 10. Siguiente Paso

Una vez que puedas:
- [x] Ejecutar VoiceFlow
- [x] Ver el overlay
- [x] Ejecutar un comando (ej: "Claudia... enter")
- [x] Hacer un cambio y verificar

Estás listo para:
1. Leer `CLAUDE.md` para entender comandos
2. Explorar `core/commands.py` para entender matching
3. Revisar `docs/audit/` para contexto completo
