"""
Tests for core.commands module.
"""

import pytest
from core.commands import CommandRegistry, Command
from core.state import State


def test_register_command(registry, sample_command):
    """Test registering a command."""
    registry.register(sample_command)
    assert len(registry._commands) == 1


def test_find_single_command(registry, sample_command):
    """Test finding a single command by keyword."""
    registry.register(sample_command)
    result = registry.find_chain("test", State.IDLE)

    assert len(result) == 1
    assert result[0].keywords[0] == "test"


def test_find_command_with_alias(registry, sample_command):
    """Test finding command using alias."""
    registry.register(sample_command)
    result = registry.find_chain("prueba", State.IDLE)

    assert len(result) == 1
    assert result[0].keywords[0] == "test"


def test_find_command_case_insensitive(registry, sample_command):
    """Test case insensitive matching."""
    registry.register(sample_command)
    result = registry.find_chain("TEST", State.IDLE)

    assert len(result) == 1


def test_find_no_match(registry, sample_command):
    """Test when no command matches."""
    registry.register(sample_command)
    result = registry.find_chain("unknown", State.IDLE)

    assert len(result) == 0


def test_find_wrong_state(registry):
    """Test command not available in wrong state."""
    cmd = Command(
        keywords=["listo"],
        action=lambda: None,
        allowed_states=[State.DICTATING],  # Only in DICTATING
        sound="success"
    )
    registry.register(cmd)

    result = registry.find_chain("listo", State.IDLE)
    assert len(result) == 0

    result = registry.find_chain("listo", State.DICTATING)
    assert len(result) == 1


def test_find_chain_multiple_commands(registry):
    """Test finding chain of commands."""
    cmd1 = Command(
        keywords=["enter"],
        action=lambda: None,
        allowed_states=[State.IDLE],
        sound="click"
    )
    cmd2 = Command(
        keywords=["tab"],
        action=lambda: None,
        allowed_states=[State.IDLE],
        sound="click"
    )
    registry.register(cmd1)
    registry.register(cmd2)

    result = registry.find_chain("enter tab", State.IDLE)
    assert len(result) == 2
    assert result[0].keywords[0] == "enter"
    assert result[1].keywords[0] == "tab"


def test_command_with_next_state(registry):
    """Test command with next_state for chaining."""
    cmd = Command(
        keywords=["dictado"],
        action=lambda: None,
        allowed_states=[State.IDLE],
        sound="ding",
        next_state=State.DICTATING
    )
    registry.register(cmd)

    result = registry.find_chain("dictado", State.IDLE)
    assert len(result) == 1
    assert result[0].next_state == State.DICTATING


def test_command_defaults():
    """Test Command default values."""
    cmd = Command(
        keywords=["test"],
        action=lambda: None
    )

    assert cmd.allowed_states == [State.IDLE]
    assert cmd.sound is None
    assert cmd.next_state is None
