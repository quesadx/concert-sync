"""E2E tests for Phase 1: User ID + Session-Based TTL."""

import json
import socket
import time
import pytest

from src.server.concert_server import ConcertServer
from src.client.concert_client import ConcertClient
from src.utils.config import RESERVATION_TTL


@pytest.fixture
def concert_server():
    """Start concert server for testing on random port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]

    server = ConcertServer(port=port)
    server.start()
    time.sleep(0.5)

    yield type("Server", (), {"port": port, "instance": server})()

    server.stop()


class TestPhase1SessionTTL:
    def test_client_accepts_user_id(self):
        """ConcertClient accepts user_id parameter in __init__."""
        c = ConcertClient(user_id="TestUser")
        assert c.user_id == "TestUser"

    def test_reserve_returns_session_id(self, concert_server):
        """RESERVE with user_id returns a session_id as transaction_id."""
        client = ConcertClient(user_id="TestUser", port=concert_server.port)
        response = client.reserve_seat("VIP", 0, 0)
        assert response["status"] == "SUCCESS"
        assert "transaction_id" in response
        assert len(response["transaction_id"]) > 0

    def test_same_user_gets_same_session_id(self, concert_server):
        """Two RESERVE calls from same user return same session_id."""
        client = ConcertClient(user_id="TestUser", port=concert_server.port)
        r1 = client.reserve_seat("VIP", 0, 0)
        r2 = client.reserve_seat("VIP", 0, 1)
        assert r1["transaction_id"] == r2["transaction_id"]

    def test_ttl_field_in_response(self, concert_server):
        """TTL field equals RESERVATION_TTL."""
        client = ConcertClient(user_id="TestUser", port=concert_server.port)
        response = client.reserve_seat("VIP", 0, 0)
        assert response["ttl"] == RESERVATION_TTL

    def test_query_without_user_id_succeeds(self, concert_server):
        """QUERY and QUERY_SEAT_MAP work without user_id (200, not ERR_INVALID_PAYLOAD)."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(("localhost", concert_server.port))
            query_request = json.dumps({"action": "QUERY"})
            s.send(query_request.encode())
            chunks = []
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            response = json.loads(b"".join(chunks).decode())
        assert response["status"] == "SUCCESS"
        assert "sections" in response
