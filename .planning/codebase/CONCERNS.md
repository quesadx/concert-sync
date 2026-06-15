# Codebase Concerns

**Analysis Date:** 2026-06-04

## Known Bugs

### RESERVE_SELECTED action blocked by protocol validator

- Symptoms: The TUI's "Confirm Selected Seats" button sends `action: "RESERVE_SELECTED"` but the server rejects it with `ERR_INVALID_ACTION: Unknown action: RESERVE_SELECTED`.
- Files: `src/utils/protocol_validator.py:94` (missing from `valid_actions`), `src/server/transactional_thread.py:54` (has routing), `src/client/concert_client.py:196` (sends it), `frontend_tui/app.py:767-820` (triggers it)
- Trigger: Click available seats on the seat map, then press "Confirm Selected Seats". The request reaches the server but `validate_action()` rejects it before `handle_reserve_selected()` can process it.
- Workaround: None. The feature is completely broken server-side.

### Individual reserve overrides session semantics

- Symptoms: A user who has accumulated multiple seats in a session (via multiple `RESERVE` calls or a `RESERVE_BATCH`) shares the same `session_id`. When the user sends `CONFIRM` with that `session_id`, all seats are correctly confirmed atomically. However, review notes indicate confusing behavior: "si el usuario tiene varios asientos seleccionados pero confirma mediante la modalidad individual, únicamente se reserva el último asiento seleccionado." — suggesting there are two distinct reservation paths that don't compose correctly.
- Files: `src/server/transactional_thread.py:108-187` (handle_reserve), `src/server/transactional_thread.py:190-301` (handle_reserve_batch), `src/server/session_manager.py:35-44` (get_or_create maps by user_id)
- Trigger: User reserves seat A (gets session_id X, TTL resets), then reserves seat B (same session_id X, TTL resets again). The session now has [A, B]. Both should be confirmed or cancelled together.

### Automatic expiration unreliable under evaluated conditions (PRUEBA 3)

- Symptoms: Review documents state "El mecanismo de expiración automática no funciona correctamente bajo las condiciones evaluadas." MonitorThread polls every 1 second and calls `expire_session`, but reports indicate seats don't always release.
- Files: `src/server/monitor_thread.py:13-75`, `src/server/session_manager.py:21-24`
- Trigger: Unknown specific conditions; review doesn't detail the reproduction steps. The TTL check (`is_expired`) depends on `last_activity` being updated, but the session might expire while a transaction is mid-flight (the double-check inside `table_and_sections` helps but doesn't cover all races).
- Workaround: None documented.

### Cancel-while-modify errors (PRUEBA 6)

- Symptoms: "La prueba no fue aprobada debido a errores detectados durante el proceso de cancelación concurrente." — concurrent cancellation scenarios trigger errors.
- Files: `src/server/transactional_thread.py:472-529` (handle_cancel), `tests/test_transaction_races.py:93-126` (test_cancel_vs_expire_releases_once)
- Trigger: One client cancels a reservation while another client modifies the same seat/section concurrently. The double-check pattern (`get_by_session_id` inside the lock) protects against expire-while-cancel but may not cover all races between two clients cancelling/modifying simultaneously.
- Workaround: None.

### Seats lost on client disconnect (PRUEBA 8)

- Symptoms: "Si el usuario cierra la instancia mientras tiene asientos reservados o seleccionados, estos se pierden al volver a ingresar al sistema." The server doesn't persist sessions across client reconnects.
- Files: `src/server/session_manager.py:30-51` (no persistence, in-memory only)
- Trigger: User closes the TUI or loses network while having active reserved seats. On reconnect, a new `session_id` is created and old seats remain expired (released after TTL) but there's no way to reclaim them.
- Workaround: None. Eventually the MonitorThread will release expired seats (after 300s TTL).

## Tech Debt

### ReservationTable is dead code from migration

- Issue: The `ReservationTable` class in `src/shared_resources/reservation_table.py` was the original reservation tracking mechanism. The system has migrated to `SessionManager` for tracking active reservations, rendering `ReservationTable` unused by the main flow. It still exists with its own mutex and condition variable, and `cleanup_stale_reservations` in `concert_server.py:35-76` tries to clean it up at startup — but handler methods (`handle_reserve`, `handle_reserve_batch`, `handle_reserve_selected`) never add entries to it.
- Files: `src/shared_resources/reservation_table.py` (entire file), `src/server/concert_server.py:35-76`
- Impact: Maintenance confusion. Developers may mistakenly add entries to the table or try to use it. The `monitor_thread.py:62-75` `expire_reservation` method is marked "Legacy safety wrapper — no longer called from run()."
- Fix approach: Remove `ReservationTable` and all references. Verify `cleanup_stale_reservations` is no longer needed (the `_release_all_sessions` method covers shutdown cleanup via SessionManager).

### Code duplication between handle_reserve_batch and handle_reserve_selected

- Issue: `handle_reserve_batch` (`transactional_thread.py:190-301`) and `handle_reserve_selected` (`transactional_thread.py:304-405`) are nearly identical — both parse seats from a list, group by section, acquire locks in hierarchy order, validate availability, mark RESERVED, acquire semaphore slots, append to session, reset TTL, and respond. The only difference is the action name logged.
- Files: `src/server/transactional_thread.py:190-405` (~215 lines of duplicated logic)
- Impact: Any bug fix or change must be applied in both places. Drift risk — code in one handler may diverge from the other.
- Fix approach: Extract shared reservation logic into a single `_reserve_multiple_seats(request, action_name)` method. Both handlers delegate to it with a different `action_name` string.

### Large files with mixed responsibilities

- Issue: `frontend_tui/app.py` (1126 lines) and `src/server/transactional_thread.py` (625 lines) are the largest files and mix multiple concerns.
  - `app.py`: UI composition, event handling, threading (worker threads), network client calls, data tracking, metrics/sparklines, log tailing, and seat map rendering — all in one class.
  - `transactional_thread.py`: JSON protocol handling, request routing, all 6 action handlers, lock orchestration, rollback logic, error handling, seat grouping utilities.
- Files: `frontend_tui/app.py`, `src/server/transactional_thread.py`
- Impact: Hard to test individual components. Changes ripple unpredictably. New contributors struggle to navigate.
- Fix approach: For `app.py`, extract workers into a `tui_workers.py` or similar; extract data models (`TrackedSession`, `LogTailer`) to a `tui_models.py`. For `transactional_thread.py`, extract each handler into its own method or delegate class.

### Misspelled filename

- Issue: `src/synchronization/lock_hierarcky.py` is misspelled (should be `lock_hierarchy.py`).
- Files: `src/synchronization/lock_hierarcky.py`
- Impact: Confusing to find/search. Type-checking and IDE navigation may stumble.
- Fix approach: Rename to `lock_hierarchy.py` and update all imports (`src/synchronization/mutex_manager.py:3`).

### No message framing in TCP protocol

- Issue: The client reads from the socket in a loop until no more data arrives (`concert_client.py:94-99`). There's no length prefix, delimiter, or message boundary marker. If the server ever multiplexed multiple responses on a single connection, the client would concatenate them into one malformed JSON string.
- Files: `src/client/concert_client.py:94-101`, `src/server/transactional_thread.py:38-45`
- Impact: Currently masked because each request opens a new TCP connection. If connection pooling or keep-alive is ever added, this will break.
- Fix approach: Add a length-prefix framing (e.g., 4-byte big-endian length followed by JSON payload), or use a newline delimiter with `makefile()`.

## Security Considerations

### No user authentication or identity verification

- Risk: `user_id` is a plain string sent in every request. Any client can claim any `user_id`. An attacker can reserve seats under another user's ID, confirm/cancel their reservations, or spam fake reservations that block legitimate users.
- Files: `src/server/transactional_thread.py:345-350` (validator only checks presence, not authenticity), `frontend_tui/login_screen.py:26-29` (just collects a display name), `src/client/concert_client.py:70-74` (user_id is a constructor parameter)
- Current mitigation: None. The system relies on honest clients.
- Recommendations: Add at minimum a server-assigned session token on first connect. For production, integrate OAuth2 or JWT-based authentication.

### Connectionless identity enables session theft

- Risk: Since `user_id` is the only identity, an attacker knowing another user's `user_id` can call `CONFIRM` with the stolen `transaction_id` to confirm their seats, or `CANCEL` to release them.
- Files: `src/server/transactional_thread.py:416-469` (handle_confirm checks `session.user_id != user_id` but user_id is self-reported)
- Current mitigation: The `handle_confirm` ownership check compares the request's `user_id` against the session's stored `user_id`. Both are self-reported strings, so an attacker simply needs to know (or guess) the target's `user_id`.
- Recommendations: Assign a random secret token per session that must accompany CONFIRM/CANCEL requests. Do not trust client-provided identity.

### Error responses expose internal state to clients

- Risk: Some error messages expose internal implementation details (e.g., seat state values, expected vs actual counts, section names with coordinates). While not a critical vulnerability, this aids attackers probing the system.
- Files: `src/utils/error_responses.py:144-178`
- Current mitigation: The protocol-contract intentionally provides descriptive error codes for debuggability. This is a design trade-off for a system that's academic/demo in nature.

## Performance Bottlenecks

### Global table_and_sections lock serializes all mutations

- Problem: `MutexManager.table_and_sections()` acquires the reservation table mutex AND all requested section mutexes simultaneously. While section locks are ordered (preventing deadlock), the table-level lock serializes ALL reserve/confirm/cancel operations — even for unrelated sections.
- Files: `src/synchronization/mutex_manager.py:28-31`, `src/synchronization/lock_hierarcky.py:10-23`
- Cause: The `table()` context manager acquires `reservation_table.mutex_table` before acquiring section locks. Every transactional operation goes through this path.
- Improvement path: The table lock is redundant since session operations use `session_manager._lock` directly. Remove the table lock from `table_and_sections` or scope it only to operations that actually read/write the reservation table (which is currently dead code).

### One-socket-per-request connection model

- Problem: Each `concert_client.send_request()` creates a new TCP socket, connects, sends, receives, and closes. The TUI calls `query()` + `query_seat_map()` every second — that's 2 new connections per second per client.
- Files: `src/client/concert_client.py:91-99`
- Cause: Simplicity of implementation. The protocol contract assumes one JSON object per connection.
- Improvement path: Implement connection pooling or keep-alive with proper message framing (see Tech Debt: No message framing).

### Sequential semaphore acquisition in batch reserve

- Problem: `handle_reserve_batch` acquires semaphore slots one at a time in a loop (`for _ in range(requested_count): acquire()`). If 10 seats are requested and the 9th fails, the other 8 were already acquired and must be rolled back. The acquire is also non-blocking, so partial failures are common under contention.
- Files: `src/server/transactional_thread.py:260-277`
- Cause: Python's `threading.Semaphore` doesn't support `acquire(n)` with timeout. The semaphore manager wraps individual semaphore instances.
- Improvement path: Replace `threading.Semaphore` with `threading.BoundedSemaphore` and implement a `try_acquire_multiple` method that checks capacity atomically before acquiring.

## Fragile Areas

### Session TTL reset on every reserve extends lifetime arbitrarily

- Files: `src/server/session_manager.py:20-27`, `src/server/transactional_thread.py:157,283,389`
- Why fragile: The `reset_ttl()` call sets `last_activity = time.time()` on every `RESERVE`/`RESERVE_BATCH`/`RESERVE_SELECTED`. A user who reserves one seat every 4.5 minutes (TTL is 300s) can keep a session alive indefinitely, holding seats hostage. Review PRUEBA 4 notes this: "el TTL se maneja individualmente por asiento y no como parte integral de una reserva o sesión de selección."
- Safe modification: Consider a hard session cap (e.g., 5 minutes from session creation, regardless of activity) or per-seat independent TTLs.
- Test coverage: `tests/test_transaction_races.py` tests race conditions between expire and confirm/cancel, but doesn't test the indefinite extension scenario.

### TUI session tracking unbounded and desynced from server

- Files: `frontend_tui/app.py:104,549-565`
- Why fragile: The TUI's `self.sessions` dict grows without bound as sessions are added. Expired sessions are marked "EXPIRED" but never removed. The TUI tracks TTL using `created_at` (when the TUI received the response), while the server uses `last_activity` (reset on each operation). This causes the TUI to show sessions as expired while the server still considers them active.
- Safe modification: Cap the tracked sessions at a maximum (e.g., 100) and evict oldest non-ACTIVE entries. Periodically sync TTL from server instead of tracking independently.
- Test coverage: No dedicated tests for TUI session tracking logic.

### Shutdown doesn't wait for in-flight TransactionalThreads

- Files: `src/server/concert_server.py:140-161`
- Why fragile: `stop()` calls `server_socket.close()`, sleeps 0.5s, releases sessions, then joins listener/monitor threads with 2s timeout. Running `TransactionalThread` instances (spawned by the listener) may be in the middle of a critical section. Their sockets may be closed under them, but they hold locks acquired via `table_and_sections`. If a transaction is mid-flight, the locks are held until the thread's context manager exits — but the server process may terminate before that.
- Safe modification: The listener should track spawned threads and wait for them to complete (with a reasonable timeout) before releasing sessions. Alternatively, use a `threading.Event` shutdown flag that TransactionalThreads check before acquiring locks.
- Test coverage: No test for shutdown-during-active-transaction scenario.

### Concurrent session access after removal

- Files: `src/server/session_manager.py:71-73`, `src/server/monitor_thread.py:50`, `src/server/transactional_thread.py:459`
- Why fragile: After `session_manager.remove(user_id)` is called (by expire or confirm), a concurrent operation that already fetched the session object (via `get_by_session_id`) may still hold a reference to the removed `UserSession` dataclass. The session's `.seats` list and `.state` could be accessed after removal. This is typically safe because the removal makes future lookups return `None`, and held references remain valid Python objects — but the data they reference (seat coordinates) may have been released.
- Safe modification: Add a `_removed` flag to `UserSession` and check it before operating on the session. Or stale reference checks after each lock acquisition.
- Test coverage: `tests/test_transaction_races.py` covers the double-check pattern but doesn't specifically test stale references.

## Scaling Limits

### Semaphore capacity is fixed at section size

- Current capacity: VIP=50, PREFERENTIAL=150, GENERAL=400 (configured in `src/utils/config.py`). The semaphore is initialized to `rows * cols` — i.e., every seat can be reserved concurrently.
- Limit: Under high load with all seats reserved but not confirmed, new RESERVE attempts fail immediately. The semaphore blocks further reservations until seats are confirmed (moving to SOLD, not counted against semaphore) or released.
- Scaling path: The semaphore capacity could be set higher than physical seats (allowing overbooking), but this would require additional logic to prevent overselling at confirm time. Currently, the semaphore acts as a reservation-buffer limiter, which is correct for the current design.

### In-memory state only — no persistence

- Current capacity: All data (sessions, seat matrix, reservations) lives in Python objects in the single server process. No database, no file persistence (except logs).
- Limit: Server restart loses all state. All active sessions, reserved seats, and confirmed (SOLD) seats are reset. The `_cleanup_stale_reservations` startup method tries to recover from the reservation table, but since the table is dead code, cleanup is effectively a no-op.
- Scaling path: Add SQLite or file-based persistence for the seat matrix state at minimum. Use WAL mode for concurrent reads during persistence writes.

## Dependencies at Risk

### Textual (TUI framework)

- Risk: The TUI depends on `textual>=0.70.0` (in `pyproject.toml:16`). Textual is actively developed and has frequent breaking changes between minor versions. The codebase pins to a minimum version (`>=0.70.0`) rather than a lock range, meaning a future `uv sync` could pull a breaking Textual update.
- Impact: TUI breaks on startup or has visual/behavioral regressions after dependency update.
- Migration plan: Pin to a specific version range (e.g., `textual>=0.70.0,<1.0.0`) and test upgrades explicitly before accepting them. The `uv.lock` file does lock the current version but is git-committed, meaning collaborators get the same version. The risk is on fresh installs where `uv.lock` is regenerated.

### No type checker configured

- Risk: The project uses type hints (`Optional`, `List`, `Dict`, `Tuple` from `typing`) but has no mypy or pyright configuration. There's no type checking in CI or pre-commit hooks.
- Impact: Type errors can go undetected. The `Reservation.seats: list` field (no generic parameter) in `reservation_table.py:13` would be flagged by a strict type checker. Several `# type: ignore` comments would be necessary for the semaphore `._value` access used in tests.
- Migration plan: Add a `mypy.ini` or `pyproject.toml [tool.mypy]` section. Start with loose settings and gradually tighten.

## Test Coverage Gaps

### Minimal TUI test coverage

- What's not tested: The `frontend_tui/` package has only one test file (`tests/test_tui_seat_map.py`, 160 lines) covering seat map rendering with mocked widgets. The other ~1100 lines of `app.py` (worker threads, network client calls, session tracking, event handling, button wiring, log tailing, metrics) have zero automated tests.
- Files: `frontend_tui/app.py` (1126 lines), `frontend_tui/login_screen.py` (33 lines)
- Risk: Visual regressions, button wiring errors, threading bugs in worker patterns go undetected.
- Priority: Medium (the TUI is the primary user interface).

### No shutdown-during-transaction tests

- What's not tested: Server shutdown while TransactionalThreads are mid-execution. No test verifies that locks are released, sockets are properly closed, and no seat state is corrupted.
- Files: `src/server/concert_server.py:140-161`
- Risk: Data corruption on server restart. Seats may remain in RESERVED state permanently if the shutdown doesn't properly release them.
- Priority: High.

### No TTL indefinite extension test

- What's not tested: A user repeatedly reserving seats to extend TTL beyond the configured 300s. The `is_expired` property uses `last_activity` which resets on every operation.
- Files: `src/server/session_manager.py:21-24`
- Risk: Resource starvation — a user can hold seats indefinitely.
- Priority: Medium.

### No RESERVE_SELECTED end-to-end test

- What's not tested: The `RESERVE_SELECTED` action end-to-end (client -> validator -> handler). Since the validator blocks this action, no test exercises the full path. The `test_reserve_batch.py` tests use `RESERVE_BATCH`, not `RESERVE_SELECTED`.
- Files: `src/server/transactional_thread.py:304-405`, `src/utils/protocol_validator.py:94`
- Risk: The feature is broken in production (see Known Bugs).
- Priority: High (must fix the validator before testing the handler).

---

*Concerns audit: 2026-06-04*
