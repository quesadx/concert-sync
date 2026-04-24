import socket
import time

import pytest

from src.client.concert_client import ConcertClient, TransactionNotActiveError
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


def test_confirm_is_idempotent(concert_server_instance):
    server, port = concert_server_instance
    client = ConcertClient(host="localhost", port=port)

    reserve_response = client.reserve_seat("VIP", 0, 0)
    tx_id = reserve_response["transaction_id"]

    first_confirm = client.confirm(tx_id)
    second_confirm = client.confirm(tx_id)

    assert first_confirm["status"] == "SUCCESS"
    assert second_confirm["status"] == "SUCCESS"

    with server.reservation_table.mutex_table:
        reservation = server.reservation_table.reservations[tx_id]
        assert reservation.state == ReservationStatus.CONFIRMED

    assert server.seat_matrix.seats[Section.VIP][0][0] == SeatState.SOLD


def test_cancel_is_idempotent(concert_server_instance):
    server, port = concert_server_instance
    client = ConcertClient(host="localhost", port=port)

    reserve_response = client.reserve_seat("VIP", 0, 1)
    tx_id = reserve_response["transaction_id"]

    first_cancel = client.cancel(tx_id)
    second_cancel = client.cancel(tx_id)

    assert first_cancel["status"] == "SUCCESS"
    assert second_cancel["status"] == "SUCCESS"

    with server.reservation_table.mutex_table:
        reservation = server.reservation_table.reservations[tx_id]
        assert reservation.state == ReservationStatus.CANCELLED

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

    with pytest.raises(TransactionNotActiveError):
        client.confirm(tx_id)

    with server.reservation_table.mutex_table:
        reservation = server.reservation_table.reservations[tx_id]
        assert reservation.state == ReservationStatus.EXPIRED

    assert server.seat_matrix.seats[Section.VIP][0][2] == SeatState.AVAILABLE
