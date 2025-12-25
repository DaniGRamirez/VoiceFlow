# VoiceFlow - Action Plan 30 Días

## Contexto

Plan ejecutable para 1 persona trabajando part-time (~2h/día).

---

## Semana 1 - Limpieza y Estabilización

### Día 1-2: Eliminar Dead Code

- [ ] Eliminar `core/skill_*.py` (5 archivos)
- [ ] Eliminar `core/permission_store.py`
- [ ] Eliminar `ui/ui_Merged.txt`
- [ ] Eliminar archivos `nul`, `claude-pty-wrapper/del`
- [ ] Limpiar archivos con encoding raro en git

```bash
rm -f core/skill_*.py core/permission_store.py
rm -f ui/ui_Merged.txt nul ui/nul claude-pty-wrapper/del
git add -A && git commit -m "chore: Remove dead code and temp files"
```

### Día 3: Seguridad Básica

- [ ] Crear `.env.example` con variables requeridas
- [ ] Actualizar `config/settings.py` para leer de env vars
- [ ] Documentar en README

```python
# config/settings.py
import os

def load_config():
    config = load_json("config.json")
    # Override con env vars
    if os.environ.get("PICOVOICE_ACCESS_KEY"):
        config["picovoice"]["access_key"] = os.environ["PICOVOICE_ACCESS_KEY"]
    return config
```

### Día 4-5: Actualizar .gitignore y Repo Health

- [ ] Agregar patrones faltantes a .gitignore
- [ ] Mover `logs/usage.json` a .gitignore
- [ ] Commit y push

```gitignore
# Agregar a .gitignore
.pytest_cache/
.mypy_cache/
.coverage
coverage.xml
logs/usage.json
*.bak
```

---

## Semana 2 - Testing Básico

### Día 1-2: Setup pytest

- [ ] Crear `tests/` directory
- [ ] Crear `tests/conftest.py` con fixtures
- [ ] Crear `pytest.ini` o `pyproject.toml`

```bash
pip install pytest pytest-cov
mkdir tests
```

```python
# tests/conftest.py
import pytest
from core.commands import CommandRegistry
from core.state import StateMachine, State

@pytest.fixture
def state_machine():
    return StateMachine()

@pytest.fixture
def registry():
    return CommandRegistry()
```

### Día 3-4: Tests Críticos

- [ ] `tests/test_state.py` - StateMachine transitions
- [ ] `tests/test_commands.py` - Command matching
- [ ] `tests/test_notification_manager.py` - Deduplicación

```python
# tests/test_commands.py
def test_find_single_command(registry):
    registry.register(Command(keywords=["enter"]))
    result = registry.find_chain("enter", State.IDLE)
    assert len(result) == 1
    assert result[0].keywords == ["enter"]

def test_find_with_alias(registry):
    registry.register(Command(keywords=["enter", "aceptar"]))
    result = registry.find_chain("aceptar", State.IDLE)
    assert len(result) == 1
```

### Día 5: CI Básico

- [ ] Crear `.github/workflows/test.yml`
- [ ] Verificar que pasa en GitHub

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt pytest
      - run: pytest -v
```

---

## Semana 3 - Documentación y Quality

### Día 1-2: Documentación API

- [ ] Crear `docs/API.md` con todos los endpoints
- [ ] Agregar ejemplos curl para cada endpoint

```markdown
# docs/API.md

## POST /api/notification

Crea una notificación en el panel.

**Request:**
curl -X POST http://localhost:8765/api/notification \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "body": "Hello"}'

**Response:**
{"success": true, "correlation_id": "uuid"}
```

### Día 3: Comandos de Voz

- [ ] Crear `docs/COMMANDS.md` con tabla completa
- [ ] Incluir todos los aliases

### Día 4-5: Linting Setup

- [ ] Instalar black, isort, flake8
- [ ] Crear configuración en `pyproject.toml`
- [ ] Ejecutar y fixear issues críticos

```bash
pip install black isort flake8
black core/ ui/ --check
isort core/ ui/ --check
```

---

## Semana 4 - Refactor Inicial

### Día 1-3: Split main.py

- [ ] Crear `cli.py` con argparse
- [ ] Crear `bootstrap.py` con inicialización
- [ ] Reducir main.py a <100 líneas

```python
# main.py (después)
from cli import parse_args
from bootstrap import create_app

def main():
    args = parse_args()
    app = create_app(args)
    app.run()

if __name__ == "__main__":
    main()
```

### Día 4: Type Hints

- [ ] Agregar type hints a `core/state.py`
- [ ] Agregar type hints a `core/commands.py`
- [ ] Configurar mypy básico

### Día 5: Review y Merge

- [ ] Revisar todos los cambios
- [ ] Actualizar CHANGELOG.md
- [ ] Tag versión v1.1.0

---

## Backlog Post-30 Días

### Prioridad Alta

- [ ] Split overlay.py en rendering/logic
- [ ] Aumentar test coverage a 40%
- [ ] Health checks endpoint
- [ ] Logging centralizado

### Prioridad Media

- [ ] Pre-commit hooks
- [ ] Dependabot
- [ ] ADRs para decisiones arquitectónicas
- [ ] GIF demo en README

### Prioridad Baja

- [ ] Event bus
- [ ] Plugin system para commands
- [ ] OpenAPI docs para EventServer
- [ ] Sphinx docs generados

---

## Checkpoints de Verificación

### Fin Semana 1
- [ ] No hay archivos muertos en repo
- [ ] Secrets no están hardcodeados
- [ ] .gitignore completo

### Fin Semana 2
- [ ] `pytest` corre sin errores
- [ ] Al menos 5 tests pasando
- [ ] CI verde en GitHub

### Fin Semana 3
- [ ] API.md existe y es útil
- [ ] COMMANDS.md existe
- [ ] `black --check` pasa

### Fin Semana 4
- [ ] main.py < 100 líneas
- [ ] Type hints en core crítico
- [ ] Tag v1.1.0 creado

---

## Métricas de Éxito

| Métrica | Inicio | Semana 2 | Semana 4 |
|---------|--------|----------|----------|
| Dead code | ~570 | 0 | 0 |
| Test coverage | 3% | 15% | 25% |
| main.py líneas | 600+ | 600+ | <100 |
| CI | ❌ | ✅ | ✅ |
| Docs | Parcial | Básica | Completa |
