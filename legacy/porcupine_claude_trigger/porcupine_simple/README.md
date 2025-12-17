# Claude Voice Trigger con Porcupine

**Alternativa SIMPLE a Talon** - Wake word detection que FUNCIONA.

## Por qué Porcupine > Talon para esto

| Aspecto | Talon + Conformer | Porcupine |
|---------|-------------------|-----------|
| Precisión wake words | ~20% | ~95% |
| Soporta español | Mal | ✅ Sí |
| Setup | Complejo | 3 comandos |
| Peso | ~2 GB | ~5 MB |

## Setup (5 minutos)

### Paso 1: Instalar dependencias

```bash
pip install pvporcupine pvrecorder pyautogui
```

### Paso 2: Conseguir API Key (GRATIS)

1. Ve a https://console.picovoice.ai/
2. Crea una cuenta (gratis)
3. Copia tu AccessKey

### Paso 3: Configurar

Edita `claude_trigger.py`:

```python
ACCESS_KEY = "tu-api-key-aqui"
WAKE_WORD = "jarvis"  # o "computer", "alexa", etc.
```

### Paso 4: Ejecutar

```bash
python claude_trigger.py
```

## Wake words disponibles (gratis)

- `jarvis` ← Recomendado, muy preciso
- `computer`
- `hey google`
- `ok google`
- `alexa`
- `hey siri`
- `terminator`
- `bumblebee`
- `porcupine`

## Crear wake word personalizado (ej: "Claudia")

1. Ve a https://console.picovoice.ai/
2. Click en "Porcupine" → "Train Wake Word"
3. Escribe "claudia" (soporta español!)
4. Descarga el archivo `.ppn`
5. Usa así:

```python
porcupine = pvporcupine.create(
    access_key=ACCESS_KEY,
    keyword_paths=["ruta/a/claudia.ppn"],
    sensitivities=[0.7]
)
```

## Ejecutar al iniciar Windows

1. Crea un archivo `claude_trigger.bat`:
```batch
@echo off
python "C:\ruta\a\claude_trigger.py"
```

2. Presiona `Win+R`, escribe `shell:startup`
3. Copia el .bat ahí

## Free tier límites

- 3 wake words personalizados
- Sin límite de uso para wake words incluidos (jarvis, etc.)
- Suficiente para uso personal

## Troubleshooting

### "No se detecta el micrófono"
```python
# Lista los dispositivos disponibles
from pvrecorder import PvRecorder
for i, device in enumerate(PvRecorder.get_available_devices()):
    print(f"{i}: {device}")

# Usa el índice correcto
recorder = PvRecorder(device_index=1, ...)  # Cambia el número
```

### "API key inválida"
Verifica que copiaste bien la key desde https://console.picovoice.ai/

### "Detecta demasiadas falsas alarmas"
Baja la sensibilidad:
```python
SENSITIVITY = 0.5  # Más bajo = menos falsos positivos
```
