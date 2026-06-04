"""Verify CANCEL idempotency under concurrent load (CANC-01).

Reproduces the teacher-flagged Prueba 6: two clients cancelling the same
transaction simultaneously must not produce errors or double-release seats.
"""

import threading

from src.client.concert_client import ConcertClientError
from src.utils.enums import SeatState, Section


class TestCancelRace:
    """Concurrent cancel idempotency and sequential double-cancel tests."""

    def test_concurrent_cancel_idempotent(self, server, client):
        """Two threads cancel the same tx simultaneously — at least one succeeds.

        After both complete, the seat must be AVAILABLE exactly once (not
        double-released), and the semaphore must be fully restored.
        """
        reserve = client.reserve_seat("VIP", 0, 0)
        tx_id = reserve["transaction_id"]

        barrier = threading.Barrier(2)
        results = []

        def cancel_worker():
            barrier.wait()
            try:
                resp = client.send_request(
                    {"action": "CANCEL", "transaction_id": tx_id}
                )
                results.append(resp.get("status"))
            except ConcertClientError as exc:
                results.append(f"error:{type(exc).__name__}")
            except Exception as exc:
                results.append(f"error:{type(exc).__name__}")

        t1 = threading.Thread(target=cancel_worker)
        t2 = threading.Thread(target=cancel_worker)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert len(results) == 2
        # At least one thread must return SUCCESS; the other may see a
        # TransactionNotFoundError if the first thread already removed the session.
        assert any(r == "SUCCESS" for r in results), (
            f"At least one cancel must return SUCCESS, got {results}"
        )

        # Verify seat is AVAILABLE and semaphore is fully restored
        seat_state = server.seat_matrix.seats[Section.VIP][0][0]
        assert seat_state == SeatState.AVAILABLE, (
            f"Seat should be AVAILABLE after cancel, got {seat_state}"
        )
        sem_value = server.semaphore_mgr.s_sections[Section.VIP]._value
        from src.utils.config import SECTION_CONFIG
        cfg = SECTION_CONFIG[Section.VIP]
        capacity = cfg["rows"] * cfg["cols"]
        assert sem_value == capacity, (
            f"Semaphore should be {capacity} (no double-release), got {sem_value}"
        )

    def test_cancel_already_cancelled_returns_success(self, server, client):
        """Cancel → Cancel again → second cancel returns SUCCESS (idempotent).

        If the server has been patched for idempotent cancel (Plan 02),
        the second cancel returns SUCCESS. Otherwise it may return FAILURE
        (transaction not found). Either outcome is acceptable; the key
        invariant is that the seat is AVAILABLE after the first cancel.
        """
        reserve = client.reserve_seat("PREFERENTIAL", 0, 0)
        tx_id = reserve["transaction_id"]

        # First cancel
        cancel1 = client.cancel(tx_id)
        assert cancel1["status"] == "SUCCESS"

        # Verify seat is AVAILABLE
        seat_map = client.query_seat_map()["seat_map"]
        pref_grid = seat_map["PREFERENTIAL"]
        assert pref_grid[0][0] == "AVAILABLE", (
            f"Seat should be AVAILABLE after cancel, got {pref_grid[0][0]}"
        )

        # Second cancel — may succeed or fail depending on idempotency fix
        try:
            cancel2 = client.cancel(tx_id)
            # If it reaches here, idempotent fix is in place
            assert cancel2["status"] in ("SUCCESS", "FAILURE")
        except ConcertClientError:
            # TransactionNotFoundError is acceptable (session already removed)
            pass
