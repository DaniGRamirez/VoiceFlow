"""
Tests for CommandRegistry thread safety and source tracking.
"""

import pytest
import threading
import time

from core.commands import CommandRegistry, Command
from core.state import State


def test_register_with_source():
    """Test registering commands with source tracking."""
    registry = CommandRegistry()

    cmd1 = Command(keywords=["test1"], action=lambda: None)
    cmd2 = Command(keywords=["test2"], action=lambda: None)

    registry.register(cmd1, source="builtin")
    registry.register(cmd2, source="custom")

    counts = registry.get_source_counts()
    assert counts["builtin"] == 1
    assert counts["custom"] == 1


def test_unregister_by_source():
    """Test unregistering commands by source."""
    registry = CommandRegistry()

    # Register commands from different sources
    for i in range(5):
        registry.register(
            Command(keywords=[f"builtin{i}"], action=lambda: None),
            source="builtin"
        )
    for i in range(3):
        registry.register(
            Command(keywords=[f"custom{i}"], action=lambda: None),
            source="custom"
        )

    # Verify initial counts
    counts = registry.get_source_counts()
    assert counts["builtin"] == 5
    assert counts["custom"] == 3

    # Unregister custom commands
    removed = registry.unregister_by_source("custom")
    assert removed == 3

    # Verify builtin commands remain
    counts = registry.get_source_counts()
    assert counts["builtin"] == 5
    assert "custom" not in counts


def test_register_batch():
    """Test batch registration of commands."""
    registry = CommandRegistry()

    commands = [
        Command(keywords=[f"cmd{i}"], action=lambda: None)
        for i in range(10)
    ]

    count = registry.register_batch(commands, source="batch")
    assert count == 10

    counts = registry.get_source_counts()
    assert counts["batch"] == 10


def test_get_commands_by_source():
    """Test getting commands by source."""
    registry = CommandRegistry()

    registry.register(Command(keywords=["a"], action=lambda: None), source="A")
    registry.register(Command(keywords=["b"], action=lambda: None), source="B")
    registry.register(Command(keywords=["c"], action=lambda: None), source="A")

    a_commands = registry.get_commands_by_source("A")
    assert len(a_commands) == 2
    assert all(cmd.keywords[0] in ["a", "c"] for cmd in a_commands)


def test_find_with_lock():
    """Test that find() is thread-safe."""
    registry = CommandRegistry()

    # Register some commands
    for i in range(100):
        registry.register(
            Command(keywords=[f"cmd{i}"], action=lambda: None),
            source="test"
        )

    errors = []

    def find_worker():
        try:
            for _ in range(100):
                result = registry.find("cmd50", State.IDLE)
                if result is None:
                    errors.append("Command not found")
        except Exception as e:
            errors.append(str(e))

    def modify_worker():
        try:
            for _ in range(50):
                registry.register(
                    Command(keywords=["new"], action=lambda: None),
                    source="dynamic"
                )
                time.sleep(0.001)
                registry.unregister_by_source("dynamic")
        except Exception as e:
            errors.append(str(e))

    # Run concurrent access
    threads = [
        threading.Thread(target=find_worker),
        threading.Thread(target=find_worker),
        threading.Thread(target=modify_worker),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors occurred: {errors}"


def test_unregister_preserves_other_sources():
    """Test that unregistering one source doesn't affect others."""
    registry = CommandRegistry()

    # Register commands
    registry.register(Command(keywords=["keep1"], action=lambda: None), source="keep")
    registry.register(Command(keywords=["remove1"], action=lambda: None), source="remove")
    registry.register(Command(keywords=["keep2"], action=lambda: None), source="keep")

    # Remove one source
    registry.unregister_by_source("remove")

    # Verify kept commands still work
    result = registry.find("keep1", State.IDLE)
    assert result is not None
    assert result.keywords[0] == "keep1"

    result = registry.find("keep2", State.IDLE)
    assert result is not None


def test_find_chain_with_lock():
    """Test that find_chain() is thread-safe."""
    registry = CommandRegistry()

    registry.register(Command(keywords=["a"], action=lambda: None), source="test")
    registry.register(Command(keywords=["b"], action=lambda: None), source="test")
    registry.register(Command(keywords=["c"], action=lambda: None), source="test")

    errors = []

    def chain_worker():
        try:
            for _ in range(100):
                result = registry.find_chain("a b c", State.IDLE)
                if len(result) != 3:
                    errors.append(f"Expected 3 commands, got {len(result)}")
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=chain_worker) for _ in range(5)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors occurred: {errors}"
