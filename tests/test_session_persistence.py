"""Verify session persistence across disconnect/reconnect (SESS-01, SESS-02).

Reproduces the teacher-flagged Prueba 8: reserved seats must survive client
disconnect and be reclaimable with the same session ID.
"""

import time

from src.utils.config import RESERVATION_TTL
from src.utils.enums import ReservationStatus, SeatState, Section


class TestSessionPersistence:
    """Reconnect reclaim, session_id reclaim, and expired-session rejection."""

    def test_reconnect_reclaims_seats(self, server, client, client2):
        """Client1 reserves → Client1 disconnects → Client2 reclaims the session.

        Client2 reconnects with the same session_id and regains access to
        the reserved seats.
        """
        # Client1 reserves 2 seats
        reserve1 = client.reserve_seat("VIP", 0, 0)
        reserve2 = client.reserve_seat("VIP", 0, 1)

        tx_id = reserve1["transaction_id"]
        session = server.session_manager.get_by_session_id(tx_id)

        assert session is not None
        assert len(session.seats) == 2

        # Client2 reclaims the session (simulating reconnect with same session_id)
        reclaimed = server.session_manager.reclaim_session(
            session.session_id, client2.user_id
        )
        assert reclaimed is not None, "Session reclaim failed"
        assert reclaimed.session_id == session.session_id
        assert reclaimed.user_id == client2.user_id
        assert len(reclaimed.seats) == 2

        # Now client2 can confirm the reservation
        confirm = client2.confirm(reclaimed.session_id)
        assert confirm["status"] == "SUCCESS"

    def test_session_id_reclaim_returns_existing_session(self, server):
        """Direct SessionManager.reclaim_session remaps the session to a new user."""
        # Create session via get_or_create
        session = server.session_manager.get_or_create("user1")
        session_id = session.session_id

        # Reserve a seat so session has data (direct state manipulation)
        with server.mutex_manager.table_and_sections([Section.VIP]):
            server.seat_matrix.seats[Section.VIP][0][0] = SeatState.RESERVED
            session.seats.append((Section.VIP, 0, 0))
            session.reset_ttl()

        # Reclaim to user2
        reclaimed = server.session_manager.reclaim_session(session_id, "user2")
        assert reclaimed is not None
        assert reclaimed.user_id == "user2"
        assert len(reclaimed.seats) == 1
        assert reclaimed.seats[0] == (Section.VIP, 0, 0)

        # Cleanup: release the seat
        server.session_manager.remove("user2")
        with server.seat_matrix.mutex_sections[Section.VIP]:
            server.seat_matrix.seats[Section.VIP][0][0] = SeatState.AVAILABLE

    def test_expired_session_not_reclaimable(self, server, client):
        """An expired session cannot be reclaimed."""
        reserve = client.reserve_seat("PREFERENTIAL", 0, 0)
        tx_id = reserve["transaction_id"]

        session = server.session_manager.get_by_session_id(tx_id)
        assert session is not None

        # Artificially expire the session by aging last_activity
        session.last_activity = time.time() - (RESERVATION_TTL + 10)
        # Force sweep to actually change state to non-ACTIVE
        server.monitor_thread.expire_session(session)

        # Attempt reclaim — should return None (session no longer ACTIVE)
        reclaimed = server.session_manager.reclaim_session(
            session.session_id, "new_user"
        )
        assert reclaimed is None, (
            "Expired session should not be reclaimable"
        )
