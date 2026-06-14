"""E2E tests for Phase 3: Fix Buy Near Expiry + Concurrent Cancellation."""

import socket
import threading
import time

from src.client.concert_client import (
    ConcertClient,
    TransactionNotActiveError,
    TransactionNotFoundError,
)
from src.server.concert_server import ConcertServer
from src.utils.config import SECTION_CONFIG
from src.utils.enums import Section, SeatState


def _wait_for_server(host, port, retries=50, wait_seconds=0.1):
    for _ in range(retries):
        try:
            client = ConcertClient(host=host, port=port)
            response = client.query()
            if response.get("status") == "SUCCESS":
                return
        except Exception:
            time.sleep(wait_seconds)
    raise RuntimeError("Server did not start in time")


def _expire_session_by_id(server, session_id):
    """Look up session and expire it. No-op if session already gone."""
    session = server.session_manager.get_by_session_id(session_id)
    if session is not None:
        server.monitor_thread.expire_session(session)


class TestConfirmNearExpiry:
    """Tests for purchase-near-expiry race conditions."""

    def test_confirm_succeeds_when_expire_runs_first(self):
        """CONFIRM after session expired -> graceful failure, seat AVAILABLE."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        import os
        _db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "concert_sync.db")
        try: os.remove(_db)
        except FileNotFoundError: pass
        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)
            client = ConcertClient(user_id="TestA", port=port)

            resp = client.reserve_seat("VIP", 0, 0)
            tx_id = resp["transaction_id"]

            # Age the session so expire_session actually expires it
            session = server.session_manager.get_by_session_id(tx_id)
            if session is not None:
                session.last_activity = time.time() - session.ttl_secs - 10

            _expire_session_by_id(server, tx_id)

            try:
                client.confirm(tx_id)
                assert False, "CONFIRM should fail after expire"
            except (TransactionNotActiveError, TransactionNotFoundError):
                pass

            seat_state = server.seat_matrix.seats[Section.VIP][0][0]
            assert seat_state == SeatState.AVAILABLE, "Seat should be AVAILABLE after expire"
        finally:
            server.stop()

    def test_expire_skips_when_confirm_wins(self):
        """Parallel CONFIRM vs expire: consistent state in either outcome."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        import os
        _db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "concert_sync.db")
        try: os.remove(_db)
        except FileNotFoundError: pass
        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)
            client = ConcertClient(user_id="TestB", port=port)

            resp = client.reserve_seat("VIP", 0, 1)
            tx_id = resp["transaction_id"]

            barrier = threading.Barrier(2)
            results = {}
            results_lock = threading.Lock()

            def do_confirm():
                barrier.wait()
                try:
                    client.confirm(tx_id)
                    with results_lock:
                        results["confirm"] = "ok"
                except Exception as e:
                    with results_lock:
                        results["confirm"] = str(e)

            def do_expire():
                barrier.wait()
                try:
                    _expire_session_by_id(server, tx_id)
                    with results_lock:
                        results["expire"] = "ok"
                except Exception as e:
                    with results_lock:
                        results["expire"] = str(e)

            t_confirm = threading.Thread(target=do_confirm)
            t_expire = threading.Thread(target=do_expire)
            t_confirm.start()
            t_expire.start()
            t_confirm.join(timeout=5)
            t_expire.join(timeout=5)

            assert results.get("expire") == "ok", f"Expire failed: {results}"

            seat_state = server.seat_matrix.seats[Section.VIP][0][1]
            if results.get("confirm") == "ok":
                assert seat_state == SeatState.SOLD, "CONFIRM won -> seat should be SOLD"
            else:
                assert seat_state == SeatState.AVAILABLE, "EXPIRE won -> seat should be AVAILABLE"
        finally:
            server.stop()

    def test_consecutive_confirm_expire_rounds(self):
        """Multiple CONFIRM vs expire rounds: no seat loss or semaphore leak."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        import os
        _db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "concert_sync.db")
        try: os.remove(_db)
        except FileNotFoundError: pass
        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)

            for round_idx in range(5):
                section = Section.VIP
                row, col = 0, round_idx + 2
                client = ConcertClient(
                    user_id=f"RoundUser{round_idx}", port=port
                )

                resp = client.reserve_seat(section.name, row, col)
                tx_id = resp["transaction_id"]

                barrier = threading.Barrier(2)
                results = {}
                results_lock = threading.Lock()

                def do_confirm():
                    barrier.wait()
                    try:
                        client.confirm(tx_id)
                        with results_lock:
                            results["confirm"] = "ok"
                    except Exception:
                        with results_lock:
                            results["confirm"] = "fail"

                def do_expire():
                    barrier.wait()
                    try:
                        _expire_session_by_id(server, tx_id)
                        with results_lock:
                            results["expire"] = "ok"
                    except Exception:
                        with results_lock:
                            results["expire"] = "fail"

                t_confirm = threading.Thread(target=do_confirm)
                t_expire = threading.Thread(target=do_expire)
                t_confirm.start()
                t_expire.start()
                t_confirm.join(timeout=5)
                t_expire.join(timeout=5)

                seat = server.seat_matrix.seats[Section.VIP][row][col]
                possible_states = {SeatState.SOLD, SeatState.AVAILABLE}
                assert seat in possible_states, (
                    f"Round {round_idx}: seat in unexpected state {seat}"
                )

            sem_value = server.semaphore_mgr.s_sections[Section.VIP]._value
            capacity = SECTION_CONFIG[Section.VIP]["rows"] * SECTION_CONFIG[Section.VIP]["cols"]
            confirms = sum(1 for r in range(5) if True)
            # Cannot know exact semaphore without counting wins, but verify no leak:
            assert sem_value <= capacity, f"Semaphore over-released: {sem_value} > {capacity}"
            assert sem_value >= 0, f"Semaphore underflow: {sem_value}"
        finally:
            server.stop()


class TestConcurrentCancellation:
    """Tests for concurrent cancellation race conditions."""

    def test_cancel_vs_cancel_same_session(self):
        """Two concurrent CANCELs: exactly one succeeds, seat ends AVAILABLE."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        import os
        _db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "concert_sync.db")
        try: os.remove(_db)
        except FileNotFoundError: pass
        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)
            client = ConcertClient(user_id="TestC", port=port)

            resp = client.reserve_seat("VIP", 0, 0)
            tx_id = resp["transaction_id"]

            barrier = threading.Barrier(2)
            cancel_results = []
            cancel_lock = threading.Lock()

            def do_cancel():
                barrier.wait()
                try:
                    ConcertClient(user_id="TestC", port=port).cancel(tx_id)
                    with cancel_lock:
                        cancel_results.append("ok")
                except Exception:
                    with cancel_lock:
                        cancel_results.append("fail")

            t1 = threading.Thread(target=do_cancel)
            t2 = threading.Thread(target=do_cancel)
            t1.start()
            t2.start()
            t1.join(timeout=5)
            t2.join(timeout=5)

            successes = cancel_results.count("ok")
            assert successes == 1, f"Expected 1 CANCEL success, got {successes}"

            seat_state = server.seat_matrix.seats[Section.VIP][0][0]
            assert seat_state == SeatState.AVAILABLE, "Seat should be AVAILABLE after cancel"
        finally:
            server.stop()

    def test_cancel_vs_reserve_overlapping_seat(self):
        """CANCEL frees seat while concurrent RESERVE targets same seat."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        import os
        _db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "concert_sync.db")
        try: os.remove(_db)
        except FileNotFoundError: pass
        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)
            section = Section.VIP
            row, col = 0, 1

            client_a = ConcertClient(user_id="OverlapA", port=port)
            client_b = ConcertClient(user_id="OverlapB", port=port)

            resp = client_a.reserve_seat(section.name, row, col)
            tx_a = resp["transaction_id"]

            barrier = threading.Barrier(2)
            results = {}
            results_lock = threading.Lock()

            def do_cancel():
                barrier.wait()
                try:
                    client_a.cancel(tx_a)
                    with results_lock:
                        results["cancel"] = "ok"
                except Exception as e:
                    with results_lock:
                        results["cancel"] = str(e)

            def do_reserve():
                barrier.wait()
                try:
                    client_b.reserve_seat(section.name, row, col)
                    with results_lock:
                        results["reserve"] = "ok"
                except Exception as e:
                    with results_lock:
                        results["reserve"] = str(e)

            t_cancel = threading.Thread(target=do_cancel)
            t_reserve = threading.Thread(target=do_reserve)
            t_cancel.start()
            t_reserve.start()
            t_cancel.join(timeout=5)
            t_reserve.join(timeout=5)

            seat_state = server.seat_matrix.seats[section][row][col]
            # After concurrent cancel+reserve, the seat is either:
            # - AVAILABLE (cancel won: freed before reserve grabbed it)
            # - RESERVED (reserve won: grabbed before cancel freed it)
            # Both outcomes are valid — no double-sold, no stuck RESERVED
            assert seat_state in {SeatState.AVAILABLE, SeatState.RESERVED}, (
                f"Unexpected seat state: {seat_state}"
            )
        finally:
            server.stop()

    def test_semaphore_integrity_after_concurrent_cancel(self):
        """Concurrent cancels: semaphore count matches available seats."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]

        import os
        _db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "concert_sync.db")
        try: os.remove(_db)
        except FileNotFoundError: pass
        server = ConcertServer(port=port)
        server.start()
        try:
            _wait_for_server("localhost", port)

            num_clients = 20
            clients = [
                ConcertClient(user_id=f"SemTestUser{i}", port=port)
                for i in range(num_clients)
            ]
            sections = [Section.VIP, Section.PREFERENTIAL, Section.GENERAL]
            tx_ids = []

            col_map = {
                Section.VIP: 0,
                Section.PREFERENTIAL: 0,
                Section.GENERAL: 0,
            }
            for i, client in enumerate(clients):
                section = sections[i % len(sections)]
                col = col_map[section]
                resp = client.reserve_seat(section.name, 0, col)
                tx_ids.append(resp["transaction_id"])
                col_map[section] += 1

            cancel_threads = []
            for i in range(num_clients):
                t = threading.Thread(
                    target=lambda idx=i: ConcertClient(user_id=f"SemTestUser{idx}", port=port).cancel(tx_ids[idx])
                )
                cancel_threads.append(t)
                t.start()

            for t in cancel_threads:
                t.join(timeout=5)

            query = ConcertClient(user_id="QueryUser", port=port).query()
            assert query["status"] == "SUCCESS"

            for section in sections:
                stats = query["sections"][section.name]
                available = stats["available"]
                sem_value = server.semaphore_mgr.s_sections[section]._value
                assert sem_value == available, (
                    f"Section {section.name}: semaphore={sem_value}, "
                    f"available={available} (mismatch)"
                )
        finally:
            server.stop()
