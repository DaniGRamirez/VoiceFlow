@echo off
REM Claude Code PTY Wrapper for Windows
REM This shim intercepts claude CLI calls and routes through the wrapper
REM
REM Usage:
REM   claude [args...]           - Runs through wrapper with VoiceFlow integration
REM
REM Escape hatch:
REM   set CLAUDE_MON_DISABLE=1   - Skip wrapper and run real Claude directly
REM
REM Installation:
REM   Add this shim's directory to PATH (before Claude's install directory)

REM Check for escape hatch
if defined CLAUDE_MON_DISABLE (
    REM Run real claude directly, bypassing the wrapper
    "%LOCALAPPDATA%\Programs\claude-code\claude.exe" %*
    exit /b %ERRORLEVEL%
)

REM Get the directory where this script is located
set "SHIM_DIR=%~dp0"

REM Run through wrapper
node "%SHIM_DIR%..\dist\index.js" %*
exit /b %ERRORLEVEL%
