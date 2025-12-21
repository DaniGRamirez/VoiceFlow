---
name: analyze-voiceflow-patterns
description: Analyze VoiceFlow usage logs to find patterns, suggest new aliases, and identify recognition problems. Use when asked to analyze voice patterns, check usage, review logs, improve recognition, or find alias opportunities.
allowed-tools: Read, Grep, Glob
---

# Analyze VoiceFlow Voice Patterns

This skill analyzes `logs/usage.json` to extract insights and suggest improvements.

## Data Source

Location: `logs/usage.json`

Structure:
```json
{
  "sessions": [
    {
      "start": "2025-12-18T10:25:53",
      "end": "2025-12-18T10:27:53",
      "duration_seconds": 120.0,
      "commands": [
        {
          "time": "2025-12-18T10:26:18",
          "command": "claudia",
          "recognized": "claudia"
        }
      ],
      "ignored": [
        {
          "time": "2025-12-18T10:26:09",
          "text": "clave"
        }
      ]
    }
  ]
}
```

## Analysis Steps

### 1. Load and Parse Usage Data

Read `logs/usage.json` and extract:
- Total sessions count
- Total commands executed
- Total ignored texts
- Date range of data

### 2. Analyze Ignored Texts

Find frequently ignored texts that might be:
- **Misheard commands** → candidates for new aliases
- **Background noise** → should remain ignored
- **New command ideas** → user trying to do something not supported

Report format:
```
IGNORED TEXT ANALYSIS
=====================
Text               | Count | Possible Match
-------------------|-------|---------------
"lector"           |    12 | dictado (sounds similar)
"mercado"          |     8 | dictado (sounds similar)
"entre"            |     5 | enter (Spanish variant)
```

### 3. Analyze Command Success Rates

For each command, calculate:
- Times executed
- Recognition variants (what was actually heard)
- Success rate

Report format:
```
COMMAND PERFORMANCE
===================
Command    | Executions | Variants Heard
-----------|------------|----------------
dictado    |         45 | dictado(30), estado(10), víctor(5)
enter      |         32 | enter(28), intro(4)
listo      |         28 | listo(25), lista(3)
```

### 4. Identify Alias Opportunities

Cross-reference:
- Ignored texts that appear frequently
- Existing aliases in `config/aliases.py`
- Patterns of recognition errors

Suggest additions:
```
SUGGESTED NEW ALIASES
=====================
Add to DICTADO_ALIASES:
  - "lector" (ignored 12 times, sounds like dictado)

Add to ENTER_ALIASES:
  - "entre" (ignored 5 times, Spanish for enter)
```

### 5. Detect Underused Commands

Find commands with:
- Low execution count
- High ignore rate when attempted
- Candidates for deprecation or renaming

### 6. Session Statistics

Overall health metrics:
```
SESSION STATISTICS
==================
Total sessions:        156
Avg session duration:  89 seconds
Commands per session:  4.2
Ignore rate:          12%
Peak usage hours:     10:00-12:00, 15:00-17:00
```

## Output Format

Provide a structured report with:

1. **Executive Summary** - Key findings in 3-4 bullet points
2. **Alias Recommendations** - Specific additions to `config/aliases.py`
3. **Problem Commands** - Commands with recognition issues
4. **Usage Trends** - Most/least used commands
5. **Action Items** - Prioritized list of improvements

## Example Analysis Output

```markdown
## Voice Pattern Analysis Report

### Summary
- 156 sessions analyzed (Dec 1-21, 2025)
- 12% ignore rate (below 15% threshold ✓)
- 3 high-value alias opportunities identified

### Recommended Alias Additions

**High Priority:**
1. Add "lector" to DICTADO_ALIASES
   - Ignored 12 times, phonetically similar
   - Edit: config/aliases.py line 45

**Medium Priority:**
2. Add "entre" to ENTER_ALIASES
   - Spanish variant, ignored 5 times

### Commands Needing Attention
- "rehacer" - 0 uses, consider removing or renaming
- "tab" - Often confused with "estaba", alias already exists

### Top 5 Commands
1. dictado (45 uses)
2. enter (32 uses)
3. listo (28 uses)
4. code dictado (22 uses)
5. escape (18 uses)
```

## When to Run This Analysis

- Weekly: Quick check for new alias opportunities
- After adding new commands: Verify recognition works
- When users report "it doesn't understand me": Debug specific phrases
