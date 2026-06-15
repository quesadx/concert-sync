"""
Notification management for ConcertSync push notification system (v1.0).

Provides thread-safe per-user notification queues, subscriber management,
and a background notifier thread for async push delivery over TCP.

NotificationManager stores subscriber sockets and message queues, while
NotifierThread polls the queues and sends JSON notification messages
to subscribed clients.
"""

import json
import queue
import socket
import threading
import time
from typing import Dict, List, Optional, Set

from src.utils.enums import NotificationType
from src.utils.error_responses import build_notification_response


class NotificationSubscriber:
    """Represents a single subscriber with its socket and message queue.

    Attributes:
        user_id: The user identifier this subscription belongs to.
        socket: The TCP socket used for push delivery.
        queue: A thread-safe queue.Queue holding pending notifications.
        last_activity: Timestamp of last activity (subscribe or message enqueue).
    """

    def __init__(self, user_id: str, socket: socket.socket):
        self.user_id = user_id
        self.socket = socket
        self.queue: queue.Queue = queue.Queue()
        self.last_activity = time.time()


class NotificationManager:
    """Thread-safe notification queue and subscriber management.

    Manages per-user message queues and subscription sockets. All public
    methods are safe to call from any thread (TransactionalThread,
    MonitorThread, etc.) without additional locking.

    Key design points:
    - subscribe() replaces existing subscription for same user_id (closes old socket)
    - append() is non-blocking — just enqueues to queue.Queue
    - generate_ticket_id() provides sequential TKT-NNNNNN format IDs
    - section_full_state tracks section fullness for AVAILABILITY detection
    """

    def __init__(self, global_log):
        """Initialize the notification manager.

        Args:
            global_log: GlobalLog instance for event logging.
        """
        self._subscribers: Dict[str, NotificationSubscriber] = {}
        self._lock = threading.Lock()
        self._global_log = global_log
        self._section_full_state: Dict[str, bool] = {
            "VIP": False,
            "PREFERENTIAL": False,
            "GENERAL": False,
        }
        self._ticket_counter = 0
        self._ticket_counter_lock = threading.Lock()
        self.running = True

    # ── Subscription Management ───────────────────────────────────────────

    def subscribe(self, user_id: str, client_socket: socket) -> bool:
        """Register a client socket for push notification delivery.

        If a subscription for this user_id already exists, the old socket
        is closed and replaced by the new one.

        Args:
            user_id: User identifier for the subscriber.
            client_socket: TCP socket to deliver notifications over.

        Returns:
            True if subscription was successful.
        """
        with self._lock:
            if user_id in self._subscribers:
                old = self._subscribers[user_id]
                try:
                    old.socket.close()
                except Exception:
                    pass
            sub = NotificationSubscriber(user_id, client_socket)
            self._subscribers[user_id] = sub
        self._global_log.append(
            "NOTIFICATION",
            f"User:{user_id} subscribed to notifications",
        )
        self.append(user_id, NotificationType.SUBSCRIBED,
                    "[NOTIFICACIÓN]\nSuscripción a notificaciones activada.")
        return True

    def unsubscribe(self, user_id: str) -> bool:
        """Remove a subscription and close its socket.

        Args:
            user_id: User identifier to unsubscribe.

        Returns:
            True if a subscription was removed, False if not found.
        """
        with self._lock:
            sub = self._subscribers.pop(user_id, None)
            if sub is None:
                return False
            try:
                sub.socket.close()
            except Exception:
                pass
        self._global_log.append(
            "NOTIFICATION",
            f"User:{user_id} unsubscribed from notifications",
        )
        return True

    # ── Notification Enqueue ──────────────────────────────────────────────

    def append(self, user_id: str, n_type: NotificationType, message: str) -> None:
        """Enqueue a notification for a specific user.

        Non-blocking — just enqueues to the subscriber's queue.Queue.
        Safe to call from any thread (TransactionalThread, MonitorThread)
        while holding existing locks.

        Args:
            user_id: Target user identifier.
            n_type: NotificationType enum member.
            message: Human-readable notification message.
        """
        notification = build_notification_response(n_type.value, message)
        with self._lock:
            sub = self._subscribers.get(user_id)
            if sub is None:
                return
            sub.queue.put(notification)
            sub.last_activity = time.time()

    def append_to_all(self, n_type: NotificationType, message: str) -> None:
        """Enqueue a notification for all currently subscribed users.

        Args:
            n_type: NotificationType enum member.
            message: Human-readable notification message.
        """
        notification = build_notification_response(n_type.value, message)
        with self._lock:
            for sub in self._subscribers.values():
                sub.queue.put(notification)

    def get_next_notification(self, user_id: str, timeout: float = 1.0) -> Optional[dict]:
        """Dequeue the next pending notification for a user, with timeout.

        Args:
            user_id: User identifier.
            timeout: Maximum seconds to wait for a notification.

        Returns:
            The notification dict, or None if timeout expires.
        """
        with self._lock:
            sub = self._subscribers.get(user_id)
            if sub is None:
                return None
            q = sub.queue
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None

    # ── Query Methods ─────────────────────────────────────────────────────

    def get_all_subscribers(self) -> List[str]:
        """Get list of all currently subscribed user IDs.

        Returns:
            List of user_id strings.
        """
        with self._lock:
            return list(self._subscribers.keys())

    def get_subscriber_count(self) -> int:
        """Get the number of active subscribers.

        Returns:
            Subscriber count.
        """
        with self._lock:
            return len(self._subscribers)

    # ── Ticket ID Generation ──────────────────────────────────────────────

    def generate_ticket_id(self) -> str:
        """Generate a sequential ticket ID in TKT-NNNNNN format.

        Thread-safe using a dedicated counter lock.

        Returns:
            Ticket ID string, e.g. "TKT-000001".
        """
        with self._ticket_counter_lock:
            self._ticket_counter += 1
            return f"TKT-{self._ticket_counter:06d}"

    # ── Section Full State ────────────────────────────────────────────────

    def set_section_full(self, section_name: str, is_full: bool) -> None:
        """Set whether a section is fully occupied.

        Used for AVAILABILITY notification detection.

        Args:
            section_name: Section name ("VIP", "PREFERENTIAL", "GENERAL").
            is_full: True if section has no available seats.
        """
        with self._lock:
            self._section_full_state[section_name] = is_full

    def is_section_full(self, section_name: str) -> bool:
        """Check if a section is currently marked as fully occupied.

        Args:
            section_name: Section name ("VIP", "PREFERENTIAL", "GENERAL").

        Returns:
            True if section was marked full.
        """
        with self._lock:
            return self._section_full_state.get(section_name, False)

    # ── Cleanup ───────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Close all subscriber sockets and clear subscriptions.

        Called during server shutdown.
        """
        self.running = False
        with self._lock:
            for user_id, sub in list(self._subscribers.items()):
                try:
                    sub.socket.close()
                except Exception:
                    pass
            self._subscribers.clear()
