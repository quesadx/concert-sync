import random
import threading
import time
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.client.concert_client import ConcertClient
from src.server.concert_server import ConcertServer
from src.utils.enums import Section
from src.utils.config import SECTION_CONFIG


ITERATIONS = 50
THREADS_PER_SECTION = 10


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


def _check_invariants(server, query_response):
    """
    Verify invariants from QUERY response.
    
    Note: QUERY no longer returns "total" field (protocol-contract-v1 compliance).
    We calculate total implicitly: total = available + reserved + sold.
    """
    assert query_response["status"] == "SUCCESS"

    for section in Section:
        section_stats = query_response["sections"][section.name]

        available = section_stats["available"]
        reserved = section_stats["reserved"]
        sold = section_stats["sold"]
        
        # Calculate total implicitly (not in response)
        total = available + reserved + sold

        # Verify accounting invariant
        config = SECTION_CONFIG.get(section, {})
        capacity = config.get("rows", 0) * config.get("cols", 0)
        assert total == capacity, (
            f"Invariant broken in {section.name}: "
            f"available({available}) + reserved({reserved}) + sold({sold}) = {total}, "
            f"expected capacity {capacity}"
        )

        # Verify semaphore consistency (must match available count)
        semaphore_available = server.semaphore_mgr.s_sections[section]._value
        assert semaphore_available == available, (
            f"Invariant broken in {section.name}: semaphore={semaphore_available},"
            f" available={available}"
        )


def test_concurrent_reservations(iterations=ITERATIONS, threads_per_section=THREADS_PER_SECTION):
    host = "localhost"
    port = random.randint(12000, 18000)

    server = ConcertServer(host=host, port=port)
    server.start()

    try:
        _wait_for_server(host, port)

        total_reserve_successes = 0
        total_confirms = 0
        total_cancels = 0

        for iteration in range(iterations):
            all_results = []
            result_lock = threading.Lock()

            def reserve_attempt(section_name, row, col):
                client = ConcertClient(host=host, port=port)
                try:
                    response = client.reserve_seat(section_name, row, col)
                except Exception as e:
                    response = {"status": "ERROR", "message": str(e)}
                with result_lock:
                    all_results.append((section_name, row, col, response))

            threads = []
            seat_by_section = {}

            for section in Section:
                rows = len(server.seat_matrix.seats[section])
                cols = len(server.seat_matrix.seats[section][0])
                capacity = rows * cols

                if iteration >= capacity:
                    raise ValueError(
                        f"iterations={iterations} exceeds capacity={capacity} "
                        f"for section {section.name}; increase capacity or lower iterations"
                    )

                row = iteration // cols
                col = iteration % cols
                seat_by_section[section.name] = (row, col)

                for _ in range(threads_per_section):
                    thread = threading.Thread(
                        target=reserve_attempt,
                        args=(section.name, row, col),
                    )
                    threads.append(thread)
                    thread.start()

            for thread in threads:
                thread.join()

            for section_name in seat_by_section:
                section_results = [
                    entry for entry in all_results if entry[0] == section_name
                ]
                successes = [entry for entry in section_results if entry[3]["status"] == "SUCCESS"]
                assert len(successes) == 1, (
                    f"Safety violation in {section_name}, iteration {iteration}:"
                    f" expected 1 success, got {len(successes)}."
                    f" results={section_results}"
                )

                total_reserve_successes += 1

                tx_id = successes[0][3]["transaction_id"]
                client = ConcertClient(host=host, port=port)

                if iteration % 5 == 0:
                    confirm_response = client.confirm(tx_id)
                    assert confirm_response["status"] == "SUCCESS"
                    total_confirms += 1
                else:
                    cancel_response = client.cancel(tx_id)
                    assert cancel_response["status"] == "SUCCESS"
                    total_cancels += 1

            query_response = ConcertClient(host=host, port=port).query()
            _check_invariants(server, query_response)

            if (iteration + 1) % 10 == 0:
                print(f"Progress: {iteration + 1}/{iterations} iterations", flush=True)

        final_query = ConcertClient(host=host, port=port).query()
        _check_invariants(server, final_query)

        print("Concurrent stress test completed")
        print(f"Iterations: {iterations}")
        print(f"Threads per section: {threads_per_section}")
        print(f"Successful reservations: {total_reserve_successes}")
        print(f"Confirmed transactions: {total_confirms}")
        print(f"Cancelled transactions: {total_cancels}")
    finally:
        server.stop()


def test_expiration_releases_seats_under_concurrent_reserve(num_clients=5):
    """
    Verify that expiration releases all seats under concurrent RESERVE load.

    Uses threading.Barrier to synchronize concurrent reservation attempts,
    then forces all sessions to expire (TTL=2, last_activity set to past) and
    verifies MonitorThread releases all seats and restores semaphore counts.
    """
    import threading
    import time

    host = "localhost"
    port = random.randint(12000, 18000)

    server = ConcertServer(host=host, port=port)
    server.start()

    try:
        _wait_for_server(host, port)

        # Create clients with unique user IDs
        clients = [
            ConcertClient(user_id=f"stress_user_{i}", port=port)
            for i in range(num_clients)
        ]

        # Pre-compute seat assignments (spread across sections)
        all_sections = list(Section)
        seat_assignments = []
        for i in range(num_clients):
            section = all_sections[i % len(all_sections)]
            cols = SECTION_CONFIG.get(section, {}).get("cols", 10)
            num_seats = (i % 3) + 1  # 1, 2, or 3 seats per user
            seats = [(section, 0, j) for j in range(min(num_seats, cols))]
            seat_assignments.append(seats)

        barrier = threading.Barrier(num_clients)
        results_lock = threading.Lock()
        reservation_results = []

        def reserve_all(cl, seats, br):
            br.wait()
            for section, row, col in seats:
                try:
                    cl.reserve_seat(section.name, row, col)
                    with results_lock:
                        reservation_results.append((cl.user_id, section.name, row, col, "SUCCESS"))
                except Exception as e:
                    with results_lock:
                        reservation_results.append((cl.user_id, section.name, row, col, str(e)))

        threads = []
        for i in range(num_clients):
            t = threading.Thread(
                target=reserve_all,
                args=(clients[i], seat_assignments[i], barrier),
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Force all sessions to expire immediately by setting TTL=2 and
        # pushing last_activity into the past. This exercises the real
        # MonitorThread path (poll + expire_session + seat release).
        for session in server.session_manager._sessions.values():
            session.ttl_secs = 2
            aged = time.time() - 3
            session.last_activity = aged
            for seat_key in list(session.seat_timestamps.keys()):
                session.seat_timestamps[seat_key] = aged

        # Wait for MonitorThread to poll and expire sessions (poll=1s, 4s safe margin)
        time.sleep(4)

        # Verify invariants first (capacity + semaphore checks)
        query_response = ConcertClient(host=host, port=port).query()
        _check_invariants(server, query_response)

        # Assert no leaked RESERVED seats
        for section in Section:
            stats = query_response["sections"][section.name]
            assert stats["reserved"] == 0, (
                f"Section {section.name} has {stats['reserved']} RESERVED seats "
                f"after expiration (expected 0)"
            )

        # Assert semaphore counts restored to full capacity
        for section in Section:
            config = SECTION_CONFIG.get(section, {})
            capacity = config.get("rows", 0) * config.get("cols", 0)
            sem_value = server.semaphore_mgr.s_sections[section]._value
            assert sem_value == capacity, (
                f"Semaphore for {section.name} has value {sem_value}, "
                f"expected {capacity} (not restored after expiry)"
            )

        successes = sum(1 for r in reservation_results if r[4] == "SUCCESS")
        total = len(reservation_results)
        print(
            f"Expiration stress test: num_clients={num_clients}, "
            f"reservations={total}, successes={successes}"
        )

    finally:
        server.stop()


def test_concurrent_cancel_and_expire(num_clients=12):
    """
    Stress test: concurrent CANCEL vs expire, CANCEL vs RESERVE.

    Phase A: Concurrent CANCEL + expire for the same sessions.
    Phase B: Concurrent CANCEL + RESERVE for overlapping seats.
    Verifies no seat loss, no semaphore leaks, no double-booking.
    """
    host = "localhost"
    port = random.randint(12000, 18000)

    server = ConcertServer(host=host, port=port)
    server.start()

    try:
        _wait_for_server(host, port)

        sections = list(Section)

        # Phase A: CANCEL vs expire for same sessions
        # Reserve N seats (1 per client), then half cancel + half expire concurrently
        clients_a = [ConcertClient(user_id=f"cancel_expire_{i}", port=port) for i in range(num_clients)]
        tx_ids_a = []

        for i, client in enumerate(clients_a):
            section = sections[i % len(sections)]
            resp = client.reserve_seat(section.name, 0, 0)
            tx_ids_a.append(resp["transaction_id"])

        cancel_indices = set(range(0, num_clients, 2))
        barrier_a = threading.Barrier(num_clients)
        results_a = []
        results_a_lock = threading.Lock()

        def cancel_or_expire(i):
            barrier_a.wait()
            try:
                if i in cancel_indices:
                    clients_a[i].cancel(tx_ids_a[i])
                    with results_a_lock:
                        results_a.append(("cancel", i, "ok"))
                else:
                    session = server.session_manager.get_by_session_id(tx_ids_a[i])
                    if session:
                        server.monitor_thread.expire_session(session)
                    with results_a_lock:
                        results_a.append(("expire", i, "ok"))
            except Exception as e:
                with results_a_lock:
                    results_a.append(("cancel_or_expire", i, str(e)))

        threads_a = [threading.Thread(target=cancel_or_expire, args=(i,)) for i in range(num_clients)]
        for t in threads_a:
            t.start()
        for t in threads_a:
            t.join()

        # Verify Phase A: all seats AVAILABLE
        query_a = ConcertClient(port=port).query()
        _check_invariants(server, query_a)
        for section in sections:
            stats = query_a["sections"][section.name]
            available = stats["available"]
            cfg = SECTION_CONFIG.get(section, {})
            capacity = cfg.get("rows", 0) * cfg.get("cols", 0)
            assert available == capacity, (
                f"Phase A: Section {section.name} has {available} available, "
                f"expected {capacity} (seats not fully released)"
            )

        # Phase B: Concurrent CANCEL + RESERVE for overlapping seats
        # User A reserves, User B tries to reserve same seat while A cancels
        num_rounds = 20
        for round_idx in range(num_rounds):
            section = sections[round_idx % len(sections)]
            row = round_idx // 5
            col = 0

            client_a = ConcertClient(user_id=f"overlap_A_{round_idx}", port=port)
            client_b = ConcertClient(user_id=f"overlap_B_{round_idx}", port=port)

            resp = client_a.reserve_seat(section.name, row, col)
            tx_a = resp["transaction_id"]

            barrier_b = threading.Barrier(2)
            phase_b_results = {}
            phase_b_lock = threading.Lock()

            def do_cancel():
                barrier_b.wait()
                try:
                    client_a.cancel(tx_a)
                    with phase_b_lock:
                        phase_b_results["cancel"] = "ok"
                except Exception as e:
                    with phase_b_lock:
                        phase_b_results["cancel"] = str(e)

            def do_reserve():
                barrier_b.wait()
                try:
                    client_b.reserve_seat(section.name, row, col)
                    with phase_b_lock:
                        phase_b_results["reserve"] = "ok"
                except Exception as e:
                    with phase_b_lock:
                        phase_b_results["reserve"] = str(e)

            t_cancel = threading.Thread(target=do_cancel)
            t_reserve = threading.Thread(target=do_reserve)
            t_cancel.start()
            t_reserve.start()
            t_cancel.join(timeout=5)
            t_reserve.join(timeout=5)

            # Verify Phase B round: no double-booking, no RESERVED leak
            query_b = ConcertClient(port=port).query()
            section_stats = query_b["sections"][section.name]
            reserved = section_stats["reserved"]
            available = section_stats["available"]
            sold = section_stats["sold"]

            assert reserved <= 1, (
                f"Phase B round {round_idx}: {reserved} RESERVED seats "
                f"(expected 0 or 1)"
            )
            assert sold == 0, (
                f"Phase B round {round_idx}: {sold} SOLD seats (expected 0)"
            )

        # Final invariants
        final_query = ConcertClient(port=port).query()
        _check_invariants(server, final_query)

        total_reserved = sum(
            final_query["sections"][s.name]["reserved"] for s in sections
        )
        assert total_reserved == 0, (
            f"Final: {total_reserved} RESERVED seats remain (expected 0)"
        )

        print(
            f"Concurrent cancel/expire stress test: "
            f"clients={num_clients}, overlap_rounds={num_rounds}"
        )

    finally:
        server.stop()


if __name__ == "__main__":
    try:
        test_concurrent_reservations()
        test_expiration_releases_seats_under_concurrent_reserve()
        test_concurrent_cancel_and_expire()
    except KeyboardInterrupt:
        print("Interrupted by user")