# Testing Patterns

**Analysis Date:** 2026-06-01

## Test Framework

**Runner:**
- pytest >=9.0.3
- Config: `[tool.pytest.ini_options]` in `pyproject.toml` sets `pythonpath = ["."]` so `src.*` imports resolve correctly

**Assertion Library:**
- Built-in `assert` statements (no separate assertion library)

**Run Commands:**
```bash
uv run pytest                          # Run all tests
uv run pytest -v                       # Verbose
uv run pytest tests/test_file.py       # Single test file
uv run pytest -k "test_name"           # Filter by name
uv run pytest -x                       # Stop on first failure
uv run pytest --tb=short               # Short traceback
```
Or via the convenience script:
```bash
./scripts/run.sh test                  # Run all tests
./scripts/run.sh test -v -k "batch"   # With pytest args
```

## Test File Organization

**Location:**
- All tests live in `tests/` directory (separate from source, not co-located)
- No `__init__.py` in `tests/` — pytest discovers files by naming convention

**Naming:**
- Test files: `test_<feature>.py` — e.g., `test_protocol_contract.py`, `test_reserve_batch.py`, `test_transaction_idempotency.py`, `test_deterministic_errors.py`, `test_query_atomicity.py`, `test_query_seat_map.py`, `test_lock_hierarchy_core.py`, `test_transaction_races.py`, `concurrent_tests.py`
- Note: `concurrent_tests.py` does NOT follow the `test_` prefix convention — it is a standalone script with `if __name__ == "__main__":` and is NOT auto-discovered by pytest

**Structure:**
```
tests/
├── test_protocol_contract.py      # Request/response schema validation
├── test_deterministic_errors.py   # Error code determinism & structure
├── test_reserve_batch.py          # Batch reserve atomicity & protocol
├── test_transaction_idempotency.py # Confirm/cancel/expire lifecycle
├── test_transaction_races.py      # Concurrent confirm vs expire races
├── test_query_atomicity.py        # QUERY invariants under concurrency
├── test_query_seat_map.py         # Seat map query lifecycle
├── test_lock_hierarchy_core.py    # Lock ordering/deadlock prevention
└── concurrent_tests.py            # Stress test (not auto-discovered)
```

## Test Structure

**Suite Organization:**
Tests are organized using classes that group related tests. Each class focuses on one aspect of the feature:

```python
class TestReserveBatchAtomicity:
    """Verify all-or-nothing semantics for batch reserves."""
    
    def test_all_seats_available_reserves_all(self, concert_server):
        """When all seats available, all should be reserved."""
        client = ConcertClient('localhost', concert_server.port)
        response = client.send_request({
            "action": "RESERVE_BATCH",
            "seats": [{"section": "VIP", "row": 0, "col": 0}, ...]
        })
        assert response["status"] == "SUCCESS"
        assert "transaction_id" in response

    def test_one_seat_unavailable_reserves_none(self, concert_server):
        """When any seat unavailable, no seats should be reserved."""
        # ... test body ...
```

**Patterns:**
- Class name: `Test<Feature><Aspect>` — `TestRequestJsonParsing`, `TestErrorResponseStructure`, `TestReserveBatchProtocolValidation`
- Test method name: `test_<condition_or_behavior>` — `test_valid_json_object`, `test_missing_section`, `test_batch_ttl_field_in_response`
- Each test has a one-line docstring explaining what it validates
- Section comments as visual delimiters: `# =========================================`

**Setup/Teardown:**
- `@pytest.fixture` for server lifecycle
- No `setup_method`/`teardown_method` used
- Server is started in fixture, yielded, then `.stop()` called in teardown

## Fixtures

**Two fixture patterns exist — use the second one (cleaner):**

Pattern 1 — Tuple fixture (used in older tests: `test_transaction_idempotency.py`, `test_query_seat_map.py`):
```python
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
```

Pattern 2 — Object fixture (used in newer tests: `test_reserve_batch.py`, `test_query_atomicity.py`): **PREFERRED**
```python
@pytest.fixture
def concert_server():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('localhost', 0))
        port = s.getsockname()[1]
    server = ConcertServer(port=port)
    server.start()
    time.sleep(0.5)
    yield type('Server', (), {'port': port, 'instance': server})()
    server.stop()
```

All fixtures:
| Fixture | File(s) | Returns |
|---------|---------|---------|
| `concert_server` | `test_reserve_batch.py`, `test_query_atomicity.py` | Object with `.port` and `.instance` |
| `concert_server_instance` | `test_transaction_idempotency.py`, `test_query_seat_map.py` | Tuple `(server, port)` |

**Best practice when adding new tests:** Use the `concert_server` fixture pattern (pattern 2) to stay consistent with newer test files.

## Mocking

**Framework:** No mocking framework used. No `unittest.mock` or `pytest-mock` imports detected.

**What to Mock:** Nothing is currently mocked — tests use real `ConcertServer` instances on ephemeral ports. This is an integration-heavy approach.

**Patterns without mocks:**
- Inline test doubles for unit tests: `RecordingLock`, `DummySeatMatrix`, `DummyReservationTable` in `test_lock_hierarchy_core.py`
```python
class RecordingLock:
    def __init__(self, name, events):
        self.name = name
        self.events = events

    def acquire(self):
        self.events.append(f"acquire:{self.name}")

    def release(self):
        self.events.append(f"release:{self.name}")
```

- Direct state manipulation for forcing edge cases:
```python
# Force expiration path without waiting full TTL.
with server.reservation_table.mutex_table:
    reservation = server.reservation_table.reservations[tx_id]
    reservation.timestamp_creation = 0.0
server.monitor_thread.expire_reservation(tx_id)
```

- Semaphore value introspection (uses private `_value` attribute):
```python
semaphore_value = server.semaphore_mgr.s_sections[Section.VIP]._value
```

## Fixtures and Factories

**Test Data:**
Test data is constructed inline in each test method. No fixture factory or data builder utility exists.

Common patterns:
```python
# Single seat request
{"section": "VIP", "row": 2, "col": 5}

# Batch seats
[
    {"section": "VIP", "row": 0, "col": 0},
    {"section": "PREFERENTIAL", "row": 5, "col": 5},
    {"section": "GENERAL", "row": 10, "col": 10}
]
```

**Where fixtures live:**
- Fixtures are defined at the bottom of each test file or at the top
- `concert_server` fixture is duplicated in `test_reserve_batch.py` and `test_query_atomicity.py` (some duplication across files)
- No shared `conftest.py` file exists — this is a gap when adding new test files

## Coverage

**Requirements:** None enforced. No coverage tool configuration in `pyproject.toml`.

**Coverage gap:** With no conftest.py and no coverage config, coverage is not tracked.

**View Coverage (not configured, but could use):**
```bash
uv run pytest --cov=src
```

## Test Types

**Unit Tests:**
- `test_lock_hierarchy_core.py` — Tests lock ordering logic with recording test doubles (pure unit, no server)
- `test_deterministic_errors.py` — Tests error response factory functions (pure unit)
- `test_protocol_contract.py` — Tests validation functions directly (pure unit)

**Integration Tests:**
- `test_reserve_batch.py` — Tests RESERVE_BATCH against live server
- `test_transaction_idempotency.py` — Tests CONFIRM/CANCEL/expire lifecycle
- `test_query_seat_map.py` — Tests seat map query against live server
- `test_query_atomicity.py` — Tests QUERY invariants with concurrency
- `test_transaction_races.py` — Tests concurrent confirm vs expire behavior

**E2E Tests:**
- Not formally defined. `concurrent_tests.py` is a stress/load test script, not auto-discovered by pytest.

## Common Patterns

**Async Testing:**
No async code in the codebase. All I/O is synchronous. Threading is used for concurrency.

**Concurrent Testing Pattern (using threading.Barrier):**
```python
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
```

**Error Testing:**
```python
def test_scenario_reserve_invalid_section(self):
    response = error_invalid_section("EXECUTIVE")
    assert response["status"] == "ERROR"
    assert response["error_code"] == ErrorCode.INVALID_SECTION
    assert "EXECUTIVE" in response["message"]
```

**Exception Testing with pytest.raises:**
```python
def test_confirm_fails_after_expiration(self, concert_server_instance):
    # ... setup ...
    with pytest.raises((TransactionNotActiveError, TransactionNotFoundError)):
        client.confirm(tx_id)
```

**Invariant Testing Pattern (used in test_query_atomicity.py):**
```python
for section_name, counts in response["sections"].items():
    available = counts["available"]
    reserved = counts["reserved"]
    sold = counts["sold"]
    config = SECTION_CONFIG.get(Section[section_name], {})
    capacity = config.get("rows", 0) * config.get("cols", 0)
    total = available + reserved + sold
    assert total == capacity
```

**Thread Safety Verification Pattern:**
```python
results = {"success": [], "failure": []}
lock = threading.Lock()

def reserve_seats(client_id):
    try:
        client = ConcertClient('localhost', port)
        response = client.send_request({...})
        with lock:
            if response["status"] == "SUCCESS":
                results["success"].append(client_id)
            else:
                results["failure"].append(client_id)
    except Exception as e:
        with lock:
            results["failure"].append((client_id, str(e)))

threads = [threading.Thread(target=reserve_seats, args=(i,)) for i in range(2)]
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=5)

assert len(results["success"]) == 1
assert len(results["failure"]) == 1
```

**Test types by file:**

| File | Type | Tests |
|------|------|-------|
| `test_lock_hierarchy_core.py` | Unit | 4 tests — lock ordering, deduplication, context manager |
| `test_protocol_contract.py` | Unit | ~30 tests — JSON parsing, action validation, payload validation, response validation |
| `test_deterministic_errors.py` | Unit | ~20 tests — error structure, determinism, status differentiation, enum values |
| `test_query_atomicity.py` | Integration | 6 tests — protocol compliance, invariants, idempotence, consistency |
| `test_query_seat_map.py` | Integration | 3 tests — initial state, reflects lifecycle |
| `test_reserve_batch.py` | Integration | ~12 tests — protocol validation, atomicity, edge cases, concurrency |
| `test_transaction_idempotency.py` | Integration | 3 tests — confirm/cancel removes reservation, expiration |
| `test_transaction_races.py` | Integration | 2 tests — confirm vs expire, cancel vs expire races |

## Gaps & Recommendations

1. **No `conftest.py`** — Shared fixtures (`concert_server`) are duplicated across test files. Extract into `tests/conftest.py`.
2. **No code coverage configuration** — Add `[tool.coverage.run]` to `pyproject.toml` and enforce minimum coverage.
3. **`concurrent_tests.py` not auto-discovered** — Not picked up by pytest because it lacks `test_` prefix. Rename to `test_concurrent_stress.py` and convert to pytest functions.
4. **No mocking framework** — Adding `pytest-mock` would allow isolating server logic from network I/O for faster unit tests.
5. **No parameterized tests** — No `@pytest.mark.parametrize` usage. Many validation tests repeat similar patterns.
6. **Missing `__init__.py` in `tests/`** — While not strictly required by pytest, adding one (even empty) ensures consistent test discovery with all tooling.

---

*Testing analysis: 2026-06-01*
