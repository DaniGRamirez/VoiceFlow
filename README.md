# VoiceFlow

Control por voz para Windows. Dicta a Claude en VSCode sin tocar el teclado.

## Características

- **Wake-word "Claudia"** en español (Picovoice Porcupine)
- **Dictado con Win+H** de Windows (gratis, sin servicios externos)
- **Overlay visual animado** con feedback en tiempo real
- **30+ comandos de voz** para navegación y edición
- **Logging de uso** para mejorar reconocimiento

## Requisitos

- Windows 10/11
- Python 3.10+
- VSCode con extensión Claude
- Micrófono
- [API key de Picovoice](https://console.picovoice.ai/) (gratis)

## Instalación

### 1. Clonar repositorio

```bash
git clone https://github.com/tu-usuario/voiceflow.git
cd voiceflow
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
pip install -r requirements-picovoice.txt
```

### 3. Descargar modelo Vosk

Descarga el modelo de español desde [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models):

- **vosk-model-small-es-0.42** (45 MB) - Rápido, menos preciso
- **vosk-model-es-0.42** (1.1 GB) - Lento, más preciso

Extrae en la carpeta `models/`:

```
voiceflow/
└── models/
    ├── vosk-model-small-es-0.42/
    └── vosk-model-es-0.42/
```

### 4. Configurar Picovoice

1. Crea una cuenta en [console.picovoice.ai](https://console.picovoice.ai/)
2. Copia tu Access Key
3. Crea un archivo `.env` (recomendado) o edita `config.json`:

**Opción A - Variables de entorno (recomendado):**
```bash
cp .env.example .env
# Edita .env y pega tu key:
PICOVOICE_ACCESS_KEY=TU-API-KEY-AQUI
```

**Opción B - config.json:**
```json
{
  "picovoice": {
    "access_key": "TU-API-KEY-AQUI"
  }
}
```

### 5. Ejecutar

```bash
python main.py
```

## Uso

1. El overlay aparece en pantalla (barras blancas animadas)
2. Di **"Claudia"** para activar
3. El overlay colapsa y espera tu comando
4. Di el comando (ej: "abre chat")
5. VoiceFlow ejecuta la acción

### Flujo de dictado

```
"Claudia" → "dictado" → [dictas tu texto] → "listo"
```

- **"listo"**: Envía el texto dictado
- **"cancela"**: Descarta todo
- **"pausa"**: Pausa temporalmente

## Comandos Disponibles

### Activación

| Comando | Acción |
|---------|--------|
| claudia | Abre VSCode y chat de Claude |
| claudia dictado | Abre chat y comienza dictado |

### Dictado

| Comando | Acción |
|---------|--------|
| dictado | Inicia dictado con Win+H |
| listo | Termina dictado y envía |
| cancela | Cancela y borra todo |
| enviar | Envía mensaje (Enter) |
| pausa | Pausa el dictado |
| reanuda | Continúa el dictado |

### Navegación

| Comando | Aliases | Acción |
|---------|---------|--------|
| enter | intro, entrar | Presiona Enter |
| escape | escapar | Presiona Escape |
| tab | tabulador | Presiona Tab |
| arriba | sube | Flecha arriba |
| abajo | baja | Flecha abajo |
| izquierda | - | Flecha izquierda |
| derecha | - | Flecha derecha |
| inicio | - | Ir al inicio |
| fin | final | Ir al final |

### Edición

| Comando | Aliases | Acción |
|---------|---------|--------|
| copiar | copia | Ctrl+C |
| pegar | pega | Ctrl+V |
| deshacer | deshace | Ctrl+Z |
| rehacer | rehace | Ctrl+Y |
| guardar | guarda | Ctrl+S |
| seleccion | selección | Ctrl+A (seleccionar todo) |
| eliminar | elimina | Delete |
| borrar | borra | Backspace |
| borra todo | borrar todo | Borra todo el texto |

### Utilidades

| Comando | Acción |
|---------|--------|
| aceptar | Click en botón aceptar |
| repetir | Repite última acción |
| ayuda | Muestra comandos disponibles |
| opcion uno/dos/tres... | Presiona tecla numérica |

## Configuración

El archivo `config.json` se crea automáticamente. Opciones principales:

```json
{
  "engine": "picovoice",
  "dictation_mode": "winh",

  "picovoice": {
    "access_key": "tu-api-key",
    "sensitivity": 0.7,
    "command_window": 5.0
  },

  "overlay": {
    "size": 40,
    "position": [100, 100],
    "opacity": 0.9
  },

  "sounds": {
    "enabled": true,
    "volume": 0.5
  },

  "timing": {
    "vscode_focus_delay": 0.3,
    "chat_open_delay": 0.5
  }
}
```

### Opciones de motor

| Motor | Descripción |
|-------|-------------|
| picovoice | Wake-word "Claudia" + Win+H (recomendado) |
| vosk | Reconocimiento continuo sin wake-word |
| hybrid | OpenWakeWord + Win+H (legacy) |

## Argumentos de línea de comandos

```bash
python main.py [opciones]

Opciones:
  -d, --debug           Modo debug (sin reconocimiento)
  -e, --engine ENGINE   Motor: vosk, picovoice, hybrid
  -m, --model MODEL     Modelo Vosk: small, large
  -D, --dictation MODE  Modo dictado: wispr, winh
  -h, --help            Muestra ayuda

Ejemplos:
  python main.py                    # Picovoice (default)
  python main.py -e vosk -m small   # Vosk con modelo pequeño
  python main.py -d                 # Modo debug
```

## Overlay Visual

El overlay muestra el estado del sistema:

| Estado | Visual | Descripción |
|--------|--------|-------------|
| IDLE | Barras blancas | Escuchando wake-word |
| LISTENING | Punto pulsante | Wake detectado, esperando comando |
| DICTATING | Círculo rojo | Grabando dictado |
| PAUSED | Círculo amarillo | Dictado pausado |

### Controles del overlay

- **Arrastrar**: Mover posición
- **Click derecho**: Menú contextual
- **Guardar posición**: Se guarda en config.json

## Troubleshooting

### "No detecta el micrófono"

Verifica que Windows tiene acceso al micrófono:
- Configuración → Privacidad → Micrófono

### "Wake-word no responde"

1. Verifica tu API key de Picovoice
2. Aumenta la sensibilidad en config.json:
   ```json
   "picovoice": {
     "sensitivity": 0.8
   }
   ```

### "Dictado no funciona"

- Asegúrate de que Win+H funciona manualmente
- El dictado de Windows debe estar habilitado

### "VSCode no se enfoca"

- Verifica que VSCode está abierto
- Ajusta `vscode_focus_delay` en config.json

## Logging

VoiceFlow guarda estadísticas en `logs/usage.json`:

- Comandos ejecutados
- Textos no reconocidos (útil para añadir aliases)
- Duración de sesiones

## Tests

```bash
pytest                    # Ejecutar todos los tests
pytest tests/ -v          # Con output detallado
pytest tests/test_commands.py  # Solo tests de comandos
```

## Licencia

MIT
