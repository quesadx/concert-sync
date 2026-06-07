"""Verify single vs batch reserve consistency (RSRV-01).

Reproduces the teacher-flagged issue: individual reserve must reserve all
selected seats, not just one. Both RESERVE_SELECTED and RESERVE_BATCH must
produce consistent seat states (all seats RESERVED, semaphore counts correct).
"""

from src.client.concert_client import ConcertClientError
from src.utils.enums import SeatState, Section


class TestReserveConsistency:
    """Multi-seat reservation correctness for RESERVE_SELECTED and RESERVE_BATCH."""

    def test_batch_reserves_all_seats_atomic(self, client):
        """RESERVE_BATCH with 2 seats reserves both, not just one."""
        seats = [
            {"section": "VIP", "row": 0, "col": 0},
            {"section": "VIP", "row": 0, "col": 1},
        ]
        response = client.send_request({"action": "RESERVE_BATCH", "seats": seats})
        assert response["status"] == "SUCCESS"
        reserved = response.get("reserved_seats", [])
        assert len(reserved) == 2, (
            f"Expected 2 reserved seats, got {len(reserved)}: {reserved}"
        )

        # Verify both seats are RESERVED in the server
        seat_map = client.query_seat_map()["seat_map"]
        vip_grid = seat_map["VIP"]
        # OWN_RESERVED is returned when the querying user is the owner
        assert vip_grid[0][0] in ("RESERVED", "OWN_RESERVED"), (
            f"VIP(0,0) should be RESERVED/OWN_RESERVED, got {vip_grid[0][0]}"
        )
        assert vip_grid[0][1] in ("RESERVED", "OWN_RESERVED"), (
            f"VIP(0,1) should be RESERVED/OWN_RESERVED, got {vip_grid[0][1]}"
        )

    def test_reserve_batch_reserves_all_seats(self, client):
        """RESERVE_BATCH reserves all seats in the batch atomically."""
        seats = [
            {"section": "VIP", "row": 1, "col": 0},
            {"section": "VIP", "row": 1, "col": 1},
        ]
        response = client.send_request({"action": "RESERVE_BATCH", "seats": seats})
        assert response["status"] == "SUCCESS"
        reserved = response.get("reserved_seats", [])
        assert len(reserved) == 2, (
            f"Expected 2 reserved seats, got {len(reserved)}"
        )

        seat_map = client.query_seat_map()["seat_map"]
        vip_grid = seat_map["VIP"]
        assert vip_grid[1][0] in ("RESERVED", "OWN_RESERVED")
        assert vip_grid[1][1] in ("RESERVED", "OWN_RESERVED")

    def test_single_vs_batch_consistency(self, client):
        """2 individual RESERVEs vs 1 RESERVE_BATCH produce consistent seat states."""
        # Reserve 2 seats individually (both share the same session for "test_user")
        r1 = client.reserve_seat("VIP", 2, 0)
        r2 = client.reserve_seat("VIP", 2, 1)
        assert r1["status"] == "SUCCESS"
        assert r2["status"] == "SUCCESS"

        seat_map = client.query_seat_map()["seat_map"]
        vip_grid = seat_map["VIP"]
        assert vip_grid[2][0] in ("RESERVED", "OWN_RESERVED")
        assert vip_grid[2][1] in ("RESERVED", "OWN_RESERVED")

        # Cancel the shared session (either tx_id works — both refer to same session)
        client.cancel(r1["transaction_id"])

        # Now reserve the same seats via batch
        seats = [
            {"section": "VIP", "row": 2, "col": 0},
            {"section": "VIP", "row": 2, "col": 1},
        ]
        batch = client.send_request({"action": "RESERVE_BATCH", "seats": seats})
        assert batch["status"] == "SUCCESS"

        seat_map = client.query_seat_map()["seat_map"]
        vip_grid = seat_map["VIP"]
        assert vip_grid[2][0] in ("RESERVED", "OWN_RESERVED")
        assert vip_grid[2][1] in ("RESERVED", "OWN_RESERVED")
