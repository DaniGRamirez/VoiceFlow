---
name: setup-voiceflow-command
description: Create new VoiceFlow voice commands. Use when asked to add, create, or setup a new voice command, custom command, or voice action for VoiceFlow.
allowed-tools: Read, Write, Edit, Glob
---

# Setup VoiceFlow Command

This skill helps create new voice commands for the VoiceFlow system.

## VoiceFlow Command Architecture

VoiceFlow has two types of commands:

1. **Built-in commands** - Registered in `main.py` using `registry.register()`
2. **Custom commands** - JSON files in `config/commands/` (preferred for new commands)

## Custom Command JSON Structure

Location: `config/commands/{command_name}.json`

```json
{
  "version": "1.0",
  "description": "What this command file does",
  "commands": [
    {
      "name": "command-name",
      "keywords": ["primary", "keyword"],
      "aliases": ["alias1", "alias2", "spanish-variant"],
      "description": "Human-readable description",
      "states": ["idle"],
      "sound": "ding",
      "actions": [
        { "type": "key", "key": "enter" }
      ]
    }
  ]
}
```

## Available Action Types

| Type | Parameters | Example |
|------|------------|---------|
| `key` | `key` | `{"type": "key", "key": "enter"}` |
| `hotkey` | `keys[]` | `{"type": "hotkey", "keys": ["ctrl", "c"]}` |
| `type` | `text` | `{"type": "type", "text": "hello"}` |
| `wait` | `seconds` | `{"type": "wait", "seconds": 0.5}` |
| `open` | `path` | `{"type": "open", "path": "https://..."}` |
| `clipboard` | `text` | `{"type": "clipboard", "text": "..."}` |
| `sound` | `name` | `{"type": "sound", "name": "success"}` |
| `shell` | `cmd`, `timeout` | `{"type": "shell", "cmd": "git status"}` |
| `prompt` | `template` | `{"type": "prompt", "template": "config/prompts/x.json"}` |
| `browser` | `actions[]` | Browser automation via Playwright |

## Valid States

- `idle` - Default state, waiting for commands
- `dictating` - During voice dictation
- `paused` - System paused

## Available Sounds

`ding`, `success`, `error`, `click`, `pop`, `notification`

## Step-by-Step Process

1. **Understand the command purpose** - What should happen when user says it?

2. **Choose keywords and aliases**
   - Primary keyword: most natural phrase
   - Aliases: Spanish variants, common mishearings
   - Check `config/aliases.py` for existing patterns

3. **Define the action pipeline**
   - Simple: single key/hotkey
   - Complex: multiple steps with waits

4. **Create the JSON file**
   - Save to `config/commands/{name}.json`
   - Follow existing patterns from `ejemplo.json`, `mute.json`

5. **Test activation**
   - VoiceFlow loads commands on startup
   - User says keyword → action executes

## Example: Simple Hotkey Command

```json
{
  "version": "1.0",
  "description": "Toggle microphone mute",
  "commands": [
    {
      "name": "mute",
      "keywords": ["silencio", "mute"],
      "aliases": ["silenciar", "mutear"],
      "description": "Mutes system audio",
      "states": ["idle"],
      "actions": [
        { "type": "key", "key": "volumemute" }
      ]
    }
  ]
}
```

## Example: Multi-Step Command with Template

```json
{
  "version": "1.0",
  "description": "Send clipboard to ChatGPT with template",
  "commands": [
    {
      "name": "resumen",
      "keywords": ["resumen"],
      "aliases": ["resumir", "resume"],
      "description": "Summarize clipboard content",
      "states": ["idle"],
      "sound": "ding",
      "actions": [
        { "type": "prompt", "template": "config/prompts/resumen.json" },
        {
          "type": "browser",
          "actions": [
            { "action": "connect" },
            { "action": "find_tab", "url_contains": "chatgpt" },
            { "action": "paste", "selector": "div[contenteditable='true']" },
            { "action": "press", "key": "Enter" }
          ]
        }
      ]
    }
  ]
}
```

## Prompt Template Structure

If command needs a prompt template, create `config/prompts/{name}.json`:

```json
{
  "name": "template-name",
  "description": "What this template does",
  "prompt": "Your instructions here.\n\nUser content:\n{user_msg}"
}
```

The `{user_msg}` placeholder is replaced with clipboard content.

## Alias Suggestions

When creating aliases, consider:
- Spanish spelling variants (acento vs no acento)
- Common speech recognition errors
- English equivalents if relevant
- Check `logs/usage.json` "ignored" field for frequently misheard words
