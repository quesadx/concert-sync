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


if __name__ == "__main__":
    try:
        test_concurrent_reservations()
    except KeyboardInterrupt:
        print("Interrupted by user")