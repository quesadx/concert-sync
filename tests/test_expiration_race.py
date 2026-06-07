"""Verify TTL expiration correctness under concurrent load (EXPR-01, EXPR-02).

Reproduces the teacher-flagged Prueba 3: TTL expiration racing with CONFIRM
must never produce double-sold seats or stuck RESERVED state.
"""

import threading
import time

from src.client.concert_client import ConcertClientError
from src.utils.config import SECTION_CONFIG, RESERVATION_TTL
from src.utils.enums import Section, SeatState


def _vip_capacity():
    """Return total VIP seat count from SECTION_CONFIG."""
    cfg = SECTION_CONFIG[Section.VIP]
    return cfg["rows"] * cfg["cols"]


class TestExpirationRace:
    """Concurrent expire+confirm and semaphore consistency tests."""

    def test_concurrent_expire_and_confirm(self, server, client):
        """Expire + Confirm in parallel → seat is SOLD or AVAILABLE, NEVER both.

        Two threads synchronize via Barrier: Thread A expires the session,
        Thread B confirms. After both complete, the seat must be in a
        consistent state with correct semaphore count.
        """
        reserve = client.reserve_seat("VIP", 0, 0)
        tx_id = reserve["transaction_id"]

        barrier = threading.Barrier(2)
        results = {}

        def expire_worker():
            barrier.wait()
            try:
                session = server.session_manager.get_by_session_id(tx_id)
                if session is not None:
                    server.monitor_thread.expire_session(session)
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
        # Confirm may succeed (seat SOLD) or fail (transaction not active — expired first)
        assert results.get("confirm") in {
            "ok",
            "error:TransactionNotActiveError",
            "error:TransactionNotFoundError",
        }

        seat_state = server.seat_matrix.seats[Section.VIP][0][0]
        sem_value = server.semaphore_mgr.s_sections[Section.VIP]._value
        capacity = _vip_capacity()

        if results["confirm"] == "ok":
            assert seat_state == SeatState.SOLD, f"Expected SOLD, got {seat_state}"
            assert sem_value == capacity - 1, (
                f"Semaphore should be {capacity - 1} after SOLD, got {sem_value}"
            )
        else:
            assert seat_state == SeatState.AVAILABLE, (
                f"Expected AVAILABLE after expire, got {seat_state}"
            )
            assert sem_value == capacity, (
                f"Semaphore should be {capacity} after expire, got {sem_value}"
            )

    def test_expire_during_transaction(self, server, client):
        """Reserve → sleep past TTL boundary → attempt confirm → consistent state."""
        reserve = client.reserve_seat("VIP", 0, 1)
        tx_id = reserve["transaction_id"]

        # Artificially age the session to force immediate expiry
        session = server.session_manager.get_by_session_id(tx_id)
        if session is not None:
            session.last_activity = time.time() - (RESERVATION_TTL + 10)

        # Allow MonitorThread to sweep (runs every 1s)
        time.sleep(1.5)

        # Confirm should fail — session is expired
        try:
            client.confirm(tx_id)
            # If confirm somehow succeeded, check state
        except ConcertClientError:
            pass  # Expected — TransactionNotActiveError

        seat_state = server.seat_matrix.seats[Section.VIP][0][1]
        assert seat_state in (SeatState.AVAILABLE, SeatState.SOLD), (
            f"Seat must be AVAILABLE or SOLD, got {seat_state}"
        )

    def test_expiration_releases_semaphore(self, server, client):
        """Reserve → let session expire → semaphore restored, seat AVAILABLE."""
        reserve = client.reserve_seat("VIP", 0, 2)
        tx_id = reserve["transaction_id"]

        # Artificially age the session to force expiry
        session = server.session_manager.get_by_session_id(tx_id)
        if session is not None:
            session.last_activity = time.time() - (RESERVATION_TTL + 10)

        # Let MonitorThread sweep
        time.sleep(1.5)

        seat_state = server.seat_matrix.seats[Section.VIP][0][2]
        sem_value = server.semaphore_mgr.s_sections[Section.VIP]._value
        capacity = _vip_capacity()

        assert seat_state == SeatState.AVAILABLE, (
            f"Seat should be AVAILABLE after expire, got {seat_state}"
        )
        assert sem_value == capacity, (
            f"Semaphore should be {capacity} after expire, got {sem_value}"
        )
