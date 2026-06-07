# Testing Patterns

**Analysis Date:** 2026-06-04

## Test Framework

**Runner:**
- pytest v9.0.3
- Config: `pyproject.toml` under `[tool.pytest.ini_options]` with `pythonpath = ["."]`
- No additional pytest plugins detected
- No `pytest.ini`, `conftest.py`, or `tox.ini` files found — all configuration in `pyproject.toml`

**Assertion Library:**
- pytest built-in `assert` statements (no third-party assertion library)
- `pytest.raises()` for exception testing

**Run Commands:**
```bash
pytest                          # Run all tests (from project root)
pytest tests/                   # Run all tests
pytest tests/test_phase1_e2e.py # Run specific test file
pytest -v                       # Verbose output
pytest -x                       # Stop on first failure
```

**Coverage:**
- No coverage tool installed (no `pytest-cov`, `coverage.py`, or coverage configuration detected)
- `.coverage` and `coverage.xml` are in `.gitignore` but no coverage setup currently in use

## Test File Organization

**Location:**
- All tests live in the `tests/` directory at project root — separate from source (not co-located)
- Tests mirror the project structure loosely but use descriptive `test_<feature>.py` names

**Naming:**
- Test files: `test_<feature>.py` — e.g., `test_phase1_e2e.py`, `test_protocol_contract.py`, `test_lock_hierarchy_core.py`
- Test classes: `Test<PascalCase>` — e.g., `TestPhase1SessionTTL`, `TestErrorResponseStructure`, `TestReserveBatchProtocolValidation`
- Test methods: `test_<behavior>()` — e.g., `test_client_accepts_user_id`, `test_reserve_returns_session_id`, `test_valid_reserve_batch_single_seat`

**Structure:**
```
tests/
├── test_phase1_e2e.py              # Phase 1: User ID + Session-Based TTL
├── test_phase2_e2e.py              # Phase 2: expire_reservation fix + startup cleanup
├── test_phase3_e2e.py              # Phase 3: Buy Near Expiry + Concurrent Cancellation
├── test_phase6_e2e.py              # Phase 6: Instance Closure + Saturated Zone + Audit Log
├── test_protocol_contract.py       # Request/Response JSON schema validation
├── test_deterministic_errors.py    # Error code correctness and consistency
├── test_reserve_batch.py           # RESERVE_BATCH atomicity and edge cases
├── test_lock_hierarchy_core.py     # Lock ordering and mutex manager
├── test_transaction_idempotency.py # Confirm/Cancel idempotency guarantees
├── test_transaction_races.py       # CONFIRM vs EXPIRE concurrency races
├── test_query_atomicity.py        # QUERY snapshot consistency
├── test_query_seat_map.py         # QUERY_SEAT_MAP correctness
├── test_tui_seat_map.py           # TUI seat map rendering (unit tests with mocks)
├── concurrent_tests.py            # Stress/concurrency tests with invariants
```

## Test Structure

**Suite Organization:**
```python
import pytest

from src.module import SomeClass


class TestFeatureName:
    """Tests for specific feature."""

    def test_behavior_description(self):
        """What this test validates — single-line docstring."""
        # Arrange
        obj = SomeClass()

        # Act
        result = obj.method()

        # Assert
        assert result == expected
```

**Patterns:**
- Classes used to group related tests — each class tests one feature or concern
- Docstrings on every test method describing what is being validated
- `# Arrange / Act / Assert` sections commonly used but not strictly enforced
- Tests are independent — each test starts its own server instance on a random port

**Setup (Fixtures):**
```python
@pytest.fixture
def concert_server():
    """Start concert server for testing on random port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]

    server = ConcertServer(port=port)
    server.start()
    time.sleep(0.5)

    yield type("Server", (), {"port": port, "instance": server})()

    server.stop()
```

**Teardown:**
- Fixtures handle teardown after `yield` — e.g., `server.stop()`
- Some tests use `try/finally` inside the test body for explicit cleanup
- Dynamic types created with `type("Server", (), {...})()` to bundle port + instance

**Assertion Pattern:**
```python
# Direct value assertions
assert response["status"] == "SUCCESS"
assert "transaction_id" in response

# Invariant assertions with descriptive messages
assert total == capacity, (
    f"Invariant broken in {section.name}: "
    f"available({available}) + reserved({reserved}) + sold({sold}) = {total}, "
    f"expected capacity {capacity}"
)

# Exception assertions
with pytest.raises((TransactionNotActiveError, TransactionNotFoundError)):
    client.confirm(tx_id)

# Boolean/method assertions
assert is_valid, f"Expected valid request, got error: {msg}"
```

## Mocking

**Framework:** `unittest.mock` (standard library) — `MagicMock`, `patch`, `call`

**Patterns:**
```python
from unittest.mock import MagicMock, call, patch

@pytest.fixture
def app():
    """Return a ConcertTextualApp instance with mocked widgets."""
    app = ConcertTextualApp()
    table_mock = MagicMock()
    table_mock.cursor_type = "cell"
    table_mock.row_count = 0
    app.query_one = MagicMock(return_value=table_mock)
    app.pending_selections = []
    return app


def test_empty_grid_sets_cursor_none(self, app):
    """Empty grid → cursor_type set to 'none', no rows added."""
    app.seat_map_snapshot = {"GENERAL": []}
    app.selected_map_section = "GENERAL"

    table = app._render_seat_map()  # or call helper

    assert table.cursor_type == "none"
    table.clear.assert_called_with(columns=True)
    table.add_columns.assert_not_called()
    table.add_row.assert_not_called()
```

**What to Mock:**
- External UI widgets (Textual `DataTable`, `Static`, `Select`, etc.) when testing TUI components
- `call_from_thread()` in TUI tests — mocked to avoid thread marshaling complexity
- Used sparingly — most tests are integration/E2E style against a real server

**What NOT to Mock:**
- Core business logic classes (`SeatMatrix`, `ReservationTable`, `SemaphoreManager`)
- Server/client communication — real TCP sockets used in most tests
- Protocol validators — tested with real JSON payloads

## Fixtures and Factories

**Test Data (Server Fixtures):**
```python
@pytest.fixture
def concert_server():
    """Start concert server with random port. Returns object with .port and .instance."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]
    server = ConcertServer(port=port)
    server.start()
    time.sleep(0.5)
    yield type("Server", (), {"port": port, "instance": server})()
    server.stop()
```

**Location:**
- Fixtures defined in test files (not in `conftest.py` — no shared fixture modules)
- Each test file defines its own server fixtures (some duplication across files)
- Some fixture names vary slightly: `concert_server`, `concert_server_instance`, `server_port`

**Helper Functions:**
- Shared helpers defined as module-level functions:
```python
def _wait_for_server(host, port, retries=50, wait_seconds=0.1):
    """Poll server until QUERY succeeds or timeout."""
    for _ in range(retries):
        try:
            client = ConcertClient(host=host, port=port)
            response = client.query()
            if response.get("status") == "SUCCESS":
                return
        except Exception:
            time.sleep(wait_seconds)
    raise RuntimeError("Server did not start in time")
```

**Recording/Fake Objects:**
```python
class RecordingLock:
    """Fake lock that records acquire/release calls for testing lock ordering."""
    def __init__(self, name, events):
        self.name = name
        self.events = events

    def acquire(self):
        self.events.append(f"acquire:{self.name}")

    def release(self):
        self.events.append(f"release:{self.name}")


class DummySeatMatrix:
    """Lightweight seat matrix stub for mutex manager tests."""
    def __init__(self, locks):
        self.mutex_sections = locks
```

## Coverage

**Requirements:** None enforced — no coverage tool installed or configured

**View Coverage:** Not available — `pytest --cov` would require `pytest-cov` to be added to dev dependencies

**Test coverage observed:**
- Protocol validation (`protocol_validator.py`): Thoroughly tested by `test_protocol_contract.py` (423 lines)
- Error responses (`error_responses.py`): Tested by `test_deterministic_errors.py` (326 lines)
- Lock hierarchy (`lock_hierarcky.py`, `mutex_manager.py`): Tested by `test_lock_hierarchy_core.py` (94 lines)
- RESERVE_BATCH: Tested by `test_reserve_batch.py` (493 lines — most comprehensive)
- TUI seat map: Tested by `test_tui_seat_map.py` (160 lines)
- Phase features: 4 E2E test files totaling ~820 lines
- Concurrency: `concurrent_tests.py` (430 lines) runs stress tests
- **Gaps:** `concert_server.py` startup/shutdown edge cases, `session_manager.py` direct unit tests, `global_log.py` no direct tests

## Test Types

**Unit Tests:**
- Scope: Functions/classes tested in isolation
- Examples: `test_lock_hierarchy_core.py` (lock ordering logic with fakes), `test_protocol_contract.py` (validator functions), `test_deterministic_errors.py` (error factory functions), `test_tui_seat_map.py` (TUI methods with mocked widgets)
- Pattern: Arrange inputs, call function, assert output/state

**Integration Tests:**
- Scope: Server + client communicating over TCP on localhost
- Examples: `test_phase1_e2e.py`, `test_phase2_e2e.py`, `test_transaction_idempotency.py`, `test_query_seat_map.py`
- Pattern: Start server fixture → create client → perform operations → assert server state
- Port binding: Always use `s.bind(("localhost", 0))` for random free port allocation
- Server warmup: `time.sleep(0.5)` after `server.start()` (no event-based ready signal)

**Stress/Concurrency Tests:**
- Scope: Multiple threads performing concurrent reservations
- Example: `concurrent_tests.py` — 50 iterations × 10 threads per section, verifying invariants
- Pattern: `threading.Barrier` for synchronized parallel execution, result collection with locks, invariant checks after each iteration
- Handles: Race conditions between RESERVE, CONFIRM, CANCEL from multiple clients

**Race Condition Tests:**
- Scope: Specific concurrency scenarios (confirm vs expire, confirm vs cancel)
- Examples: `test_transaction_races.py`, `test_phase3_e2e.py`
- Pattern: Manual timing manipulation (modify `timestamp_creation = 0.0`), synchronized thread start with `threading.Barrier(3)`

**E2E Tests:**
- Scope: Full request-response cycle through server
- Framework: No E2E framework (Cypress, Playwright, etc.) — not used
- TUI tests test individual rendering methods, not full UI interaction flow

## Common Patterns

**Async/Thread Testing:**
```python
def test_confirm_vs_expire_keeps_consistency():
    # Start server, create client, reserve seat
    ...

    start_barrier = threading.Barrier(3)
    results = {}

    def run_expire():
        start_barrier.wait()
        # Expire the session
        ...

    def run_confirm():
        start_barrier.wait()
        # Try to confirm
        ...

    t1 = threading.Thread(target=run_expire)
    t2 = threading.Thread(target=run_confirm)
    t1.start()
    t2.start()
    start_barrier.wait()  # third participant (main thread)

    t1.join(timeout=5)
    t2.join(timeout=5)

    # Assert final state is consistent
```

**Error Testing:**
```python
def test_invalid_section(self):
    """Unknown section should fail validation."""
    request = {"action": "RESERVE", "section": "BALCONY", "row": 0, "col": 0}

    is_valid, error_msg = validate_reserve_payload(request)

    assert is_valid is False
    assert "BALCONY" in error_msg

# Exception testing with pytest.raises
with pytest.raises((TransactionNotActiveError, TransactionNotFoundError)):
    client.confirm(tx_id)
```

**Invariant Checking Pattern:**
```python
def _check_invariants(server, query_response):
    """Verify all system invariants after operations."""
    # Assert protocol compliance
    assert query_response["status"] == "SUCCESS"

    for section in Section:
        stats = query_response["sections"][section.name]
        # Assert accounting invariance
        total = stats["available"] + stats["reserved"] + stats["sold"]
        capacity = rows * cols
        assert total == capacity, f"Invariant broken: {total} != {capacity}"

        # Assert semaphore consistency
        assert semaphore_value == stats["available"]
```

**Expected Failure Pattern:**
```python
def test_confirm_fails_after_expiration(concert_server_instance):
    server, port = concert_server_instance
    client = ConcertClient(host="localhost", port=port)

    resp = client.reserve_seat("VIP", 0, 2)
    tx_id = resp["transaction_id"]

    # Force expiration by backdating creation time
    with server.reservation_table.mutex_table:
        reservation = server.reservation_table.reservations[tx_id]
        reservation.timestamp_creation = 0.0

    server.monitor_thread.expire_reservation(tx_id)

    # Operation should fail after forced expiration
    with pytest.raises((TransactionNotActiveError, TransactionNotFoundError)):
        client.confirm(tx_id)
```

## Test Dependencies

**Dev Dependencies (from `pyproject.toml`):**
- `pytest>=9.0.3` — test runner
- `black>=26.3.1` — code formatter
- `flake8>=7.3.0` — linter
- No `mock` package (uses `unittest.mock` stdlib)
- No `coverage` or `pytest-cov`
- No `pytest-timeout`, `pytest-xdist`, or `pytest-asyncio`

---

*Testing analysis: 2026-06-04*
