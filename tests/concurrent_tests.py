import threading
import time

def test_concurrent_reservations():
    results = []

    def reserve_attempt(client_id):
        client = ConcertClient()
        response = client.reserve_seat("VIP", 0, 0)
        results.append((client_id, response))

    threads = []
    for i in range(10):
        t = threading.Thread(target=reserve_attempt, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    successes = [r for r in results if r[1]["status"] == "SUCCESS"]
    assert len(successes) == 1, "Safety violation: double reservation!"
    print("✓ Test passed: No double reservation")

if __name__ == "__main__":
    test_concurrent_reservations()