# Claude PTY Wrapper

PTY wrapper for Claude Code CLI that integrates with VoiceFlow for voice-controlled confirmations.

## Features

- **Transparent passthrough**: User sees normal Claude output
- **Transcript monitoring**: Watches Claude's `.jsonl` transcript files for tool uses
- **VoiceFlow integration**: Sends notifications when tools need confirmation
- **Session management**: Tracks multiple concurrent sessions
- **Windows shim**: Seamlessly intercepts `claude` commands

## Installation

### 1. Install dependencies

```bash
cd claude-pty-wrapper
npm install
```

### 2. Build

```bash
npm run build
```

### 3. Install shim (optional)

To intercept all `claude` commands:

```powershell
.\shim\install-shim.ps1
```

Restart your terminal after installation.

## Usage

### Direct usage

```bash
node dist/index.js "your prompt here"
```

### With shim installed

```bash
claude "your prompt here"
```

### Escape hatch (bypass wrapper)

```powershell
$env:CLAUDE_MON_DISABLE = 1
claude "your prompt here"
```

## Options

```
Usage: claude-wrapper [options] [claude args...]

Options:
  -V, --version              output the version number
  --voiceflow-url <url>      VoiceFlow server URL (default: "http://localhost:8765")
  --no-voiceflow             Disable VoiceFlow integration
  --claude-path <path>       Path to Claude CLI executable
  --project <path>           Claude project path (auto-detected if not specified)
  --debug                    Enable debug logging
  -h, --help                 display help for command
```

## Architecture

```
User runs: claude "prompt"
    │
    ▼
claude.cmd (shim) ── CLAUDE_MON_DISABLE? ──► Real Claude
    │
    ▼
Node.js PTY Wrapper
    ├── PTY Spawner (node-pty)
    │   └── Spawns real Claude CLI
    │   └── Forwards all output to console
    ├── Transcript Watcher (chokidar)
    │   └── Watches ~/.claude/projects/*.jsonl
    │   └── Detects tool_use / tool_result
    └── VoiceFlow Client
        └── POST /api/notification
        └── DELETE /api/notification/{id}
            │
            ▼
        VoiceFlow (Python)
        └── NotificationPanel (overlay)
```

## Auto-approved Commands

The following Bash commands don't trigger notifications:

- Git: `git add`, `git commit`, `git push`, `git status`, etc.
- Python: `python -c`, `pip install`, etc.
- Node: `npm install`, `npm run`, etc.
- Read-only: `ls`, `cat`, `pwd`, `dir`, etc.

See [src/transcript/auto-approve.ts](src/transcript/auto-approve.ts) for the full list.

## Development

### Watch mode

```bash
npm run watch
```

### Run directly with ts-node

```bash
npm run dev -- "your prompt"
```

## License

MIT
