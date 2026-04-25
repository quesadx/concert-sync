import socket
import threading
import time

from src.client.concert_client import ConcertClient, TransactionNotActiveError
from src.server.concert_server import ConcertServer
from src.utils.config import SECTION_CONFIG
from src.utils.enums import ReservationStatus, Section, SeatState


def _vip_capacity():
    cfg = SECTION_CONFIG[Section.VIP]
    return cfg["rows"] * cfg["cols"]


def _run_parallel(expire_fn, client_fn):
    start_barrier = threading.Barrier(3)
    results = {}

    def run_expire():
        start_barrier.wait()
        try:
            expire_fn()
            results["expire"] = "ok"
        except Exception as exc:
            results["expire"] = f"error:{type(exc).__name__}"

    def run_client():
        start_barrier.wait()
        try:
            client_fn()
            results["client"] = "ok"
        except Exception as exc:
            results["client"] = f"error:{type(exc).__name__}"

    t_expire = threading.Thread(target=run_expire)
    t_client = threading.Thread(target=run_client)

    t_expire.start()
    t_client.start()

    start_barrier.wait()
    t_expire.join(timeout=5)
    t_client.join(timeout=5)

    return results


def test_confirm_vs_expire_keeps_consistency():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]

    server = ConcertServer(port=port)
    server.start()
    time.sleep(0.5)

    try:
        client = ConcertClient(host="localhost", port=port)

        reserve_response = client.reserve_seat("VIP", 0, 3)
        tx_id = reserve_response["transaction_id"]

        results = _run_parallel(
            expire_fn=lambda: server.monitor_thread.expire_reservation(tx_id),
            client_fn=lambda: client.confirm(tx_id),
        )

        assert results["expire"] == "ok"
        assert results["client"] in {"ok", f"error:{TransactionNotActiveError.__name__}"}

        seat_state = server.seat_matrix.seats[Section.VIP][0][3]
        semaphore_value = server.semaphore_mgr.s_sections[Section.VIP]._value
        capacity = _vip_capacity()

        if results["client"] == "ok":
            assert seat_state == SeatState.SOLD
            assert semaphore_value == capacity - 1
        else:
            assert seat_state == SeatState.AVAILABLE
            assert semaphore_value == capacity
    finally:
        server.stop()


def test_cancel_vs_expire_releases_once():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]

    server = ConcertServer(port=port)
    server.start()
    time.sleep(0.5)

    try:
        client = ConcertClient(host="localhost", port=port)

        reserve_response = client.reserve_seat("VIP", 0, 4)
        tx_id = reserve_response["transaction_id"]

        results = _run_parallel(
            expire_fn=lambda: server.monitor_thread.expire_reservation(tx_id),
            client_fn=lambda: client.cancel(tx_id),
        )

        assert results["expire"] == "ok"
        # Cancel may win (ok) or lose to expiration (transaction not active).
        assert results["client"] in {"ok", f"error:{TransactionNotActiveError.__name__}"}

        with server.reservation_table.mutex_table:
            assert tx_id not in server.reservation_table.reservations

        seat_state = server.seat_matrix.seats[Section.VIP][0][4]
        semaphore_value = server.semaphore_mgr.s_sections[Section.VIP]._value

        assert seat_state == SeatState.AVAILABLE
        assert semaphore_value == _vip_capacity()
    finally:
        server.stop()
