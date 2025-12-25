"""
Tests for core.state module.
"""

import pytest
from core.state import StateMachine, State


def test_initial_state(state_machine):
    """Test that initial state is IDLE."""
    assert state_machine.state == State.IDLE


def test_transition_to_dictating(state_machine):
    """Test transition from IDLE to DICTATING."""
    state_machine.transition(State.DICTATING)
    assert state_machine.state == State.DICTATING


def test_transition_to_paused(state_machine):
    """Test transition from IDLE to PAUSED."""
    state_machine.transition(State.PAUSED)
    assert state_machine.state == State.PAUSED


def test_transition_back_to_idle(state_machine):
    """Test transition back to IDLE."""
    state_machine.transition(State.DICTATING)
    state_machine.transition(State.IDLE)
    assert state_machine.state == State.IDLE


def test_on_change_callback(state_machine):
    """Test that on_change callback is called."""
    changes = []

    def callback(old, new):
        changes.append((old, new))

    state_machine.on_change(callback)
    state_machine.transition(State.DICTATING)

    assert len(changes) == 1
    assert changes[0] == (State.IDLE, State.DICTATING)


def test_no_callback_on_same_state(state_machine):
    """Test that callback is not called when transitioning to same state."""
    changes = []

    def callback(old, new):
        changes.append((old, new))

    state_machine.on_change(callback)
    state_machine.transition(State.IDLE)  # Same as initial

    assert len(changes) == 0


def test_state_values():
    """Test State enum values."""
    assert State.IDLE.value == "idle"
    assert State.DICTATING.value == "dictating"
    assert State.PAUSED.value == "paused"
