"""Validate the Plan 02 TTL expiration race fix (EXPR-01, EXPR-02 — Prueba 3).

Reproduces the exact race condition where TTL expiration competes with CONFIRM:
- ``handle_confirm`` now snapshots ``seats_by_section`` INSIDE the
  ``table_and_sections`` lock (line 482 of transactional_thread.py), closing
  the TOCTOU window identified by the teacher.

Uses artificially-aged sessions to simulate short TTLs without monkeypatching
module-level constants.
"""

import threading
import time

import pytest

from src.client.concert_client import ConcertClientError
from src.utils.config import RESERVATION_TTL
from src.utils.enums import SeatState, Section


def _vip_capacity():
    """Return total VIP seat count."""
    from src.utils.config import SECTION_CONFIG
    cfg = SECTION_CONFIG[Section.VIP]
    return cfg["rows"] * cfg["cols"]


class TestTTLExpirationRace:
    """Focused reproduction of the TTL-expiration-vs-CONFIRM race."""

    def test_concurrent_confirm_and_expire_aged_session(self, server, client):
        """Thread A confirms, Thread B expires an artificially-aged session.

        After both complete, the seat is either SOLD (confirm won) or
        AVAILABLE (expire won) — never both, never stuck RESERVED.
        """
        reserve = client.reserve_seat("VIP", 0, 0)
        tx_id = reserve["transaction_id"]

        # Artificially age the session to force near-term expiry
        session = server.session_manager.get_by_session_id(tx_id)
        assert session is not None
        aged = time.time() - (RESERVATION_TTL + 1)
        session.last_activity = aged
        for seat_key in list(session.seat_timestamps.keys()):
            session.seat_timestamps[seat_key] = aged

        barrier = threading.Barrier(2)
        results = {}

        def expire_worker():
            barrier.wait()
            try:
                s = server.session_manager.get_by_session_id(tx_id)
                if s is not None:
                    server.monitor_thread.expire_session(s)
                results["expire"] = "ok"
            except Exception as exc:
                results["expire"] = f"error:{type(exc).__name__}"

        def confirm_worker():
            barrier.wait()
            try:
                client.confirm(tx_id)
                results["confirm"] = "ok"
            except ConcertClientError as exc:
                results["confirm"] = f"error:{type(exc).__name__}"
            except Exception as exc:
                results["confirm"] = f"error:{type(exc).__name__}"

        t_exp = threading.Thread(target=expire_worker)
        t_conf = threading.Thread(target=confirm_worker)
        t_exp.start()
        t_conf.start()
        t_exp.join(timeout=5)
        t_conf.join(timeout=5)

        assert results.get("expire") == "ok"

        seat_state = server.seat_matrix.seats[Section.VIP][0][0]
        sem_value = server.semaphore_mgr.s_sections[Section.VIP]._value
        capacity = _vip_capacity()

        if results["confirm"] == "ok":
            assert seat_state == SeatState.SOLD, (
                f"Confirm won — seat must be SOLD, got {seat_state}"
            )
            assert sem_value == capacity - 1, (
                f"Semaphore should be {capacity - 1} after SOLD, got {sem_value}"
            )
        else:
            assert seat_state == SeatState.AVAILABLE, (
                f"Expire won — seat must be AVAILABLE, got {seat_state}"
            )
            assert sem_value == capacity, (
                f"Semaphore should be {capacity} after expire, got {sem_value}"
            )

    def test_expire_then_confirm_returns_failure(self, server, client):
        """Reserve → expire → confirm MUST return FAILURE (not crash or ERROR).

        Validates that the server correctly rejects confirm on an expired
        transaction and the seat is AVAILABLE.
        """
        reserve = client.reserve_seat("VIP", 0, 1)
        tx_id = reserve["transaction_id"]

        # Artificially age past TTL
        session = server.session_manager.get_by_session_id(tx_id)
        assert session is not None
        aged = time.time() - (RESERVATION_TTL + 10)
        session.last_activity = aged
        for seat_key in list(session.seat_timestamps.keys()):
            session.seat_timestamps[seat_key] = aged

        # Let MonitorThread sweep (runs every 1s)
        time.sleep(1.5)

        # Confirm should now fail — session is either gone or not ACTIVE
        try:
            client.confirm(tx_id)
            pytest.fail("Expected confirm on expired session to raise an error")
        except ConcertClientError:
            pass  # Expected

        seat_state = server.seat_matrix.seats[Section.VIP][0][1]
        assert seat_state == SeatState.AVAILABLE, (
            f"Expired seat must be AVAILABLE, got {seat_state}"
        )

    def test_confirm_before_expire_no_double_release(self, server, client):
        """Confirm BEFORE expire → seat stays SOLD, semaphore NOT double-released.

        The Plan 02 fix ensures that when CONFIRM transitions the seat to
        SOLD inside the lock, the subsequent expiration sweep sees the
        non-ACTIVE state and does NOT re-release the seat.
        """
        reserve = client.reserve_seat("VIP", 0, 2)
        tx_id = reserve["transaction_id"]

        # Immediately confirm (before any expiration)
        confirm_resp = client.confirm(tx_id)
        assert confirm_resp["status"] == "SUCCESS"

        # Now artificially age the session and run expiration sweep
        session = server.session_manager.get_by_session_id(tx_id)
        if session is not None:
            aged = time.time() - (RESERVATION_TTL + 10)
            session.last_activity = aged
            for seat_key in list(session.seat_timestamps.keys()):
                session.seat_timestamps[seat_key] = aged

        # Trigger sweep — should be a no-op for the already-confirmed seat
        time.sleep(1.5)

        seat_state = server.seat_matrix.seats[Section.VIP][0][2]
        sem_value = server.semaphore_mgr.s_sections[Section.VIP]._value
        capacity = _vip_capacity()

        assert seat_state == SeatState.SOLD, (
            f"Seat must still be SOLD after confirm+expire, got {seat_state}"
        )
        assert sem_value == capacity - 1, (
            f"Semaphore must remain {capacity - 1} (no double-release), got {sem_value}"
        )
