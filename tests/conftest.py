"""
Pytest fixtures for VoiceFlow tests.
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def state_machine():
    """Create a fresh StateMachine instance."""
    from core.state import StateMachine
    return StateMachine()


@pytest.fixture
def registry():
    """Create a fresh CommandRegistry instance."""
    from core.commands import CommandRegistry
    return CommandRegistry()


@pytest.fixture
def sample_command():
    """Create a sample Command for testing."""
    from core.commands import Command
    from core.state import State

    return Command(
        keywords=["test", "prueba"],
        action=lambda: None,
        allowed_states=[State.IDLE],
        sound="click"
    )


@pytest.fixture
def sample_notification_data():
    """Create sample notification data for testing."""
    return {
        "correlation_id": "test-123",
        "title": "Test Notification",
        "body": "This is a test",
        "tool_name": "TestTool",
        "session_id": "session-abc"
    }
