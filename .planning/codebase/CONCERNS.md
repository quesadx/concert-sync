# Codebase Concerns

**Analysis Date:** 2026-06-01

## Tech Debt

### Dead code in `monitor_thread.py` — expiration logic unreachable

**Issue:** After the early-return guard on line 45, the seat-release loop (lines 50-55) is indented at the same level as the preceding `return` statement, making the entire expiration body unreachable dead code. The variables `ordered_sections` and `seats_by_section` are also referenced without being defined in this scope — both `_group_reservation_seats_by_section()` and `_ordered_sections()` are never called by `expire_reservation()`.

**Files:** `src/server/monitor_thread.py` (lines 44-55)

```python
if not reservation or reservation.state != ReservationStatus.ACTIVE:
    return
    # ────────────────────────────────────────────────────────────
    # EVERYTHING BELOW IS DEAD CODE (same indent as `return`)
    reservation.state = ReservationStatus.EXPIRED
    for section in ordered_sections:      # ← Never defined here
        for row, col in seats_by_section[section]:  # ← Never defined here
            ...
# ────────────────────────────────────────────────────────────
# This runs regardless of the return above, but the seat-release
# logic in the middle is skipped entirely.
```

**Impact:** Reserved seats whose TTL expires are never released back to AVAILABLE. The semaphore counter for the section is never decremented. This causes permanent seat leaks — once capacity is exhausted, no new reservations in that section are possible until the server is restarted. The `EXPIRE` log line on line 67 still fires (the second half of the method runs), reporting `seats_released:0` since `released_counts` is empty.

**Fix approach:** Remove the `return` on line 46; compute `seats_by_section` and `ordered_sections` by calling `self._group_reservation_seats_by_section(reservation)` and `self._ordered_sections(...)` before the `with` block. Fix the indentation so the release body executes when the reservation is ACTIVE.

### Unused methods in `SeatMatrix`

**Issue:** Four methods in `SeatMatrix` are never called from any production code path:

- `check_availability()` — `src/shared_resources/seat_matrix.py:25`
- `reserve_seat()` — `src/shared_resources/seat_matrix.py:29`
- `set_seat_state()` — `src/shared_resources/seat_matrix.py:36`
- `get_section_counts()` — `src/shared_resources/seat_matrix.py:40`

Production code directly accesses `self.server.seat_matrix.seats[section][row][col]` instead, bypassing these wrappers.

**Files:** `src/shared_resources/seat_matrix.py`

**Impact:** Maintenance burden — changes to state transitions must be replicated in both the direct array access and the unused helper (or the helper goes stale). 30 lines of dead code.

**Fix approach:** Remove unused methods or refactor all seat state mutations to go through `SeatMatrix` methods for consistency.

### Duplicate seat-counting logic

**Issue:** Both `SeatMatrix.get_section_counts()` (`src/shared_resources/seat_matrix.py:40`) and `TransactionalThread._count_section_seats()` (`src/server/transactional_thread.py:476`) implement identical logic for counting `available`, `reserved`, and `sold` per section.

**Files:**
- `src/shared_resources/seat_matrix.py` (lines 40-64)
- `src/server/transactional_thread.py` (lines 476-499)

**Impact:** Changes to the state-counting logic (e.g., adding a new state enum value) must be made in two places.

**Fix approach:** Delegate to `SeatMatrix.get_section_counts()` from `TransactionalThread` and remove the duplicate.

### Filename typo: `lock_hierarcky.py`

**Issue:** The filename contains a typo — "hierarcky" should be "hierarchy".

**File:** `src/synchronization/lock_hierarcky.py`

**Impact:** Referencing this module from documentation or for future contributions is error-prone. Might cause import confusion.

**Fix approach:** Rename file to `lock_hierarchy.py` and update all imports in `mutex_manager.py` and test files.

### No log rotation for `logs/system.log`

**Issue:** `GlobalLog` (`src/shared_resources/global_log.py`) appends to `logs/system.log` without any log rotation, truncation, or size limit. Under sustained load, this file grows unbounded.

**File:** `src/shared_resources/global_log.py`

**Impact:** Disk space exhaustion on long-running servers.

**Fix approach:** Add log rotation (e.g., `RotatingFileHandler` from stdlib, or size-based truncation after N MB).

### Hardcoded port 9999

**Issue:** Port 9999 is hardcoded in `main.py`, `desktop_launcher.py`, `frontend_tui/app.py`, and `scripts/run.sh`.

**Files:**
- `main.py` (line 6)
- `desktop_launcher.py` (line 6)
- `frontend_tui/app.py` (line 92)
- `scripts/run.sh` (line 105)

**Impact:** If port 9999 is occupied, the server fails at `bind()` with no fallback or retry mechanism.

**Fix approach:** Support config via environment variable with `int(os.getenv("CONCERT_SYNC_PORT", 9999))` in `src/utils/config.py`.

### No message framing in TCP protocol

**Issue:** The protocol sends/receives JSON with no length prefix, delimiter, or message boundary. The server side reads exactly once from the socket (`transactional_thread.py:39`), assuming the entire JSON fits in one `recv(4096)`. TCP is a stream protocol — messages can be split across packets or coalesced.

**Files:**
- `src/server/transactional_thread.py` (line 39)
- `src/client/concert_client.py` (lines 93-98 — client does loop correctly)

**Impact:** Under load, a fragmented TCP message causes JSON parse failure on the server, returning `ERR_INVALID_PAYLOAD` to the client. If two messages arrive in the same read, the second is silently dropped.

**Fix approach:** Prefix each message with a 4-byte length header (e.g., `struct.pack("!I", len(payload))`), or use a newline delimiter and read until delimiter.

## Known Bugs

### Semaphore leak on `RESERVE` rollback race

**Symptoms:** In `TransactionalThread.handle_reserve()` (lines 106-185), if `semaphore_mgr.acquire()` succeeds but `reservation_table.add_reservation()` fails, the exception handler releases the seat state (lines 172-178) AND releases the semaphore if `semaphore_acquired` is `True`. However, if `add_reservation()` throws after acquiring the semaphore but before the exception handler runs, the semaphore may not be released. The `semaphore_acquired` local variable may be out of scope or incorrectly `False` depending on exception timing.

**Files:** `src/server/transactional_thread.py` (lines 143-184)

**Trigger:** High concurrency where `add_reservation()` raises an unexpected exception (e.g., `KeyError` on corrupt data).

**Workaround:** None known. The rollback logic is in `except Exception` but references `semaphore_acquired` which may be stale.

### RESERVE_BATCH single-section fallback section logic

**Symptoms:** In `handle_reserve_batch` (line 285), when a batch spans multiple sections, `primary_section` is hardcoded to `Section.VIP`. This `primary_section` is only used as a label for the reservation record — it doesn't affect seat assignment — but it creates an incorrect section attribution.

**File:** `src/server/transactional_thread.py` (line 285)

**Trigger:** Any multi-section RESERVE_BATCH request.

**Impact:** The `Reservation.section` field will be `VIP` even if the batch has no VIP seats. This is misleading for log analysis and monitoring.

### No thread pool — unbounded thread creation

**Symptoms:** Each client connection creates a new `TransactionalThread` via `ListenerThread.run()` without any pooling or cap.

**File:** `src/server/listener_thread.py` (line 17)

**Trigger:** Attacker or high-load scenario with many concurrent connections.

**Impact:** Thread count grows linearly with connections, leading to memory exhaustion, GIL contention, and eventual `OSError: [Errno 11] Resource temporarily unavailable`. A DoS vector.

### Server socket backlog is hardcoded to 5

**Issue:** `self.server_socket.listen(5)` in `src/server/concert_server.py:32` limits the listen backlog to 5 connections.

**File:** `src/server/concert_server.py` (line 32)

**Impact:** Under high concurrency, clients will receive `Connection refused` even when the server could theoretically handle the load, because the kernel's accept queue overflows.

### Direct access to `Semaphore._value` in tests

**Issue:** Tests in `test_transaction_races.py` and `concurrent_tests.py` access `threading.Semaphore._value`, a private implementation detail.

**Files:**
- `tests/test_transaction_races.py` (lines 73, 114)
- `tests/concurrent_tests.py` (line 62)

**Risk:** `_value` is not part of Python's public API and may change between CPython versions (3.14 is being used per `.python-version`). The test will silently break or produce wrong results on alternate Python implementations (PyPy, Jython, etc.).

## Security Considerations

### No authentication or authorization

**Risk:** Any client on the network can connect to the TCP port and reserve/cancel/confirm seats. No identity, API keys, or session tokens are required.

**Files:** All `src/server/` files.

**Current mitigation:** Only `listen(5)` with no `bind()` to external interfaces — default is `localhost` in `main.py`. But `ConcertClient` constructor defaults to `localhost` and the server accepts any interface if `host` is changed.

**Recommendations:** Add token-based authentication for all mutating actions (RESERVE, CONFIRM, CANCEL). At minimum, document that the server must be firewalled.

### No input sanitization beyond JSON validation

**Risk:** The `protocol_validator.py` validates types and ranges, but seat data is stored in-memory as native Python objects. A crafted JSON payload with extremely nested arrays or huge numeric values could cause memory exhaustion.

**Files:** `src/utils/protocol_validator.py`

**Current mitigation:** `recv(4096)` buffer limits the raw input to 4KB.

**Recommendations:** Add explicit maximum JSON depth and size limits; reject payloads exceeding 4096 bytes before parsing.

### No TLS/SSL encryption

**Risk:** All communication is plain TCP. Credentials (if added later) and transaction data are sent in cleartext.

**Current mitigation:** Default `localhost` binding limits exposure.

**Recommendations:** Wrap socket with SSL context for non-localhost deployments.

## Performance Bottlenecks

### Single global `MutexManager.table()` lock

**Problem:** All CONFIRM/CANCEL/RESERVE_BATCH operations acquire the reservation table lock (`mutex_table = threading.Lock()`) before acquiring section locks. This serializes all transactional operations through a single global lock, limiting throughput even when operations target different sections.

**Files:** `src/synchronization/mutex_manager.py` (lines 28-31) and `src/shared_resources/reservation_table.py` (line 22)

**Cause:** The `table_and_sections()` context manager acquires `table()` before `sections()`. Every mutating operation uses this pattern, creating a global bottleneck.

**Improvement path:** Restructure the locking strategy so table operations (create/delete reservation) don't need to block concurrent operations on unrelated sections. A striped lock or per-section reservation tables would reduce contention.

### Per-client socket creates one thread

**Problem:** Each client connection creates a dedicated thread (`TransactionalThread`). For short-lived operations (single RESERVE/CONFIRM), the thread creation/teardown overhead exceeds the actual work.

**Files:**
- `src/server/listener_thread.py` (line 17)
- `src/server/transactional_thread.py`

**Improvement path:** Use a thread pool (`concurrent.futures.ThreadPoolExecutor`) with a fixed max size to reuse threads and cap resource usage.

### Monitor thread polls every second

**Problem:** `MonitorThread.run()` calls `time.sleep(1)` and iterates all reservations. For large reservation tables, this one-second scan creates lock contention on `mutex_table`.

**File:** `src/server/monitor_thread.py` (line 15)

**Improvement path:** Use a `threading.Condition.wait(timeout=1)` with notification from `add_reservation()` to avoid busy-waiting. Only scan reservations that are near their TTL.

## Fragile Areas

### `TransactionalThread` — error handling layer violation

**Files:** `src/server/transactional_thread.py`

**Why fragile:** The `run()` method (lines 37-77) has a single `try/except Exception` around the entire request lifecycle, followed by `error_internal(str(e))`. Internal error messages containing stack trace fragments (e.g., `"KeyError: 'seats'"`) are sent directly to the client. The `handle_reserve()` method has a separate `try/except` that duplicates rollback logic. Maintaining two layers of exception handling is error-prone — changes to seat state transitions must be reflected in both the happy path and the rollback path.

**Test coverage:** `test_deterministic_errors.py` covers error response structures but does not test full-stack error paths (e.g., server crash behavior, partial state corruption recovery).

**Safe modification:** Always update both the happy-path and exception-handler paths when changing seat state management. Add dedicated error-path tests for each handler.

### `monitor_thread.py` — dead code expiration (see Tech Debt #1)

**Files:** `src/server/monitor_thread.py`

**Why fragile:** The core expiration logic is entirely dead code. Any fix requires rewriting the entire method's control flow. The `released_counts` defaultdict pattern and the `_group_reservation_seats_by_section` / `_ordered_sections` helper are already correct and well-tested — they just need to be called.

**Test coverage:** Race tests (`test_transaction_races.py`) test expire-vs-confirm and expire-vs-cancel scenarios. These tests call `monitor_thread.expire_reservation(tx_id)` directly. If the dead-code bug is fixed, these tests provide good regression coverage. However, they currently pass despite the bug because they check seat states post-expiration and the test expectations may not catch the failure.

### `SeatMatrix` — State modified via direct array access

**Files:** `src/shared_resources/seat_matrix.py` and `src/server/transactional_thread.py`

**Why fragile:** Seat state is mutated via `self.server.seat_matrix.seats[section][row][col] = SeatState.RESERVED` throughout `transactional_thread.py`. This bypasses any invariant checks, logging, or guards that could be centralized in `SeatMatrix`. Adding a new state (e.g., `HELD`) requires finding all direct assignments across multiple methods.

**Safe modification:** Route all state mutations through `SeatMatrix.set_seat_state()` or similar method that enforces valid state transitions.

### `ConcertClient` — error/failure exception mapping

**Files:** `src/client/concert_client.py`

**Why fragile:** The `ERROR_CODE_TO_EXCEPTION` mapping (lines 62-67) maps error codes to specific exception classes. If a new error code is added to `ErrorCode` class but not mapped here, the client raises the generic `ServerFailureError` instead of the specific exception. Callers catching specific exceptions (e.g., `SeatNotAvailableError`) will silently miss the new code.

**Test coverage:** `test_reserve_batch.py` tests use `send_request()` directly and check response status rather than relying on exception-based API (`reserve_seat()`, `confirm()`). The higher-level client methods (`reserve_seat()`, `confirm()`) are tested only in `test_transaction_idempotency.py` and `test_transaction_races.py`.

## Scaling Limits

### Maximum seating capacity

**Current capacity:**
- VIP: 5 rows × 10 cols = 50
- PREFERENTIAL: 10 rows × 15 cols = 150
- GENERAL: 20 rows × 20 cols = 400
- **Total: 600 seats**

**Limit:** Section dimensions are hardcoded in `src/utils/config.py` (line 5-7). Scaling beyond 600 seats requires both config changes and verification that `Section` enum values handle the hierarchy correctly. The lock-hierarchy order relies on `Section.value` (0=VIP, 1=PREF, 2=GEN), so adding sections changes lock ordering.

**Scaling path:** Define sections in external config (JSON/YAML) instead of Python enums. Use a lock hierarchy based on section name hash rather than ordinal value.

### Maximum concurrent connections

**Current capacity:** Limited by thread count (one thread per connection) and listen backlog of 5 (`src/server/concert_server.py:32`).

**Limit:** At ~100 concurrent connections, thread overhead becomes significant. At ~1000, OS thread limits are hit (`ulimit -u` typically 4096).

## Dependencies at Risk

### `textual` for TUI frontend

**Risk:** The TUI frontend depends on `textual>=0.70.0` (specified as a separate `tui` dependency group in `pyproject.toml:16`). The production server (`main.py`) has no TUI dependency and runs fine without it. However, `desktop_launcher.py` imports both `ConcertServer` and `ConcertTextualApp`, making it dependent on `textual`.

**Impact:** Workspaces without the TUI dependency cannot run `desktop_launcher.py`.

**Migration plan:** Document the separate dependency groups. Consider making `textual` optional via lazy import in `desktop_launcher.py`.

### `pyinstaller` for Windows builds (build-time only)

**Risk:** The Windows build script (`scripts/build_windows_exe.ps1`) uses PyInstaller, which is known to have compatibility issues with Python 3.14+. The script is not tested in CI.

**Impact:** Windows distribution builds may fail with newer Python versions.

## Missing Critical Features

### No data persistence

**Problem:** All seat state, reservation table, and transaction history is in-memory. Server restart loses all data. There is no recovery mechanism.

**Blocks:** Production deployment where seat assignments must survive restarts. Any server crash during a CONFIRM operation means that seat's revenue is lost.

### No idempotency for RESERVE and RESERVE_BATCH

**Problem:** Per the protocol contract, `RESERVE` and `RESERVE_BATCH` are NOT idempotent. If a client sends a RESERVE, receives a timeout, and retries, the second request creates a duplicate reservation for the same seat. The protocol contract explicitly states RESERVE is not idempotent, but this means clients must implement their own deduplication.

**Files:** `docs/protocol-contract-v1.md` (lines 47-48)

### No health-check or monitoring endpoint

**Problem:** There is no endpoint to check server health, thread counts, or seat capacity without querying seat data. No Prometheus metrics or structured logging for observability platforms.

## Test Coverage Gaps

### Expiration logic untested

**What's not tested:** The actual seat-release behavior of `expire_reservation()` is tested via race-condition tests (`test_transaction_races.py`) but the core expiration logic is dead code (see Tech Debt #1). No test directly calls the method and verifies seat states change from RESERVED to AVAILABLE.

**Files:** `tests/test_transaction_races.py`, `tests/test_transaction_idempotency.py`

**Risk:** The dead code bug in `monitor_thread.py` was not caught by existing tests. When fixed, the tests may need updating to reliably detect correct behavior.

**Priority:** High

### Error handler paths untested

**What's not tested:** The rollback logic in `handle_reserve()` exception handler (lines 165-185), `handle_reserve_batch()` rollback paths (lines 262-269, 292-302), and the main `run()` error path (lines 66-72) have no dedicated tests.

**Files:** `src/server/transactional_thread.py`

**Risk:** A change to the happy path that breaks rollback logic will not be caught.

**Priority:** Medium

### TUI frontend untested

**What's not tested:** The entire `frontend_tui/` module has zero tests. Event handlers, state management, and thread safety of the TUI are untested.

**Files:** `frontend_tui/app.py`, `frontend_tui/__main__.py`

**Risk:** UI bugs during seat selection, TTL display, or concurrent state updates are not caught.

**Priority:** Low

---

*Concerns audit: 2026-06-01*
