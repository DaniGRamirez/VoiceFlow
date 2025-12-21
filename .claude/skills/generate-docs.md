---
name: generate-voiceflow-docs
description: Generate documentation for VoiceFlow commands. Use when asked to document commands, create command reference, generate docs, list all commands, or create a command cheatsheet.
allowed-tools: Read, Write, Glob, Grep
---

# Generate VoiceFlow Command Documentation

This skill generates unified documentation of all VoiceFlow commands by scanning the codebase.

## Data Sources

1. **Built-in commands**: `main.py` - registered via `registry.register()`
2. **Custom commands**: `config/commands/*.json`
3. **Aliases**: `config/aliases.py`
4. **Prompt templates**: `config/prompts/*.json`

## Documentation Generation Steps

### 1. Scan Built-in Commands

Read `main.py` and extract:
- Command registrations
- Keywords from alias imports
- Valid states
- Associated sounds

Pattern to find:
```python
registry.register(Command(
    keywords=ALIAS_NAME,
    action=actions.on_something,
    valid_states=[State.IDLE],
    sound="ding"
))
```

### 2. Scan Custom Commands

Read all `config/commands/*.json` files and extract:
- Command name
- Keywords and aliases
- Description
- Action pipeline summary
- Required states

### 3. Scan Aliases

Read `config/aliases.py` and map:
- Alias constant name → list of variants
- Used by which commands

### 4. Scan Prompt Templates

Read `config/prompts/*.json` for commands that use templates:
- Template name
- Description
- Prompt preview (first 100 chars)

## Output: docs/COMMANDS.md

Generate a markdown file with:

```markdown
# VoiceFlow Command Reference

Generated: 2025-12-21

## Quick Reference

| Command | Keywords | State | Sound |
|---------|----------|-------|-------|
| enter | enter, intro, entrar | idle | click |
| dictado | dictado, dicta, estado | idle | ding |
...

## Built-in Commands

### Navigation
- **enter** - Press Enter key
  - Keywords: enter, intro, entrar, entró, center, entre
  - State: idle
  - Sound: click

### Editing
- **copiar** - Copy selection
  - Keywords: copiar, copia
  - State: idle

## Custom Commands

### resumen
- **Description**: Summarize clipboard content via ChatGPT
- **Keywords**: resumen, resumir, resume
- **State**: idle
- **Actions**:
  1. Apply prompt template
  2. Open ChatGPT tab
  3. Paste and send

### plan
- **Description**: Generate development plan
- **Keywords**: plan, planear, planifica
- **State**: idle

## Aliases Reference

| Alias Constant | Variants |
|----------------|----------|
| ENTER_ALIASES | enter, intro, entrar, entró, center, entre, entero, entera |
| DICTADO_ALIASES | dictado, dicta, dictando, estado, dictador, héctor, mercado... |
...

## Statistics

- Total built-in commands: 20
- Total custom commands: 12
- Total unique keywords: 85
- Total aliases: 120
```

## Consistency Checks

While generating, detect and report:

1. **Orphan aliases** - Defined in aliases.py but not used
2. **Missing aliases** - Commands without Spanish variants
3. **Duplicate keywords** - Same keyword in multiple commands
4. **Broken references** - Commands referencing non-existent templates

Report format:
```
CONSISTENCY ISSUES
==================
⚠️ REINICIAR_ALIASES defined but not imported in main.py
⚠️ "mute" keyword used in both mute.json and ejemplo.json
⚠️ plan.json references config/prompts/plan.json (exists ✓)
```

## Usage

When user asks to generate docs:

1. Scan all sources
2. Generate `docs/COMMANDS.md`
3. Report any consistency issues
4. Optionally update README.md with command count

## Example Trigger Phrases

- "document all commands"
- "generate command reference"
- "create docs for voiceflow"
- "list all voice commands"
- "make a command cheatsheet"
