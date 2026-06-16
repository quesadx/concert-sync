"""Verify that the ConcertClient (used by PySide6) correctly drives all
JSON-over-TCP protocol actions (FRNT-01).

Tests cover every action defined in the protocol contract v1.0:
RESERVE, RESERVE_BATCH, CONFIRM, CANCEL, QUERY, and QUERY_SEAT_MAP.
"""

import pytest

from src.client.concert_client import ConcertClientError
from src.utils.enums import Section


class TestPySide6ProtocolCompliance:
    """End-to-end protocol compliance via ConcertClient.

    Every test goes through the same TCP path the PySide6 frontend uses,
    ensuring that server responses match the protocol contract.
    """

    # ------------------------------------------------------------------
    # RESERVE — single seat
    # ------------------------------------------------------------------

    def test_reserve_seat_success(self, client):
        """Reserve VIP(0,0) returns SUCCESS with transaction_id and ttl > 0."""
        response = client.reserve_seat("VIP", 0, 0)
        assert response["status"] == "SUCCESS"
        assert "transaction_id" in response
        assert response["ttl"] > 0

    # ------------------------------------------------------------------
    # CONFIRM
    # ------------------------------------------------------------------

    def test_confirm_success(self, client):
        """Reserve → confirm makes the seat SOLD/OWN_SOLD in the seat map."""
        reserve_resp = client.reserve_seat("VIP", 0, 0)
        tx_id = reserve_resp["transaction_id"]

        confirm_resp = client.confirm(tx_id)
        assert confirm_resp["status"] == "SUCCESS"

        seat_map = client.query_seat_map()["seat_map"]
        vip_grid = seat_map["VIP"]
        assert vip_grid[0][0] == "OWN_SOLD", (
            "Seat should be OWN_SOLD for the purchasing user after confirm, got: "
            + vip_grid[0][0]
        )

    # ------------------------------------------------------------------
    # CANCEL
    # ------------------------------------------------------------------

    def test_cancel_success(self, client):
        """Reserve → cancel makes the seat AVAILABLE again."""
        reserve_resp = client.reserve_seat("PREFERENTIAL", 0, 0)
        tx_id = reserve_resp["transaction_id"]

        cancel_resp = client.cancel(tx_id)
        assert cancel_resp["status"] == "SUCCESS"

        seat_map = client.query_seat_map()["seat_map"]
        pref_grid = seat_map["PREFERENTIAL"]
        assert pref_grid[0][0] == "AVAILABLE", (
            "Seat should be AVAILABLE after cancel, got: " + pref_grid[0][0]
        )

    # ------------------------------------------------------------------
    # QUERY
    # ------------------------------------------------------------------

    def test_query_returns_sections(self, client):
        """QUERY returns a ``sections`` dict with VIP/PREFERENTIAL/GENERAL keys."""
        response = client.query()
        assert response["status"] == "SUCCESS"
        sections = response["sections"]
        for key in ("VIP", "PREFERENTIAL", "GENERAL"):
            assert key in sections, f"QUERY response missing section '{key}'"

    # ------------------------------------------------------------------
    # QUERY_SEAT_MAP
    # ------------------------------------------------------------------

    def test_query_seat_map_returns_grid(self, client):
        """QUERY_SEAT_MAP returns a ``seat_map`` dict with grid data."""
        response = client.query_seat_map()
        assert response["status"] == "SUCCESS"
        seat_map = response["seat_map"]
        # VIP is 5 rows x 10 cols
        assert len(seat_map["VIP"]) == 5
        assert len(seat_map["VIP"][0]) == 10

    # ------------------------------------------------------------------
    # RESERVE_BATCH
    # ------------------------------------------------------------------

    def test_reserve_batch_success(self, client):
        """RESERVE_BATCH can reserve two seats in the same section."""
        seats = [
            {"section": "VIP", "row": 1, "col": 0},
            {"section": "VIP", "row": 1, "col": 1},
        ]
        response = client.send_request({"action": "RESERVE_BATCH", "seats": seats})
        assert response["status"] == "SUCCESS"
        assert "transaction_id" in response
        assert len(response.get("reserved_seats", [])) == 2

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_invalid_section_returns_error(self, client):
        """Reserving with an unknown section must raise ConcertClientError."""
        with pytest.raises(ConcertClientError):
            client.reserve_seat("INVALID", 0, 0)
