"""E2E tests for Phase 6: Instance Closure + Saturated Zone + Audit Log."""

import os
import re
import socket
import time

import pytest

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


class TestDisconnectDetection:
    """Tests for TUI server disconnection detection."""

    def test_client_raises_on_stopped_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)
            client = ConcertClient(user_id="DiscoA", port=port)
            response = client.reserve_seat("VIP", 0, 6)
            assert response.get("status") == "SUCCESS"
        finally:
            server.stop()

        with pytest.raises(ConcertClientError):
            client.query()

    def test_client_recovers_after_restart(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port1 = s.getsockname()[1]

        server1 = ConcertServer(port=port1)
        server1.start()
        try:
            _wait_for_server("localhost", port1)
            client = ConcertClient(user_id="DiscoB", port=port1)
            response = client.reserve_seat("VIP", 0, 7)
            assert response.get("status") == "SUCCESS"
        finally:
            server1.stop()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port2 = s.getsockname()[1]

        server2 = ConcertServer(port=port2)
        server2.start()
        try:
            _wait_for_server("localhost", port2)
            client2 = ConcertClient(user_id="DiscoB", port=port2)
            response = client2.query()
            assert response.get("status") == "SUCCESS"
        finally:
            server2.stop()


class TestSaturatedZone:
    """Tests for saturated zone pre-flight seat availability check."""

    def test_preflight_detects_unavailable_seat(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)
            client_a = ConcertClient(user_id="UserA", port=port)
            response = client_a.reserve_seat("VIP", 0, 8)
            assert response.get("status") == "SUCCESS"

            client_b = ConcertClient(user_id="UserB", port=port)
            seat_map_resp = client_b.query_seat_map()
            seat_map = seat_map_resp.get("seat_map", {})
            vip_grid = seat_map.get("VIP", [])
            assert vip_grid[0][8] != "AVAILABLE"
        finally:
            server.stop()

    def test_preflight_passes_for_available_seats(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)
            client_c = ConcertClient(user_id="UserC", port=port)
            response = client_c.reserve_seat("VIP", 0, 9)
            assert response.get("status") == "SUCCESS"

            client_d = ConcertClient(user_id="UserD", port=port)
            seat_map_resp = client_d.query_seat_map()
            seat_map = seat_map_resp.get("seat_map", {})
            vip_grid = seat_map.get("VIP", [])

            assert vip_grid[0][9] == "RESERVED"
            assert vip_grid[1][0] == "AVAILABLE"
        finally:
            server.stop()
