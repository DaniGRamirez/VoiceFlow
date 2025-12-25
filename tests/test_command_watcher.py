"""
Tests for CommandWatcher hot reload functionality.
"""

import pytest
import os
import json
import tempfile
import time
import shutil

from core.commands import CommandRegistry, Command
from core.command_watcher import CommandWatcher, ReloadResult


@pytest.fixture
def temp_commands_dir():
    """Create a temporary directory for command JSON files."""
    temp_dir = tempfile.mkdtemp(prefix="voiceflow_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_registry():
    """Create a CommandRegistry with some built-in commands."""
    registry = CommandRegistry()
    registry.register(Command(keywords=["builtin1"], action=lambda: None), source="builtin")
    registry.register(Command(keywords=["builtin2"], action=lambda: None), source="builtin")
    return registry


@pytest.fixture
def mock_loader_factory(temp_commands_dir):
    """Create a factory that produces CustomCommandLoader instances."""
    def factory():
        from core.custom_commands import CustomCommandLoader
        return CustomCommandLoader(
            commands_dir=temp_commands_dir,
            allow_dangerous=False
        )
    return factory


def write_command_json(directory: str, filename: str, commands: list):
    """Helper to write a command JSON file."""
    filepath = os.path.join(directory, filename)
    data = {
        "version": "1.0",
        "commands": commands
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    return filepath


def test_reload_result_dataclass():
    """Test ReloadResult dataclass."""
    result = ReloadResult(
        success=True,
        commands_loaded=5,
        commands_removed=3,
        errors=["error1"],
        files_processed=["file1.json"]
    )
    assert result.success
    assert result.commands_loaded == 5
    assert result.commands_removed == 3
    assert len(result.errors) == 1
    assert len(result.files_processed) == 1


def test_watcher_reload_empty_dir(temp_commands_dir, mock_registry, mock_loader_factory):
    """Test reloading with no command files."""
    watcher = CommandWatcher(
        commands_dir=temp_commands_dir,
        registry=mock_registry,
        loader_factory=mock_loader_factory,
        config={}
    )

    result = watcher.reload()

    # No errors, but also no commands loaded
    assert result.success
    assert result.commands_loaded == 0
    assert result.errors == []


def test_watcher_reload_loads_commands(temp_commands_dir, mock_registry, mock_loader_factory):
    """Test reloading loads commands from JSON files."""
    # Write a command file
    write_command_json(temp_commands_dir, "test.json", [
        {
            "name": "test1",
            "keywords": ["test1"],
            "actions": [{"type": "key", "key": "enter"}]
        },
        {
            "name": "test2",
            "keywords": ["test2"],
            "actions": [{"type": "key", "key": "escape"}]
        }
    ])

    watcher = CommandWatcher(
        commands_dir=temp_commands_dir,
        registry=mock_registry,
        loader_factory=mock_loader_factory,
        config={}
    )

    result = watcher.reload()

    assert result.success
    assert result.commands_loaded == 2
    assert len(result.files_processed) == 1

    # Verify commands were registered
    counts = mock_registry.get_source_counts()
    assert counts.get("custom", 0) == 2
    assert counts.get("builtin", 0) == 2  # Builtin still there


def test_watcher_reload_replaces_old_commands(temp_commands_dir, mock_registry, mock_loader_factory):
    """Test that reload replaces old custom commands."""
    watcher = CommandWatcher(
        commands_dir=temp_commands_dir,
        registry=mock_registry,
        loader_factory=mock_loader_factory,
        config={}
    )

    # First load
    write_command_json(temp_commands_dir, "test.json", [
        {"name": "old", "keywords": ["old"], "actions": [{"type": "key", "key": "a"}]}
    ])
    result1 = watcher.reload()
    assert result1.commands_loaded == 1

    # Second load with different commands
    os.remove(os.path.join(temp_commands_dir, "test.json"))
    write_command_json(temp_commands_dir, "new.json", [
        {"name": "new1", "keywords": ["new1"], "actions": [{"type": "key", "key": "b"}]},
        {"name": "new2", "keywords": ["new2"], "actions": [{"type": "key", "key": "c"}]}
    ])
    result2 = watcher.reload()

    assert result2.success
    assert result2.commands_loaded == 2
    assert result2.commands_removed == 1  # Old command removed

    # Verify only new commands exist
    counts = mock_registry.get_source_counts()
    assert counts.get("custom", 0) == 2


def test_watcher_ignores_underscore_files(temp_commands_dir, mock_registry, mock_loader_factory):
    """Test that files starting with _ are ignored."""
    write_command_json(temp_commands_dir, "_ignored.json", [
        {"name": "ignored", "keywords": ["ignored"], "actions": [{"type": "key", "key": "x"}]}
    ])
    write_command_json(temp_commands_dir, "loaded.json", [
        {"name": "loaded", "keywords": ["loaded"], "actions": [{"type": "key", "key": "y"}]}
    ])

    watcher = CommandWatcher(
        commands_dir=temp_commands_dir,
        registry=mock_registry,
        loader_factory=mock_loader_factory,
        config={}
    )

    result = watcher.reload()

    assert result.success
    assert result.commands_loaded == 1
    assert len(result.files_processed) == 1


def test_watcher_handles_invalid_json(temp_commands_dir, mock_registry, mock_loader_factory):
    """Test that invalid JSON files are handled gracefully."""
    # Write valid file
    write_command_json(temp_commands_dir, "valid.json", [
        {"name": "valid", "keywords": ["valid"], "actions": [{"type": "key", "key": "z"}]}
    ])

    # Write invalid JSON
    invalid_path = os.path.join(temp_commands_dir, "invalid.json")
    with open(invalid_path, 'w') as f:
        f.write("{invalid json content")

    watcher = CommandWatcher(
        commands_dir=temp_commands_dir,
        registry=mock_registry,
        loader_factory=mock_loader_factory,
        config={}
    )

    result = watcher.reload()

    # Should load valid file but report error for invalid
    assert result.success  # Partial success
    assert result.commands_loaded == 1
    assert len(result.errors) == 1
    assert "invalid.json" in result.errors[0]


def test_watcher_preserves_builtin_commands(temp_commands_dir, mock_registry, mock_loader_factory):
    """Test that builtin commands are never removed."""
    watcher = CommandWatcher(
        commands_dir=temp_commands_dir,
        registry=mock_registry,
        loader_factory=mock_loader_factory,
        config={}
    )

    # Initial builtin count
    initial_counts = mock_registry.get_source_counts()
    assert initial_counts.get("builtin", 0) == 2

    # Load and reload multiple times
    for i in range(3):
        write_command_json(temp_commands_dir, f"test{i}.json", [
            {"name": f"cmd{i}", "keywords": [f"cmd{i}"], "actions": [{"type": "key", "key": "a"}]}
        ])
        watcher.reload()

    # Builtin commands should still be there
    final_counts = mock_registry.get_source_counts()
    assert final_counts.get("builtin", 0) == 2


def test_watcher_config_options(temp_commands_dir, mock_registry, mock_loader_factory):
    """Test that config options are respected."""
    config = {
        "custom_commands": {
            "hot_reload": {
                "enabled": True,
                "debounce_seconds": 1.0,
                "notify_on_reload": False
            }
        }
    }

    watcher = CommandWatcher(
        commands_dir=temp_commands_dir,
        registry=mock_registry,
        loader_factory=mock_loader_factory,
        config=config,
        debounce_seconds=1.0
    )

    assert watcher._debounce_seconds == 1.0
    assert watcher._notify_on_reload is False


def test_watcher_is_running_property(temp_commands_dir, mock_registry, mock_loader_factory):
    """Test is_running property."""
    watcher = CommandWatcher(
        commands_dir=temp_commands_dir,
        registry=mock_registry,
        loader_factory=mock_loader_factory,
        config={}
    )

    assert not watcher.is_running

    # Note: We don't test start() here because it requires watchdog
    # and would actually start monitoring. In a real test, you'd mock watchdog.
