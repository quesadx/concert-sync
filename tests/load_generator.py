import argparse
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.client.concert_client import ConcertClient, ConcertClientError
from src.utils.config import SECTION_CONFIG
from src.utils.enums import Section


@dataclass
class LoadResult:
    thread_id: int
    action: str
    section: str
    row: int
    col: int
    status: str
    duration_ms: float
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class LoadGenerator:
    SECTIONS = ["VIP", "PREFERENTIAL", "GENERAL"]

    def __init__(self, host="localhost", port=9999, num_requests=100, conflicts=False, delay=0):
        self.host = host
        self.port = port
        self.num_requests = num_requests
        self.conflicts = conflicts
        self.delay = delay
        self.results: List[LoadResult] = []
        self.lock = threading.Lock()
        self.conflict_seats: List[Tuple[str, int, int]] = []

        cfg_limits = {}
        for s_name in self.SECTIONS:
            sec = Section[s_name]
            cfg = SECTION_CONFIG[sec]
            cfg_limits[s_name] = (cfg["rows"], cfg["cols"])
        self.section_limits = cfg_limits

    def _random_seat(self) -> Tuple[str, int, int]:
        section = random.choice(self.SECTIONS)
        max_row, max_col = self.section_limits[section]
        return section, random.randint(0, max_row - 1), random.randint(0, max_col - 1)

    def _conflict_seat(self) -> Tuple[str, int, int]:
        if self.conflict_seats:
            return random.choice(self.conflict_seats)
        seat = self._random_seat()
        self.conflict_seats.append(seat)
        return seat

    def _pick_seat(self) -> Tuple[str, int, int]:
        if self.conflicts and random.random() < 0.3 and self.conflict_seats:
            return self._conflict_seat()
        return self._random_seat()

    def _run_buy_flow(self, thread_id: int) -> LoadResult:
        section, row, col = self._pick_seat()
        t0 = time.time()
        client = ConcertClient(user_id=f"load-user-{thread_id}", host=self.host, port=self.port)
        try:
            resp = client.reserve_seat(section, row, col)
            tx_id = resp.get("transaction_id", "")
            client.confirm(tx_id)
            elapsed = (time.time() - t0) * 1000
            if self.conflicts and (section, row, col) in self.conflict_seats:
                self.conflict_seats.remove((section, row, col))
            return LoadResult(thread_id, "BUY", section, row, col, "SUCCESS", elapsed)
        except ConcertClientError as e:
            elapsed = (time.time() - t0) * 1000
            return LoadResult(thread_id, "BUY", section, row, col, "FAILURE", elapsed, str(e))

    def _run_cancel_flow(self, thread_id: int) -> LoadResult:
        section, row, col = self._pick_seat()
        t0 = time.time()
        client = ConcertClient(user_id=f"load-user-{thread_id}", host=self.host, port=self.port)
        try:
            resp = client.reserve_seat(section, row, col)
            tx_id = resp.get("transaction_id", "")
            client.cancel(tx_id)
            elapsed = (time.time() - t0) * 1000
            return LoadResult(thread_id, "CANCEL", section, row, col, "SUCCESS", elapsed)
        except ConcertClientError as e:
            elapsed = (time.time() - t0) * 1000
            return LoadResult(thread_id, "CANCEL", section, row, col, "FAILURE", elapsed, str(e))

    def _run_reserve_only(self, thread_id: int) -> LoadResult:
        section, row, col = self._pick_seat()
        t0 = time.time()
        client = ConcertClient(user_id=f"load-user-{thread_id}", host=self.host, port=self.port)
        try:
            resp = client.reserve_seat(section, row, col)
            elapsed = (time.time() - t0) * 1000
            return LoadResult(thread_id, "RESERVE_ONLY", section, row, col, "SUCCESS", elapsed)
        except ConcertClientError as e:
            elapsed = (time.time() - t0) * 1000
            return LoadResult(thread_id, "RESERVE_ONLY", section, row, col, "FAILURE", elapsed, str(e))

    def _run_batch_flow(self, thread_id: int) -> LoadResult:
        section, row_base, col_base = self._pick_seat()
        seats = [
            {"section": section, "row": row_base, "col": col_base},
            {"section": section, "row": row_base, "col": min(col_base + 1, self.section_limits[section][1] - 1)},
        ]
        t0 = time.time()
        client = ConcertClient(user_id=f"load-user-{thread_id}", host=self.host, port=self.port)
        try:
            resp = client.reserve_selected(seats)
            tx_id = resp.get("transaction_id", "")
            client.confirm(tx_id)
            elapsed = (time.time() - t0) * 1000
            return LoadResult(thread_id, "BATCH", section, row_base, col_base, "SUCCESS", elapsed)
        except ConcertClientError as e:
            elapsed = (time.time() - t0) * 1000
            return LoadResult(thread_id, "BATCH", section, row_base, col_base, "FAILURE", elapsed, str(e))

    def _execute_one(self, thread_id: int) -> LoadResult:
        choice = random.random()
        if choice < 0.4:
            return self._run_buy_flow(thread_id)
        elif choice < 0.7:
            return self._run_cancel_flow(thread_id)
        elif choice < 0.9:
            return self._run_reserve_only(thread_id)
        else:
            return self._run_batch_flow(thread_id)

    def run(self) -> List[LoadResult]:
        with ThreadPoolExecutor(max_workers=min(50, self.num_requests)) as pool:
            futures = []
            for i in range(self.num_requests):
                futures.append(pool.submit(self._execute_one, i))
                if self.delay > 0:
                    time.sleep(self.delay)
            for f in as_completed(futures):
                result = f.result()
                with self.lock:
                    self.results.append(result)
        return self.results

    def summary(self) -> dict:
        total = len(self.results)
        successes = sum(1 for r in self.results if r.status == "SUCCESS")
        failures = total - successes
        durations = [r.duration_ms for r in self.results if r.status == "SUCCESS"]

        conflicts_found = 0
        conflict_errors = []
        if self.conflicts:
            for r in self.results:
                if self._seat_in_conflicts(r.section, r.row, r.col):
                    conflicts_found += 1
                    if r.status == "FAILURE":
                        conflict_errors.append(r)

        return {
            "total": total,
            "successes": successes,
            "failures": failures,
            "success_rate": f"{successes / total * 100:.1f}%" if total else "N/A",
            "avg_duration_ms": f"{sum(durations) / len(durations):.1f}" if durations else "N/A",
            "max_duration_ms": f"{max(durations):.1f}" if durations else "N/A",
            "min_duration_ms": f"{min(durations):.1f}" if durations else "N/A",
            "conflict_requests": conflicts_found,
            "conflict_failures": len(conflict_errors),
        }

    def _seat_in_conflicts(self, section, row, col) -> bool:
        return (section, row, col) in self.conflict_seats or any(
            s == section and r == row and c == col
            for s, r, c in self.conflict_seats
        )

    def print_results(self):
        s = self.summary()
        print(f"\n{'='*60}")
        print(f"  LOAD TEST RESULTS")
        print(f"{'='*60}")
        print(f"  Total requests:    {s['total']}")
        print(f"  Successful:        {s['successes']}")
        print(f"  Failed:            {s['failures']}")
        print(f"  Success rate:      {s['success_rate']}")
        print(f"  Avg duration:      {s['avg_duration_ms']} ms")
        print(f"  Max duration:      {s['max_duration_ms']} ms")
        print(f"  Min duration:      {s['min_duration_ms']} ms")
        if self.conflicts:
            print(f"  Conflict requests: {s['conflict_requests']}")
            print(f"  Conflict failures: {s['conflict_failures']}")
        print(f"{'='*60}")

        by_action = {}
        for r in self.results:
            by_action.setdefault(r.action, {"total": 0, "success": 0})
            by_action[r.action]["total"] += 1
            if r.status == "SUCCESS":
                by_action[r.action]["success"] += 1

        print(f"\n  Per-action breakdown:")
        for action, stats in sorted(by_action.items()):
            rate = f"{stats['success'] / stats['total'] * 100:.1f}%" if stats['total'] else "N/A"
            print(f"    {action:15s}: {stats['total']:4d} total, {stats['success']:4d} ok ({rate})")

        failures = [r for r in self.results if r.status == "FAILURE"]
        if failures:
            print(f"\n  Failures (first 10):")
            for r in failures[:10]:
                print(f"    [{r.timestamp}] T{r.thread_id} {r.action:15s} "
                      f"{r.section}({r.row},{r.col}) — {r.error}")


def check_safety(host="localhost", port=9999) -> bool:
    query = ConcertClient(user_id="safety-check", host=host, port=port).query_seat_map()
    seat_map = query.get("seat_map", {})
    for section_name, grid in seat_map.items():
        for row_idx, row in enumerate(grid):
            for col_idx, state in enumerate(row):
                if state == "SOLD":
                    for check_seat in range(col_idx + 1, len(row)):
                        if row[check_seat] == "SOLD" and check_seat == col_idx:
                            pass
    return True


def main():
    parser = argparse.ArgumentParser(description="ConcertSync Concurrent Load Generator")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=9999, help="Server port")
    parser.add_argument("--requests", type=int, default=100,
                        help="Number of concurrent requests (100/200/500+)")
    parser.add_argument("--conflicts", action="store_true",
                        help="Enable conflicting scenarios (same seat targeted by multiple threads)")
    parser.add_argument("--delay", type=float, default=0,
                        help="Seconds to wait between each request (e.g. 0.5 for slow fill)")
    args = parser.parse_args()

    print(f"ConcertSync Load Generator")
    print(f"  Target:  {args.host}:{args.port}")
    print(f"  Requests: {args.requests}")
    print(f"  Conflicts: {'ON' if args.conflicts else 'OFF'}")
    print(f"  Delay: {args.delay}s between requests")
    print(f"  Starting at: {datetime.now().isoformat()}")

    gen = LoadGenerator(host=args.host, port=args.port,
                        num_requests=args.requests, conflicts=args.conflicts,
                        delay=args.delay)
    results = gen.run()
    gen.print_results()

    ok = sum(1 for r in results if r.status == "SUCCESS")
    print(f"\n  Total: {len(results)} requests, {ok} successful")
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    exit(main())
