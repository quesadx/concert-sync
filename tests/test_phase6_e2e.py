"""E2E tests for Phase 6: Instance Closure + Saturated Zone + Audit Log."""

import os
import re
import socket
import time

from src.client.concert_client import ConcertClient, ConcertClientError
from src.server.concert_server import ConcertServer
from src.utils.enums import Section, SeatState


def _wait_for_server(host, port, retries=50, wait_seconds=0.1):
    for _ in range(retries):
        try:
            client = ConcertClient(host=host, port=port)
            response = client.query()
            if response.get("status") == "SUCCESS":
                return
        except Exception:
            time.sleep(wait_seconds)
    raise RuntimeError("Server did not start in time")


LOG_FILE = "logs/system.log"


def _read_log_tail(path, n=20):
    try:
        with open(path, "r") as f:
            lines = f.readlines()
        return [l.strip() for l in lines[-n:] if l.strip()]
    except FileNotFoundError:
        return []


class TestShutdownCleanup:
    """Tests for server shutdown seat release."""

    def test_stop_releases_single_session_seats(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)
            client = ConcertClient(user_id="ShutdownA", port=port)
            client.reserve_seat("VIP", 0, 0)
            assert server.seat_matrix.seats[Section.VIP][0][0] == SeatState.RESERVED
        finally:
            server.stop()

        assert server.seat_matrix.seats[Section.VIP][0][0] == SeatState.AVAILABLE
        assert server.session_manager.get_by_user_id("ShutdownA") is None

    def test_stop_releases_multiple_sessions(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)
            client_a = ConcertClient(user_id="MultiA", port=port)
            client_b = ConcertClient(user_id="MultiB", port=port)
            client_a.reserve_seat("VIP", 0, 2)
            client_b.reserve_seat("PREFERENTIAL", 0, 0)
            assert server.seat_matrix.seats[Section.VIP][0][2] == SeatState.RESERVED
            assert server.seat_matrix.seats[Section.PREFERENTIAL][0][0] == SeatState.RESERVED
        finally:
            server.stop()

        assert server.seat_matrix.seats[Section.VIP][0][2] == SeatState.AVAILABLE
        assert server.seat_matrix.seats[Section.PREFERENTIAL][0][0] == SeatState.AVAILABLE
        assert server.session_manager.get_by_user_id("MultiA") is None
        assert server.session_manager.get_by_user_id("MultiB") is None

    def test_stop_releases_semaphores(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)
            initial_value = server.semaphore_mgr.s_sections[Section.VIP]._value
            client = ConcertClient(user_id="SemTest", port=port)
            client.reserve_seat("VIP", 0, 3)
            client.reserve_seat("VIP", 0, 4)
            after_reserve = server.semaphore_mgr.s_sections[Section.VIP]._value
            assert after_reserve == initial_value - 2
        finally:
            server.stop()

        restored = server.semaphore_mgr.s_sections[Section.VIP]._value
        assert restored == initial_value


class TestLogFormat:
    """Tests for GlobalLog TID format."""

    def test_log_entry_contains_thread_id(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)
            client = ConcertClient(user_id="LogTID", port=port)
            client.reserve_seat("VIP", 0, 5)
        finally:
            server.stop()

        lines = _read_log_tail(LOG_FILE, 30)
        tid_lines = [l for l in lines if "[TID:" in l]
        assert len(tid_lines) > 0, f"No [TID:] found in log tail ({len(lines)} lines)"

    def test_log_format_preserved(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)
            client = ConcertClient(user_id="LogFmt", port=port)
            client.reserve_seat("VIP", 0, 6)
        finally:
            server.stop()

        lines = _read_log_tail(LOG_FILE, 30)
        pattern = re.compile(r"\[\d{4}-\d{2}-\d{2}T.*\] \[.*\] \[TID:\d+\] .*")
        matching = [l for l in lines if pattern.match(l)]
        assert len(matching) > 0, f"No log lines match the expected format with TID"
