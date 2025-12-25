"""
Tests for ActionExecutor context system.

Tests the new pipeline context features:
- Variable interpolation from context
- transform action with various operations
- set action for storing variables
- condition action for conditional execution
- capture_clipboard action
"""

import pytest
from unittest.mock import patch, MagicMock

from core.action_executor import ActionExecutor


@pytest.fixture
def executor():
    """Create an ActionExecutor instance for testing."""
    return ActionExecutor(allow_dangerous=False)


class TestContextInitialization:
    """Test context initialization and predefined variables."""

    def test_initial_context_has_predefined_vars(self, executor):
        """Context should have clipboard, date, time, timestamp."""
        context = executor._create_initial_context()

        assert "clipboard" in context
        assert "date" in context
        assert "time" in context
        assert "timestamp" in context

    def test_initial_context_with_custom_vars(self, executor):
        """Custom initial context should be merged."""
        context = executor._create_initial_context({"my_var": "my_value"})

        assert context["my_var"] == "my_value"
        assert "clipboard" in context  # Predefined vars still there


class TestVariableInterpolation:
    """Test variable interpolation in actions."""

    def test_interpolate_simple_var(self, executor):
        """Should replace {var} with context value."""
        context = {"name": "John"}
        action = {"type": "log", "message": "Hello {name}!"}

        result = executor._interpolate_vars(action, context)

        assert result["message"] == "Hello John!"

    def test_interpolate_multiple_vars(self, executor):
        """Should replace multiple variables."""
        context = {"first": "Hello", "second": "World"}
        action = {"type": "log", "message": "{first} {second}!"}

        result = executor._interpolate_vars(action, context)

        assert result["message"] == "Hello World!"

    def test_interpolate_in_list(self, executor):
        """Should interpolate variables in list items."""
        context = {"key": "ctrl"}
        action = {"type": "hotkey", "keys": ["{key}", "c"]}

        result = executor._interpolate_vars(action, context)

        assert result["keys"] == ["ctrl", "c"]

    def test_interpolate_preserves_unknown_vars(self, executor):
        """Unknown variables should remain as-is."""
        context = {"known": "value"}
        action = {"type": "log", "message": "{known} and {unknown}"}

        result = executor._interpolate_vars(action, context)

        assert result["message"] == "value and {unknown}"


class TestTransformAction:
    """Test the transform action type."""

    def test_transform_upper(self, executor):
        """upper operation should uppercase text."""
        action = {"type": "transform", "input": "hello", "operation": "upper"}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "HELLO"

    def test_transform_lower(self, executor):
        """lower operation should lowercase text."""
        action = {"type": "transform", "input": "HELLO", "operation": "lower"}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "hello"

    def test_transform_trim(self, executor):
        """trim operation should strip whitespace."""
        action = {"type": "transform", "input": "  hello  ", "operation": "trim"}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "hello"

    def test_transform_title(self, executor):
        """title operation should capitalize words."""
        action = {"type": "transform", "input": "hello world", "operation": "title"}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "Hello World"

    def test_transform_reverse(self, executor):
        """reverse operation should reverse text."""
        action = {"type": "transform", "input": "hello", "operation": "reverse"}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "olleh"

    def test_transform_length(self, executor):
        """length operation should return string length."""
        action = {"type": "transform", "input": "hello", "operation": "length"}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "5"

    def test_transform_replace(self, executor):
        """replace:old:new should replace substrings."""
        action = {"type": "transform", "input": "hello world", "operation": "replace:world:universe"}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "hello universe"

    def test_transform_prefix(self, executor):
        """prefix:text should add prefix."""
        action = {"type": "transform", "input": "world", "operation": "prefix:hello "}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "hello world"

    def test_transform_suffix(self, executor):
        """suffix:text should add suffix."""
        action = {"type": "transform", "input": "hello", "operation": "suffix: world"}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "hello world"

    def test_transform_slice(self, executor):
        """slice:start:end should slice text."""
        action = {"type": "transform", "input": "hello world", "operation": "slice:0:5"}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "hello"

    def test_transform_regex(self, executor):
        """regex:pattern:replacement should do regex replace."""
        action = {"type": "transform", "input": "hello123world", "operation": "regex:[0-9]+: "}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "hello world"

    def test_transform_split(self, executor):
        """split:delimiter:index should split and get element."""
        action = {"type": "transform", "input": "a,b,c", "operation": "split:,:1"}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "b"

    def test_transform_unknown_operation(self, executor):
        """Unknown operation should return input unchanged."""
        action = {"type": "transform", "input": "hello", "operation": "unknown_op"}
        context = {}

        result = executor._execute_transform(action, context)

        assert result == "hello"


class TestSetAction:
    """Test the set action type."""

    def test_set_creates_variable(self, executor):
        """set should create variable in context."""
        context = {}
        action = {"type": "set", "var": "my_var", "value": "my_value"}

        result = executor._execute_one(action, context)

        assert context["my_var"] == "my_value"
        assert result == "my_value"

    def test_set_overwrites_variable(self, executor):
        """set should overwrite existing variable."""
        context = {"my_var": "old_value"}
        action = {"type": "set", "var": "my_var", "value": "new_value"}

        executor._execute_one(action, context)

        assert context["my_var"] == "new_value"


class TestConditionAction:
    """Test the condition action type."""

    def test_condition_equals_true(self, executor):
        """condition with equals should match."""
        context = {}
        action = {
            "type": "condition",
            "if": "hello",
            "equals": "hello",
            "then": [{"type": "set", "var": "result", "value": "matched"}]
        }

        executor._execute_condition(action, context)

        assert context.get("result") == "matched"

    def test_condition_equals_false(self, executor):
        """condition with equals should not match."""
        context = {}
        action = {
            "type": "condition",
            "if": "hello",
            "equals": "world",
            "then": [{"type": "set", "var": "result", "value": "matched"}],
            "else": [{"type": "set", "var": "result", "value": "not_matched"}]
        }

        executor._execute_condition(action, context)

        assert context.get("result") == "not_matched"

    def test_condition_contains(self, executor):
        """condition with contains should work."""
        context = {}
        action = {
            "type": "condition",
            "if": "hello world",
            "contains": "world",
            "then": [{"type": "set", "var": "result", "value": "found"}]
        }

        executor._execute_condition(action, context)

        assert context.get("result") == "found"

    def test_condition_not_empty(self, executor):
        """condition with not_empty should work."""
        context = {}
        action = {
            "type": "condition",
            "if": "some text",
            "not_empty": True,
            "then": [{"type": "set", "var": "result", "value": "has_content"}]
        }

        executor._execute_condition(action, context)

        assert context.get("result") == "has_content"

    def test_condition_not_empty_false(self, executor):
        """condition with not_empty=false should match empty."""
        context = {}
        action = {
            "type": "condition",
            "if": "",
            "not_empty": False,
            "then": [{"type": "set", "var": "result", "value": "is_empty"}]
        }

        executor._execute_condition(action, context)

        assert context.get("result") == "is_empty"

    def test_condition_starts_with(self, executor):
        """condition with starts_with should work."""
        context = {}
        action = {
            "type": "condition",
            "if": "hello world",
            "starts_with": "hello",
            "then": [{"type": "set", "var": "result", "value": "starts"}]
        }

        executor._execute_condition(action, context)

        assert context.get("result") == "starts"

    def test_condition_truthy(self, executor):
        """condition without comparison should use truthy check."""
        context = {}
        action = {
            "type": "condition",
            "if": "non-empty",
            "then": [{"type": "set", "var": "result", "value": "truthy"}]
        }

        executor._execute_condition(action, context)

        assert context.get("result") == "truthy"


class TestCaptureClipboard:
    """Test the capture_clipboard action."""

    @patch('core.action_executor.pyperclip.paste')
    def test_capture_clipboard(self, mock_paste, executor):
        """capture_clipboard should return clipboard content."""
        mock_paste.return_value = "clipboard content"
        context = {}
        action = {"type": "capture_clipboard"}

        result = executor._execute_one(action, context)

        assert result == "clipboard content"


class TestPipelineWithContext:
    """Test full pipeline execution with context."""

    @patch('core.action_executor.pyperclip.paste')
    def test_pipeline_context_flow(self, mock_paste, executor):
        """Variables should flow between actions in pipeline."""
        mock_paste.return_value = "Hello World"

        actions = [
            {"type": "set", "var": "greeting", "value": "Hello"},
            {"type": "transform", "input": "{greeting}", "operation": "upper", "output": "loud_greeting"},
            {"type": "log", "message": "Result: {loud_greeting}"}
        ]

        result = executor.execute_pipeline(actions, "test", initial_context={})

        assert result is True

    @patch('core.action_executor.pyperclip.paste')
    @patch('core.action_executor.pyautogui')
    def test_pipeline_with_condition(self, mock_pyautogui, mock_paste, executor):
        """Conditional actions should work in pipeline."""
        mock_paste.return_value = ""

        actions = [
            {"type": "set", "var": "mode", "value": "debug"},
            {
                "type": "condition",
                "if": "{mode}",
                "equals": "debug",
                "then": [{"type": "set", "var": "result", "value": "debug_mode"}],
                "else": [{"type": "set", "var": "result", "value": "normal_mode"}]
            }
        ]

        # Need to track context to verify
        with patch.object(executor, '_create_initial_context') as mock_ctx:
            ctx = {"clipboard": "", "date": "2024-01-01", "time": "12:00", "timestamp": "20240101_120000"}
            mock_ctx.return_value = ctx

            result = executor.execute_pipeline(actions, "test")

            assert result is True


class TestLogAction:
    """Test the log action type."""

    def test_log_returns_message(self, executor):
        """log should return the message."""
        context = {}
        action = {"type": "log", "message": "test message"}

        result = executor._execute_one(action, context)

        assert result == "test message"
