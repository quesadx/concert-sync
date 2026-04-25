import socket
import time

import pytest

from src.client.concert_client import ConcertClient, TransactionNotActiveError, TransactionNotFoundError
from src.server.concert_server import ConcertServer
from src.utils.enums import Section, ReservationStatus, SeatState


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


def test_confirm_removes_reservation_after_success(concert_server_instance):
    server, port = concert_server_instance
    client = ConcertClient(host="localhost", port=port)

    reserve_response = client.reserve_seat("VIP", 0, 0)
    tx_id = reserve_response["transaction_id"]

    confirm_response = client.confirm(tx_id)

    assert confirm_response["status"] == "SUCCESS"

    with server.reservation_table.mutex_table:
        assert tx_id not in server.reservation_table.reservations

    assert server.seat_matrix.seats[Section.VIP][0][0] == SeatState.SOLD


def test_cancel_removes_reservation_after_success(concert_server_instance):
    server, port = concert_server_instance
    client = ConcertClient(host="localhost", port=port)

    reserve_response = client.reserve_seat("VIP", 0, 1)
    tx_id = reserve_response["transaction_id"]

    cancel_response = client.cancel(tx_id)

    assert cancel_response["status"] == "SUCCESS"

    with server.reservation_table.mutex_table:
        assert tx_id not in server.reservation_table.reservations

    assert server.seat_matrix.seats[Section.VIP][0][1] == SeatState.AVAILABLE


def test_confirm_fails_after_expiration(concert_server_instance):
    server, port = concert_server_instance
    client = ConcertClient(host="localhost", port=port)

    reserve_response = client.reserve_seat("VIP", 0, 2)
    tx_id = reserve_response["transaction_id"]

    # Force expiration path without waiting full TTL.
    with server.reservation_table.mutex_table:
        reservation = server.reservation_table.reservations[tx_id]
        reservation.timestamp_creation = 0.0

    server.monitor_thread.expire_reservation(tx_id)

    with pytest.raises((TransactionNotActiveError, TransactionNotFoundError)):
        client.confirm(tx_id)

    with server.reservation_table.mutex_table:
        assert tx_id not in server.reservation_table.reservations

    assert server.seat_matrix.seats[Section.VIP][0][2] == SeatState.AVAILABLE
