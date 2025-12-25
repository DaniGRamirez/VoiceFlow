"""
Tests for core.notification_manager module.
"""

import pytest
import time


def test_generate_dedup_key():
    """Test dedup key generation."""
    from core.notification_manager import NotificationManager

    manager = NotificationManager()

    data1 = {"title": "Test", "body": "Hello", "tool_name": "Write"}
    data2 = {"title": "Test", "body": "Hello", "tool_name": "Write"}
    data3 = {"title": "Different", "body": "Hello", "tool_name": "Write"}

    key1 = manager._generate_dedup_key(data1)
    key2 = manager._generate_dedup_key(data2)
    key3 = manager._generate_dedup_key(data3)

    # Same content = same key
    assert key1 == key2

    # Different content = different key
    assert key1 != key3


def test_is_duplicate_false_on_first():
    """Test that first notification is not duplicate."""
    from core.notification_manager import NotificationManager

    manager = NotificationManager()

    is_dup, _ = manager._is_duplicate("unique-key-123")
    assert is_dup is False


def test_is_duplicate_true_on_second():
    """Test that second identical notification is duplicate."""
    from core.notification_manager import NotificationManager

    manager = NotificationManager()

    # Add to cache
    manager._dedup_cache["test-key"] = ("cid-123", time.time())

    # Add notification state
    from core.notification_manager import NotificationState
    manager._notifications["cid-123"] = NotificationState(
        correlation_id="cid-123",
        data={},
        status="pending",
        dedup_key="test-key"
    )

    is_dup, existing_cid = manager._is_duplicate("test-key")
    assert is_dup is True
    assert existing_cid == "cid-123"


def test_on_notification_returns_true(sample_notification_data):
    """Test on_notification returns True for new notification."""
    from core.notification_manager import NotificationManager

    manager = NotificationManager()
    result = manager.on_notification(sample_notification_data)

    assert result is True


def test_on_notification_returns_false_for_duplicate(sample_notification_data):
    """Test on_notification returns False for duplicate."""
    from core.notification_manager import NotificationManager

    manager = NotificationManager()

    # First notification
    result1 = manager.on_notification(sample_notification_data)
    assert result1 is True

    # Second identical notification
    data2 = sample_notification_data.copy()
    data2["correlation_id"] = "different-cid"
    result2 = manager.on_notification(data2)

    assert result2 is False


def test_cleanup_old_notifications():
    """Test cleanup removes old notifications."""
    from core.notification_manager import NotificationManager, NotificationState, MAX_NOTIFICATIONS

    manager = NotificationManager()

    # Add more than MAX_NOTIFICATIONS
    for i in range(MAX_NOTIFICATIONS + 20):
        state = NotificationState(
            correlation_id=f"cid-{i}",
            data={},
            status="completed",  # Not pending, can be cleaned
            created_at=time.time() - (i * 10),  # Older as i increases
            dedup_key=f"key-{i}"
        )
        manager._notifications[f"cid-{i}"] = state

    # Run cleanup
    manager._cleanup_old_notifications()

    # Should have MAX_NOTIFICATIONS or fewer
    assert len(manager._notifications) <= MAX_NOTIFICATIONS


def test_pending_count():
    """Test get_pending_count method."""
    from core.notification_manager import NotificationManager, NotificationState

    manager = NotificationManager()

    # Add notifications with different statuses
    manager._notifications["cid-1"] = NotificationState(
        correlation_id="cid-1", data={}, status="pending"
    )
    manager._notifications["cid-2"] = NotificationState(
        correlation_id="cid-2", data={}, status="completed"
    )
    manager._notifications["cid-3"] = NotificationState(
        correlation_id="cid-3", data={}, status="pending"
    )

    assert manager.get_pending_count() == 2


def test_clear_all():
    """Test clear_all method."""
    from core.notification_manager import NotificationManager, NotificationState

    manager = NotificationManager()

    manager._notifications["cid-1"] = NotificationState(
        correlation_id="cid-1", data={}, status="pending"
    )
    manager._dedup_cache["key-1"] = ("cid-1", time.time())

    manager.clear_all()

    assert len(manager._notifications) == 0
    assert len(manager._dedup_cache) == 0
