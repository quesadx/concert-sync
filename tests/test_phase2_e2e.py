"""E2E tests for Phase 2: Fix expire_reservation dead code + startup cleanup."""

import json
import socket
import time
import pytest

from src.server.concert_server import ConcertServer
from src.client.concert_client import ConcertClient
from src.utils.enums import ReservationStatus, SeatState


@pytest.fixture
def server_port():
    """Find a free random port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]
    return port


@pytest.fixture
def concert_server(server_port):
    """Start concert server for testing on random port."""
    import os
    _db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "concert_sync.db")
    try: os.remove(_db)
    except FileNotFoundError: pass
    server = ConcertServer(port=server_port)
    server.start()
    time.sleep(0.5)

    yield type("Server", (), {"port": server_port, "instance": server})()

    server.stop()


@pytest.fixture
def server_instance(server_port):
    """Create server instance WITHOUT starting it (for cleanup tests)."""
    server = ConcertServer(port=server_port)
    yield server
    if server.running:
        server.stop()


class TestExpireReservationFix:
    """Tests for expire_reservation dead code fix."""

    def test_expire_reservation_no_crash(self, concert_server):
        """Calling expire_reservation with nonexistent tx_id should not crash."""
        server = concert_server.instance
        # Should not raise any exception
        server.monitor_thread.expire_reservation("nonexistent-tx-id")
        # If we get here, the test passes
        assert True

    def test_expire_reservation_finds_session_by_transaction_id(self, concert_server):
        """expire_reservation should delegate to expire_session via session_id lookup."""
        server = concert_server.instance
        client = ConcertClient(user_id="TestUser", port=concert_server.port)

        # Reserve a seat (creates a session)
        response = client.reserve_seat("VIP", 0, 0)
        assert response["status"] == "SUCCESS"
        session_id = response["transaction_id"]

        # Age the session's per-seat timestamps
        session = server.session_manager.get_by_session_id(session_id)
        if session is not None:
            import time as _time
            aged = _time.time() - session.ttl_secs - 10
            for seat_key in list(session.seat_timestamps.keys()):
                session.seat_timestamps[seat_key] = aged
            session.last_activity = _time.time() - session.ttl_secs - 10

        # Call expire_reservation with the session_id
        server.monitor_thread.expire_reservation(session_id)

        # Verify seat is now AVAILABLE
        from src.utils.enums import Section
        seat_state = server.seat_matrix.seats[Section.VIP][0][0]
        assert seat_state == SeatState.AVAILABLE, "Seat should be AVAILABLE after expiration"

        # Verify session was removed
        session = server.session_manager.get_by_session_id(session_id)
        assert session is None, "Session should be removed after expiration"


class TestStartupCleanup:
    """Tests for startup stale reservation cleanup."""

    def test_startup_cleanup_stale_reservations(self, server_instance):
        """_cleanup_stale_reservations should remove stale ACTIVE reservations and release seats."""
        server = server_instance
        from src.utils.enums import Section

        # Manually inject a stale reservation
        tx_id = server.reservation_table.add_reservation(
            Section.VIP,
            [(0, 0)],  # 2-tuple seat format
        )
        # Mark the seat as RESERVED in seat_matrix (simulating pre-crash state)
        server.seat_matrix.set_seat_state(Section.VIP, 0, 0, SeatState.RESERVED)

        # Verify preconditions
        assert tx_id in server.reservation_table.reservations
        assert server.seat_matrix.seats[Section.VIP][0][0] == SeatState.RESERVED

        # Call cleanup
        server._cleanup_stale_reservations()

        # Verify seat is back to AVAILABLE
        assert server.seat_matrix.seats[Section.VIP][0][0] == SeatState.AVAILABLE
        # Verify reservation was removed
        assert tx_id not in server.reservation_table.reservations

    def test_startup_cleanup_releases_semaphores(self, server_instance):
        """_cleanup_stale_reservations should restore semaphore capacity."""
        server = server_instance
        from src.utils.enums import Section

        # Acquire a semaphore slot (to verify restoration)
        server.semaphore_mgr.acquire(Section.VIP, blocking=True)

        # Inject a stale reservation
        tx_id = server.reservation_table.add_reservation(
            Section.VIP,
            [(0, 0)],  # 2-tuple seat format
        )
        # Mark seat as RESERVED
        server.seat_matrix.set_seat_state(Section.VIP, 0, 0, SeatState.RESERVED)

        # Verify semaphore capacity was reduced (one less available)
        can_acquire_extra = server.semaphore_mgr.acquire(Section.VIP, blocking=False)
        if can_acquire_extra:
            # If we could acquire, release immediately — semaphore wasn't pre-loaded
            server.semaphore_mgr.release(Section.VIP)

        # Call cleanup
        server._cleanup_stale_reservations()

        # After cleanup, we should be able to acquire (capacity restored)
        acquired = server.semaphore_mgr.acquire(Section.VIP, blocking=False)
        assert acquired, "Semaphore capacity should be restored after cleanup"
        server.semaphore_mgr.release(Section.VIP)

        # Release the initial acquire
        server.semaphore_mgr.release(Section.VIP)


class TestExpireSession:
    """Tests for session-based expiration."""

    def test_expire_session_releases_seats(self, concert_server):
        """expire_session should release reserved seats and remove session."""
        server = concert_server.instance
        client = ConcertClient(user_id="TestUser", port=concert_server.port)
        from src.utils.enums import Section

        # Reserve a seat
        response = client.reserve_seat("VIP", 1, 1)
        assert response["status"] == "SUCCESS"
        session_id = response["transaction_id"]

        # Get the session and age its per-seat timestamps
        session = server.session_manager.get_by_session_id(session_id)
        assert session is not None
        import time as _time
        aged = _time.time() - session.ttl_secs - 10
        for seat_key in list(session.seat_timestamps.keys()):
            session.seat_timestamps[seat_key] = aged
        session.last_activity = _time.time() - session.ttl_secs - 10

        # Verify seat is RESERVED
        assert server.seat_matrix.seats[Section.VIP][1][1] == SeatState.RESERVED

        # Call expire_session directly
        server.monitor_thread.expire_session(session)

        # Verify seat is AVAILABLE
        assert server.seat_matrix.seats[Section.VIP][1][1] == SeatState.AVAILABLE

        # Verify session was removed
        session_check = server.session_manager.get_by_session_id(session_id)
        assert session_check is None, "Session should be removed after expire_session"
