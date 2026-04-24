import socket
import time

import pytest

from src.client.concert_client import ConcertClient
from src.server.concert_server import ConcertServer
from src.utils.enums import Section


@pytest.fixture
def concert_server_instance():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]

    server = ConcertServer(port=port)
    server.start()
    time.sleep(0.5)

    yield server, port

    server.stop()


def test_query_seat_map_initial_state(concert_server_instance):
    _, port = concert_server_instance
    client = ConcertClient(host="localhost", port=port)

    response = client.query_seat_map()

    assert response["status"] == "SUCCESS"
    seat_map = response["seat_map"]

    for section in Section:
        assert section.name in seat_map
        for row in seat_map[section.name]:
            for seat_state in row:
                assert seat_state == "AVAILABLE"


def test_query_seat_map_reflects_reserve_and_confirm(concert_server_instance):
    _, port = concert_server_instance
    client = ConcertClient(host="localhost", port=port)

    reserve_response = client.reserve_seat("VIP", 0, 0)
    tx_id = reserve_response["transaction_id"]

    seat_map_after_reserve = client.query_seat_map()["seat_map"]
    assert seat_map_after_reserve["VIP"][0][0] == "RESERVED"

    client.confirm(tx_id)
    seat_map_after_confirm = client.query_seat_map()["seat_map"]
    assert seat_map_after_confirm["VIP"][0][0] == "SOLD"


def test_query_seat_map_reflects_cancel(concert_server_instance):
    _, port = concert_server_instance
    client = ConcertClient(host="localhost", port=port)

    reserve_response = client.reserve_seat("PREFERENTIAL", 1, 1)
    tx_id = reserve_response["transaction_id"]

    seat_map_after_reserve = client.query_seat_map()["seat_map"]
    assert seat_map_after_reserve["PREFERENTIAL"][1][1] == "RESERVED"

    client.cancel(tx_id)
    seat_map_after_cancel = client.query_seat_map()["seat_map"]
    assert seat_map_after_cancel["PREFERENTIAL"][1][1] == "AVAILABLE"
