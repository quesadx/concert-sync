"""
Notification system tests for ConcertSync.

Tests the NotificationManager, subscription protocol,
and all notification event emission hooks.
"""

import json
import socket
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.server.notification_manager import NotificationManager, NotifierThread
from src.utils.enums import NotificationType
from src.utils.error_responses import build_notification_response


class FakeLog:
    def __init__(self):
        self.entries = []

    def append(self, *args):
        self.entries.append(args)


class TestNotificationManager:
    def setup_method(self):
        self.log = FakeLog()
        self.nm = NotificationManager(self.log)

    def test_subscribe_and_notify(self):
        s1, s2 = socket.socketpair()
        self.nm.subscribe("user1", s1)
        assert self.nm.get_subscriber_count() == 1

        # Drain the auto-generated SUBSCRIBED notification
        sub_notif = self.nm.get_next_notification("user1", timeout=1)
        assert sub_notif is not None
        assert sub_notif["notification_type"] == "SUBSCRIBED"

        self.nm.append("user1", NotificationType.TTL_WARNING, "Test")
        notif = self.nm.get_next_notification("user1", timeout=1)
        assert notif is not None
        assert notif["type"] == "NOTIFICATION"
        assert notif["notification_type"] == "TTL_WARNING"
        s1.close()
        s2.close()

    def test_subscribe_replaces_existing(self):
        s1, s2 = socket.socketpair()
        s3, s4 = socket.socketpair()
        self.nm.subscribe("user1", s1)
        self.nm.subscribe("user1", s3)
        assert self.nm.get_subscriber_count() == 1
        s1.close()
        s3.close()
        s4.close()

    def test_append_to_all(self):
        s1, s2 = socket.socketpair()
        s3, s4 = socket.socketpair()
        self.nm.subscribe("u1", s1)
        self.nm.subscribe("u2", s3)
        # Drain auto-generated SUBSCRIBED notifications
        self.nm.get_next_notification("u1", timeout=1)
        self.nm.get_next_notification("u2", timeout=1)
        self.nm.append_to_all(NotificationType.AVAILABILITY, "Broadcast")
        n1 = self.nm.get_next_notification("u1", timeout=1)
        n2 = self.nm.get_next_notification("u2", timeout=1)
        assert n1 is not None and n2 is not None
        assert n1["notification_type"] == "AVAILABILITY"
        assert n2["notification_type"] == "AVAILABILITY"
        s1.close()
        s2.close()
        s3.close()
        s4.close()

    def test_generate_ticket_id(self):
        id1 = self.nm.generate_ticket_id()
        id2 = self.nm.generate_ticket_id()
        assert id1 == "TKT-000001"
        assert id2 == "TKT-000002"

    def test_section_full_state(self):
        self.nm.set_section_full("VIP", True)
        assert self.nm.is_section_full("VIP") is True
        self.nm.set_section_full("VIP", False)
        assert self.nm.is_section_full("VIP") is False

    def test_unsubscribe(self):
        s1, s2 = socket.socketpair()
        self.nm.subscribe("user1", s1)
        assert self.nm.get_subscriber_count() == 1
        self.nm.unsubscribe("user1")
        assert self.nm.get_subscriber_count() == 0
        s1.close()
        s2.close()

    def test_append_nonexistent_user(self):
        """Appending to non-subscribed user should not error."""
        self.nm.append("nonexistent", NotificationType.CONFIRMED, "Test")
        # No assertion needed — just verify no exception


class TestBuildNotificationResponse:
    def test_response_shape(self):
        resp = build_notification_response("TTL_WARNING", "Test message")
        assert resp["type"] == "NOTIFICATION"
        assert resp["notification_type"] == "TTL_WARNING"
        assert resp["message"] == "Test message"
        assert "timestamp" in resp
        assert isinstance(resp["timestamp"], str)
