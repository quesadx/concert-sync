<!-- refreshed: 2026-06-04 -->
# Architecture

**Analysis Date:** 2026-06-04

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         Frontend TUI                                    │
│                    `frontend_tui/app.py`                                │
│              (Textual terminal UI with live polling)                    │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ JSON over TCP (port 9999)
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Client Layer                                     │
│                    `src/client/concert_client.py`                        │
│         (High-level API: reserve_seat, confirm, cancel, query)          │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ JSON over TCP (port 9999)
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Server Layer                                     │
│ `src/server/concert_server.py`  ─  lifecycle, startup, shutdown         │
│ `src/server/listener_thread.py`  ─  accept connections, spawn threads   │
│ `src/server/transactional_thread.py`  ─  per-request handler (actions)  │
│ `src/server/monitor_thread.py`  ─  TTL expiration background thread     │
│ `src/server/session_manager.py`  ─  user session tracking               │
└───────┬───────────────────────────────┬──────────────────────┬──────────┘
        │                               │                      │
        ▼                               ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Shared Resources (In-Memory State)                  │
│ `src/shared_resources/seat_matrix.py`     ─  seat states per section    │
│ `src/shared_resources/reservation_table.py` ─  legacy tx table (stale)  │
│ `src/shared_resources/semaphore_manager.py` ─  per-section capacity     │
│ `src/shared_resources/global_log.py`      ─  file-backed event log      │
└─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Synchronization                                    │
│ `src/synchronization/mutex_manager.py`   ─  context manager orchestration│
│ `src/synchronization/lock_hierarcky.py`  ─  deadlock-free lock ordering  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `ConcertServer` | Server lifecycle: bind, listen, start monitor & listener threads, cleanup/shutdown | `src/server/concert_server.py` |
| `ListenerThread` | Accept incoming TCP connections, spawn `TransactionalThread` per connection | `src/server/listener_thread.py` |
| `TransactionalThread` | Parse and dispatch client requests (RESERVE, RESERVE_BATCH, CONFIRM, CANCEL, QUERY, QUERY_SEAT_MAP); all state mutations happen here | `src/server/transactional_thread.py` |
| `MonitorThread` | Poll expired sessions every 1s, release seats and semaphore slots for timed-out reservations | `src/server/monitor_thread.py` |
| `SessionManager` | Track user sessions: create, retrieve, list active/expired, remove; UUID-based session IDs | `src/server/session_manager.py` |
| `SeatMatrix` | 3-section 2D seat array (5×10 VIP, 10×15 PREFERENTIAL, 20×20 GENERAL); per-section `threading.Lock` for mutual exclusion | `src/shared_resources/seat_matrix.py` |
| `ReservationTable` | Legacy in-memory transaction table with TTL tracking; used only for startup stale cleanup | `src/shared_resources/reservation_table.py` |
| `SemaphoreManager` | Per-section `threading.Semaphore` enforcing total seat capacity limits | `src/shared_resources/semaphore_manager.py` |
| `GlobalLog` | Thread-safe file-backed logger writing to `logs/system.log` | `src/shared_resources/global_log.py` |
| `MutexManager` | Context-manager orchestration for lock acquisition: `table()`, `sections()`, `table_and_sections()` | `src/synchronization/mutex_manager.py` |
| `ConcertClient` | High-level TCP client: sends JSON requests, validates responses, maps error codes to typed exceptions | `src/client/concert_client.py` |
| `ConcertTextualApp` | Textual TUI: live seat map, section tables, session tracking, batch/pending reservations | `frontend_tui/app.py` |
| `LoginScreen` | Textual modal screen capturing user display name | `frontend_tui/login_screen.py` |
| Protocol Validator | Centralized request JSON parsing, field validation, action dispatch, response schema checks | `src/utils/protocol_validator.py` |
| Error Response Builders | Factory functions producing deterministic SUCCESS/FAILURE/ERROR JSON responses | `src/utils/error_responses.py` |

## Pattern Overview

**Overall:** Client-Server over raw TCP sockets with JSON protocol (v1.0), in-memory shared state, and thread-per-connection concurrency.

**Key Characteristics:**
- **Thread-per-connection model:** Each TCP client gets a dedicated `TransactionalThread` spawned by `ListenerThread`
- **Lock hierarchy deadlock prevention:** All section locks acquired in `Section` enum value order (VIP=0 → PREFERENTIAL=1 → GENERAL=2) via `lock_hierarcky.py`; locks released in reverse order
- **Atomic transactions:** RESERVE, RESERVE_BATCH, CONFIRM, and CANCEL acquire all needed locks before mutating state; full rollback on any failure
- **Tri-state response protocol:** Every response has `status` ∈ {`SUCCESS`, `FAILURE`, `ERROR`} with deterministic error codes matching `protocol-contract-v1.md`
- **In-memory only:** No database; all seat state, sessions, and semaphores live in Python data structures
- **TTL-based reservation expiry:** Active reservations expire after 300s; `MonitorThread` sweeps every 1s and releases seats
- **Dual-layer validation:** Client (`ConcertClient`) validates inputs locally before sending; Server (`TransactionalThread`) validates on receipt

## Layers

**Frontend TUI Layer:**
- Purpose: Terminal user interface for interactive seat reservation
- Location: `frontend_tui/`
- Contains: Textual `App` subclass, `Screen` subclass, CSS theme
- Depends on: `src/client/concert_client.py`, `src/utils/config.py`, `src/utils/enums.py`
- Used by: End users (run via `python -m frontend_tui` or `desktop_launcher.py`)

**Client Layer:**
- Purpose: High-level Python API for the JSON-over-TCP protocol; wraps socket communication, validates responses, maps error codes to typed exceptions
- Location: `src/client/`
- Contains: `ConcertClient` class, exception hierarchy (`ConcertClientError` → `SeatNotAvailableError`, `NoCapacityError`, `TransactionNotFoundError`, etc.)
- Depends on: `src/utils/protocol_validator.py`
- Used by: `frontend_tui/app.py`, external scripts/tests

**Server Layer:**
- Purpose: Accept TCP connections, parse JSON requests, orchestrate state mutations through shared resources
- Location: `src/server/`
- Contains: `ConcertServer` (lifecycle), `ListenerThread` (accept loop), `TransactionalThread` (request dispatch), `MonitorThread` (expiry sweep), `SessionManager` (user sessions)
- Depends on: `src/shared_resources/`, `src/synchronization/`, `src/utils/`
- Used by: `main.py`, `desktop_launcher.py`

**Shared Resources Layer:**
- Purpose: In-memory state holders with thread-safe access; the "database" of the system
- Location: `src/shared_resources/`
- Contains: `SeatMatrix` (seat grid + locks), `ReservationTable` (legacy tx table), `SemaphoreManager` (capacity bounds), `GlobalLog` (file logger)
- Depends on: `src/utils/config.py`, `src/utils/enums.py`
- Used by: Server layer (exclusively)

**Synchronization Layer:**
- Purpose: Centralized lock orchestration enforcing deadlock-free section lock ordering
- Location: `src/synchronization/`
- Contains: `MutexManager` (context managers), `lock_hierarcky.py` (lock sort + acquire/release)
- Depends on: Nothing external
- Used by: Server layer's `TransactionalThread` and `MonitorThread`

**Utilities Layer:**
- Purpose: Configuration constants, enums, protocol validation, error response factories
- Location: `src/utils/`
- Contains: `config.py` (dimensions, TTL, port), `enums.py` (Section, SeatState, ReservationStatus), `protocol_validator.py` (request/response validation), `error_responses.py` (response builders)
- Depends on: Only Python stdlib
- Used by: All other layers

## Data Flow

### Primary Request Path (RESERVE single seat)

1. **TUI triggers reservation** — User clicks "Reserve Seat" or presses `r` in `ConcertTextualApp` → `_reserve_single_seat()` (`frontend_tui/app.py:500`)
2. **Client validates locally** — `ConcertClient.reserve_seat()` calls `validate_reserve_payload()` (`src/client/concert_client.py:175`)
3. **Client sends JSON over TCP** — `ConcertClient.send_request()` opens socket, sends `{"action": "RESERVE", "section": "VIP", "row": 0, "col": 0, "user_id": "Alice"}` (`src/client/concert_client.py:91-93`)
4. **Server accepts connection** — `ListenerThread.run()` accepts, spawns `TransactionalThread` (`src/server/listener_thread.py:16-18`)
5. **Server validates** — `TransactionalThread.run()` calls `validate_request()` which parses JSON, validates action, validates payload (`src/server/transactional_thread.py:42-46`)
6. **Server dispatches** — Routes to `handle_reserve()` (`src/server/transactional_thread.py:108`)
7. **Server acquires locks** — `handle_reserve()` calls `mutex_manager.table_and_sections([section])` which acquires `reservation_table.mutex_table` then section lock in hierarchy order (`src/synchronization/mutex_manager.py:28-31`)
8. **Server mutates state** — Checks seat is `AVAILABLE`, sets to `RESERVED` in `SeatMatrix`, acquires semaphore slot, appends seat to `UserSession`, resets TTL (`src/server/transactional_thread.py:137-163`)
9. **Server logs** — `GlobalLog.append("RESERVE", ...)` writes to `logs/system.log` (`src/server/transactional_thread.py:160-163`)
10. **Server responds** — Sends `{"status": "SUCCESS", "transaction_id": "<uuid>", "ttl": 300}` via socket (`src/server/transactional_thread.py:67, 165`)
11. **Client parses response** — `ConcertClient.send_request()` validates response schema with `validate_response()` (`src/client/concert_client.py:109-111`)
12. **TUI updates** — Worker thread calls `call_from_thread()` to update `TrackedSession`, section table, seat map, and status line (`frontend_tui/app.py:567-580`)

### Transaction Confirmation Path

1. TUI user enters transaction_id and clicks "Confirm" → `_confirm_transaction()` (`frontend_tui/app.py:822`)
2. Client sends `{"action": "CONFIRM", "transaction_id": "..."}` → `ConcertClient.confirm()` (`src/client/concert_client.py:203`)
3. Server `handle_confirm()` looks up session by `session_id`, verifies ownership and ACTIVE state (`src/server/transactional_thread.py:426-435`)
4. Acquires `table_and_sections(ordered_sections)`, double-checks session state inside lock (`src/server/transactional_thread.py:440-444`)
5. Transitions all seats from `RESERVED` → `SOLD`, sets session state to `CONFIRMED`, removes from SessionManager (`src/server/transactional_thread.py:446-459`)
6. Responds `{"status": "SUCCESS", "transaction_id": "..."}`

### TTL Expiration Path (background)

1. `MonitorThread.run()` sleeps 1s, calls `session_manager.get_expired()` (`src/server/monitor_thread.py:15-16`)
2. For each expired session, calls `expire_session()` → groups seats by section, acquires `table_and_sections()` (`src/server/monitor_thread.py:33-37`)
3. Double-checks session still ACTIVE inside lock (races with CONFIRM/CANCEL) (`src/server/monitor_thread.py:39-41`)
4. Transitions `RESERVED` → `AVAILABLE` in `SeatMatrix`, releases semaphore slots, removes session (`src/server/monitor_thread.py:43-54`)
5. Logs expiration event (`src/server/monitor_thread.py:57-60`)

### Query Path (refresh)

1. TUI's `_refresh_query_worker()` calls `client.query()` and `client.query_seat_map()` on a daemon thread every second (`frontend_tui/app.py:422-435`)
2. Server `handle_query()` acquires ALL section locks atomically via `mutex_manager.sections(list(Section))`, counts seats per section, releases locks (`src/server/transactional_thread.py:532-548`)
3. Server `handle_query_seat_map()` acquires ALL section locks, serializes seat matrix, tags requesting user's seats as `OWN_RESERVED` for visual distinction (`src/server/transactional_thread.py:554-599`)
4. TUI updates `section_snapshot` dict and `seat_map_snapshot` dict, re-renders DataTable widgets

**State Management:**
- All state is in-memory (no database). Server restart loses all reservations.
- `SeatMatrix.seats`: 3-level dict → `{Section: [[SeatState, ...], ...]}` — co-located with per-section `threading.Lock` instances in `mutex_sections`
- `SessionManager._sessions`: `Dict[str, UserSession]` protected by `threading.Lock` — maps `user_id` → session
- `SemaphoreManager.s_sections`: `Dict[Section, threading.Semaphore]` — no explicit lock needed (Semaphore is atomic)
- `ReservationTable.reservations`: Legacy `Dict[str, Reservation]` with `mutex_table` lock — used only for startup stale cleanup
- `GlobalLog`: file-backed with `mutex_log` thread lock

## Key Abstractions

**SeatMatrix:**
- Purpose: Grid representation of all seats across 3 sections (VIP: 5×10, PREFERENTIAL: 10×15, GENERAL: 20×20)
- Examples: `src/shared_resources/seat_matrix.py`
- Pattern: Each section has its own `threading.Lock` (`mutex_sections`) and `threading.RLock` (`rwlocks`); state values are `SeatState` enum members. The `mutex_sections` locks are the primary synchronization primitive used throughout the system.

**SessionManager:**
- Purpose: Tracks per-user reservation sessions with TTL; creates UUID session IDs, provides lookup by user_id or session_id
- Examples: `src/server/session_manager.py`
- Pattern: `UserSession` is a `@dataclass` with `seats: List[Tuple[Section, int, int]]`, `state: ReservationStatus`, and `last_activity: float` for TTL calculation. Protected by `threading.Lock`.

**MutexManager (lock orchestration):**
- Purpose: Provides context managers (`table()`, `sections()`, `table_and_sections()`) that acquire locks in deadlock-free hierarchy order
- Examples: `src/synchronization/mutex_manager.py`, `src/synchronization/lock_hierarcky.py`
- Pattern: Section locks sorted by `Section.value` (VIP=0 < PREFERENTIAL=1 < GENERAL=2); acquired in ascending order, released in reverse. Table lock always acquired before section locks.

**Protocol Validator:**
- Purpose: Centralized JSON request/response validation with deterministic error codes
- Examples: `src/utils/protocol_validator.py`
- Pattern: `validate_request()` is the single entry point — it chains `validate_request_json()` → `validate_action()` → action-specific validators (`validate_reserve_payload()`, `validate_confirm_payload()`, etc.). Returns `(bool, str, dict)` tuples.

**Response Factories:**
- Purpose: Ensure all server responses conform to protocol-contract-v1.md schema
- Examples: `src/utils/error_responses.py`
- Pattern: Three builder functions (`build_success_response`, `build_failure_response`, `build_error_response`) plus convenience wrappers (`error_invalid_section`, `failure_seat_not_available`, etc.) that internally import `ErrorCode` constants.

## Entry Points

**Server-only:**
- Location: `main.py`
- Triggers: `python main.py`
- Responsibilities: Instantiates `ConcertServer(port=9999)`, calls `start()`, blocks on `while True: time.sleep(1)` until Ctrl+C, then calls `stop()`

**TUI-only (separate client):**
- Location: `frontend_tui/__main__.py`
- Triggers: `python -m frontend_tui`
- Responsibilities: Instantiates `ConcertTextualApp`, calls `app.run()`. User must connect to a running server via the Connect button.

**Desktop launcher (server + TUI):**
- Location: `desktop_launcher.py`
- Triggers: `python desktop_launcher.py`
- Responsibilities: Starts `ConcertServer` in background, then runs `ConcertTextualApp`; shuts down server when TUI exits. Used for single-machine demos.

**Script orchestrator:**
- Location: `scripts/run.sh`
- Triggers: `bash scripts/run.sh [server|tui|both|test]`
- Responsibilities: Handles `uv`/venv setup, starts server, waits for port readiness, launches TUI, runs tests. The `both` mode is the primary development workflow.

## Architectural Constraints

- **Threading:** Thread-per-connection model. Each client socket gets a dedicated `TransactionalThread`. A single background `MonitorThread` sweeps expired sessions. No thread pools or async I/O.
- **Global state:** Server holds references to all shared resources (`seat_matrix`, `semaphore_mgr`, `reservation_table`, `global_log`, `mutex_manager`, `session_manager`) as instance attributes. No module-level singletons.
- **Circular imports:** Not detected. Dependencies flow unidirectionally: `utils` ← `shared_resources` ← `synchronization` ← `server` ← `main`; `client` depends on `utils`. TUI depends on `client` and `utils`.
- **Lock acquisition order:** MUST always be: table lock → section locks in `Section.value` ascending order. This is the critical deadlock-prevention invariant enforced by `lock_hierarcky.py`.
- **No DTOs/separate models:** Domain state objects (`SeatMatrix`, `SessionManager`) serve as both storage and API. No repository pattern or data access layer — all code mutates state directly through locks.

## Anti-Patterns

### Legacy ReservationTable alongside SessionManager

**What happens:** `ReservationTable` (`src/shared_resources/reservation_table.py`) was the original transaction tracking mechanism. `SessionManager` (`src/server/session_manager.py`) was introduced later as a replacement. The table lock (`reservation_table.mutex_table`) is still acquired in the `table_and_sections()` context manager but `ReservationTable` is only used during startup stale cleanup.
**Why it's wrong:** Two systems track reservation state but only one is the source of truth. The table lock is acquired unnecessarily during normal operations (it protects an effectively empty table).
**Do this instead:** Extract the table lock into `MutexManager` independently of `ReservationTable`, or remove `ReservationTable` entirely and convert `mutex_table` to a standalone lock. The `table_and_sections()` pattern should acquire the `SessionManager._lock` instead.

### Per-request socket connection in ConcertClient

**What happens:** `ConcertClient.send_request()` opens a new TCP socket per request (`src/client/concert_client.py:91`), sends the JSON payload, reads the response, and closes the socket.
**Why it's wrong:** TCP connection setup/teardown overhead per request. For the TUI's 1-second polling, this generates 2 new connections per second (QUERY + QUERY_SEAT_MAP).
**Do this instead:** Maintain a persistent socket connection, or batch QUERY and QUERY_SEAT_MAP into a single request. For a localhost demo this is acceptable but would scale poorly.

### Duplicate seat-counting logic

**What happens:** Both `TransactionalThread._count_section_seats()` (`src/server/transactional_thread.py:601`) and `SeatMatrix.get_section_counts()` (`src/shared_resources/seat_matrix.py:40`) implement identical seat-counting loops.
**Why it's wrong:** DRY violation; if counting logic changes, both must be updated.
**Do this instead:** `TransactionalThread._count_section_seats()` should delegate to `SeatMatrix.get_section_counts()`.

## Error Handling

**Strategy:** Three-tier response protocol with deterministic error codes.

**Response statuses:**
- **SUCCESS:** Operation completed; includes action-specific payload (e.g., `transaction_id`, `ttl`, `sections`, `seat_map`)
- **FAILURE:** Business logic rejection (seat not available, no capacity, transaction not found/active) — client can retry with different parameters
- **ERROR:** Technical problem (invalid JSON, unknown action, internal exception) — client must fix payload or retry later

**Server-side patterns:**
- Each `handle_*()` method returns a response dict directly; the `run()` method sends it
- Validation failures return `build_error_response(ErrorCode.INVALID_PAYLOAD, msg)` early
- State mutations inside `with mutex_manager.table_and_sections():` blocks — exceptions cause rollback
- Unexpected exceptions caught at method level, logged via `global_log.append("ERROR", ...)`, return `error_internal(str(e))`

**Client-side patterns:**
- `ConcertClient.send_request()` calls `_process_response()` which maps `error_code` to typed exceptions (`SeatNotAvailableError`, `NoCapacityError`, etc.)
- Local validation via `validate_*_payload()` raises `InvalidInputError` before sending
- Socket errors raise `ConcertClientError`

## Cross-Cutting Concerns

**Logging:** `GlobalLog` writes timestamped, threadID-tagged entries to `logs/system.log`. Format: `[ISO_TIMESTAMP] [EVENT_TYPE] [TID:N] message`. Used by server for audit trail; tailed by TUI's `LogTailer` for live event display.

**Validation:** Centralized in `src/utils/protocol_validator.py`. Entry point `validate_request(data)` chains JSON parse → action validation → action-specific validation. Both client and server use the same validator functions.

**Authentication:** Minimal — `user_id` is a display name string sent in each request. `LoginScreen` captures it. No passwords, tokens, or sessions beyond the user_id parameter. Ownership of transactions is enforced by comparing `session.user_id` against `request["user_id"]` in CONFIRM/CANCEL handlers.

**Concurrency safety:** All seat state mutations happen inside `with mutex_manager.table_and_sections(...)`. The MonitorThread's `expire_session()` uses the same lock acquisition pattern and double-checks session state inside the lock to avoid racing with in-flight TransactionalThreads.

---

*Architecture analysis: 2026-06-04*
