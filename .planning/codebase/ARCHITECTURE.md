<!-- refreshed: 2026-06-01 -->
# Architecture

**Analysis Date:** 2026-06-01

## System Overview

The ConcertSync system is a **multi-threaded TCP server-client concert seat reservation** system. It uses **JSON over TCP** for client-server communication and a **thread-per-connection** concurrency model with a strict **lock hierarchy** to prevent deadlocks. The server manages shared in-memory state (seat matrix, reservation table, semaphores) protected by mutexes acquired in a fixed global order.

```text
┌──────────────────────────────────────────────────────────────────┐
│                       Entry Points                               │
│     main.py / desktop_launcher.py / frontend_tui/__main__.py      │
└──────────┬──────────────────────────────────────┬────────────────┘
           │                                      │
           ▼                                      ▼
┌──────────────────────┐        ┌──────────────────────────────┐
│    Client Layer      │        │       Frontend (TUI)         │
│ src/client/          │◄───────│ frontend_tui/app.py          │
│ concert_client.py    │  JSON  │ ConcertTextualApp (Textual)  │
└──────────────────────┘   TCP  └──────────────┬───────────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Server Layer                                 │
│  src/server/                                                      │
│                                                                   │
│  ┌─────────────────┐   ┌───────────────────┐   ┌──────────────┐  │
│  │ ListenerThread  │──▶│TransactionalThread│──▶│ ConcertServer│  │
│  │ (accepts conns) │   │ (per-conn logic)  │   │ (orchestr.)  │  │
│  └─────────────────┘   └───────────────────┘   └──────┬───────┘  │
│                                                        │          │
│  ┌─────────────────┐                                   │          │
│  │ MonitorThread   │◄──────────────────────────────────┘          │
│  │ (TTL expiry)    │                                              │
│  └─────────────────┘                                              │
└──────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Shared Resources Layer                         │
│  src/shared_resources/                                            │
│  ┌──────────────┐ ┌─────────────────┐ ┌──────────────────────┐   │
│  │ SeatMatrix   │ │ReservationTable │ │ SemaphoreManager     │   │
│  │(2D grid/sec) │ │(tx dict + TTL) │ │(per-section caps)    │   │
│  └──────┬───────┘ └────────┬────────┘ └──────────────────────┘   │
│         │                  │                                       │
│         ▼                  ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              Synchronization Layer                            │ │
│  │  src/synchronization/                                         │ │
│  │  ┌────────────────┐  ┌─────────────────────────────────┐     │ │
│  │  │  MutexManager  │  │  acquire_section_locks          │     │ │
│  │  │  (context mgrs)│──│  (lock hierarchy enforcer)      │     │ │
│  │  └────────────────┘  └─────────────────────────────────┘     │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Utilities Layer                                │
│  src/utils/                                                       │
│  ┌─────────────┐ ┌────────────┐ ┌────────────────┐ ┌─────────┐  │
│  │config.py    │ │enums.py    │ │protocol_val..py│ │error_.. │  │
│  │(constants)  │ │(enums)     │ │(validation)    │ │(factory)│  │
│  └─────────────┘ └────────────┘ └────────────────┘ └─────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `ConcertServer` | Owns all shared resources, starts listener + monitor threads | `src/server/concert_server.py` |
| `ListenerThread` | Accepts TCP connections, spawns `TransactionalThread` per client | `src/server/listener_thread.py` |
| `TransactionalThread` | Handles one client request: validates, acquires locks, processes action | `src/server/transactional_thread.py` |
| `MonitorThread` | Daemon thread that expires timed-out reservations every 1s | `src/server/monitor_thread.py` |
| `ConcertClient` | TCP client with local input validation and response deserialization | `src/client/concert_client.py` |
| `SeatMatrix` | 3-section 2D grid storing `SeatState` per seat; per-section `Lock` + `RLock` | `src/shared_resources/seat_matrix.py` |
| `ReservationTable` | In-memory `dict` of `Reservation` dataclass; `Lock` + `Condition` | `src/shared_resources/reservation_table.py` |
| `SemaphoreManager` | Per-section `threading.Semaphore` tracking remaining capacity | `src/shared_resources/semaphore_manager.py` |
| `GlobalLog` | Thread-safe append-only file logger with timestamp | `src/shared_resources/global_log.py` |
| `MutexManager` | Context managers: `table()`, `sections()`, `table_and_sections()` | `src/synchronization/mutex_manager.py` |
| `acquire_section_locks` | Lock-acquisition context manager that enforces hierarchy order | `src/synchronization/lock_hierarcky.py` |
| `ConcertTextualApp` | Textual TUI client: 1s polling, seat map, session tracking | `frontend_tui/app.py` |

## Pattern Overview

**Overall:** Thread-per-connection TCP server with shared in-memory state protected by a tiered lock hierarchy.

**Key Characteristics:**
- **Thread-per-connection:** Each client gets a dedicated `TransactionalThread` spawned by `ListenerThread`
- **Shared mutable state:** `SeatMatrix`, `ReservationTable`, `SemaphoreManager` live in `ConcertServer` and are shared across all transaction threads
- **Lock hierarchy:** Locks are always acquired in the order `table → sections`, and section locks are acquired in `Section` enum value order (VIP=0, PREFERENTIAL=1, GENERAL=2) to prevent deadlock
- **Context-manager lock scope:** All mutex acquisition uses `with` context managers provided by `MutexManager`
- **Dual-layer validation:** Client validates before sending (`protocol_validator.py`); server re-validates on receipt in `TransactionalThread`
- **JSON-over-TCP framing:** Single JSON object per send/receive; no message delimiters; caller is responsible for boundaries

## Layers

**Entry Point Layer:**
- Purpose: Boot the server and/or TUI
- Location: Project root and `frontend_tui/`
- Contains: `main.py` (headless server), `desktop_launcher.py` (server + TUI), `frontend_tui/__main__.py` (standalone TUI)
- Depends on: `src/server/`, `src/client/`, `frontend_tui/`
- Used by: Shell scripts (`scripts/run.sh`), end user

**Client Layer:**
- Purpose: TCP client with input validation and typed error handling
- Location: `src/client/concert_client.py`
- Contains: `ConcertClient` class, exception hierarchy (`SeatNotAvailableError`, `NoCapacityError`, etc.)
- Depends on: `src/utils/protocol_validator.py`
- Used by: `ConcertTextualApp` in `frontend_tui/app.py`

**Server Layer:**
- Purpose: TCP server that accepts connections, dispatches work, monitors TTL
- Location: `src/server/`
- Contains: `ConcertServer`, `ListenerThread`, `TransactionalThread`, `MonitorThread`
- Depends on: `src/shared_resources/*`, `src/synchronization/*`, `src/utils/*`
- Used by: Entry points

**Shared Resources Layer:**
- Purpose: Thread-safe in-memory data structures for seat state, reservations, capacity, and logging
- Location: `src/shared_resources/`
- Contains: `SeatMatrix`, `ReservationTable`, `SemaphoreManager`, `GlobalLog`
- Depends on: `src/utils/config.py`, `src/utils/enums.py`
- Used by: Server layer

**Synchronization Layer:**
- Purpose: Lock acquisition helpers ensuring deadlock-free ordering
- Location: `src/synchronization/`
- Contains: `MutexManager`, `acquire_section_locks` (in `lock_hierarcky.py`)
- Depends on: `src/shared_resources/`
- Used by: Server layer

**Utilities Layer:**
- Purpose: Enums, configuration, protocol validation, error response builders
- Location: `src/utils/`
- Contains: `config.py`, `enums.py`, `protocol_validator.py`, `error_responses.py`
- Depends on: Nothing inside `src/` (pure utility)
- Used by: All layers

## Data Flow

### Primary Request Path (RESERVE)

1. **Client constructs request** — `ConcertClient.reserve_seat(section, row, col)` validates inputs locally via `validate_reserve_payload()` (`src/client/concert_client.py:166-175`)
2. **TCP send** — `send_request()` opens socket, serializes to JSON, sends over TCP to `host:port` (`src/client/concert_client.py:88-119`)
3. **Server accepts** — `ListenerThread.run()` accepts connection on `server_socket`, spawns `TransactionalThread` (`src/server/listener_thread.py:16-18`)
4. **Thread receives** — `TransactionalThread.run()` reads JSON from socket (`src/server/transactional_thread.py:39`)
5. **Validation** — `validate_request()` parses JSON, validates action, validates RESERVE payload (`src/server/transactional_thread.py:42`)
6. **Lock acquisition** — `handle_reserve()` acquires `table_and_sections([section])` lock: table lock first, then section locks in enum order (`src/server/transactional_thread.py:132`)
7. **Seat state check** — Verifies seat is `AVAILABLE` in `SeatMatrix` (`src/server/transactional_thread.py:136-139`)
8. **Seat marking** — Marks seat as `RESERVED` in `SeatMatrix` (`src/server/transactional_thread.py:141`)
9. **Semaphore acquire** — Acquires semaphore slot (non-blocking); rolls back seat on failure (`src/server/transactional_thread.py:144-148`)
10. **Transaction creation** — `ReservationTable.add_reservation()` creates `Reservation` with UUID, TTL=300s, status=`ACTIVE` (`src/server/transactional_thread.py:151-156`)
11. **Lock release** — Context manager releases section locks then table lock (reverse order)
12. **Response** — `build_success_response(transaction_id, ttl)` sent back over TCP (`src/server/transactional_thread.py:163`)
13. **Client receives** — `send_request()` reads response, validates via `validate_response()`, maps FAILURE codes to exceptions (`src/client/concert_client.py:100-114`)

### Batch Reserve Flow (RESERVE_BATCH)

1. Same as RESERVE but `handle_reserve_batch()` groups seats by section, acquires ALL section locks in order (`src/server/transactional_thread.py:236`)
2. Validates ALL seats are `AVAILABLE` before any state change (`src/server/transactional_thread.py:238-247`)
3. Marks all seats as `RESERVED` (`src/server/transactional_thread.py:250-253`)
4. Acquires ALL required semaphore slots across sections (`src/server/transactional_thread.py:256-273`)
5. Single `Reservation` with `(section, row, col)` tuples for all seats (`src/server/transactional_thread.py:287-291`)
6. On any failure at any step, rolls back ALL state changes (no partial reserve) (`src/server/transactional_thread.py:262-272`)

### TTL Expiry Flow

1. `MonitorThread` (daemon) polls every 1s (`src/server/monitor_thread.py:15`)
2. Calls `reservation_table.get_expired_reservations()` to find ACTIVE reservations past TTL (`src/server/monitor_thread.py:16`)
3. For each expired tx: acquires table lock, checks state, marks seats `AVAILABLE`, releases semaphore slots, deletes reservation (`src/server/monitor_thread.py:41-62`)

### Query Flow (QUERY / QUERY_SEAT_MAP)

1. Client sends `QUERY` or `QUERY_SEAT_MAP` action
2. Server acquires ALL section locks in order for a globally consistent snapshot (`src/server/transactional_thread.py:434` / `:462`)
3. Counts seats by state (AVAILABLE/RESERVED/SOLD) or serializes full state matrix
4. Returns snapshot in response

**State Management:**
- All state is **in-memory** (no database)
- `SeatMatrix.seats` is a `dict[Section, list[list[SeatState]]]` — 2D grid per section
- `ReservationTable.reservations` is a `dict[str, Reservation]` — UUID-keyed transaction map
- `SemaphoreManager.s_sections` is a `dict[Section, Semaphore]` — per-section capacity
- `GlobalLog` appends to `logs/system.log` on disk (thread-safe with `Lock`)

## Key Abstractions

**ConcertServer (Orchestrator):**
- Purpose: Owns all shared resources, starts/stops threads, serves as registry passed to child threads
- Files: `src/server/concert_server.py`
- Pattern: Facade / registry — child threads access `self.server.seat_matrix`, `self.server.mutex_manager`, etc.

**TransactionalThread (Request Handler):**
- Purpose: Handles exactly one client request, then exits
- Files: `src/server/transactional_thread.py`
- Pattern: Thread-per-connection (not a thread pool — each accepted connection creates a new thread)

**MutexManager (Lock Orchestration):**
- Purpose: Provides context managers that acquire/release locks in guaranteed hierarchy order
- Files: `src/synchronization/mutex_manager.py`
- Pattern: Context manager with nested lock acquisition

**acquire_section_locks (Lock Hierarchy Enforcer):**
- Purpose: Acquires section `Lock` objects sorted by `Section.value`; releases in reverse order
- Files: `src/synchronization/lock_hierarcky.py`
- Pattern: Generator-based context manager with ordered `acquire()`/`release()` calls

**Reservation (Transaction Dataclass):**
- Purpose: Immutable-ish data record for each reservation
- Files: `src/shared_resources/reservation_table.py:9-17`
- Pattern: Python `@dataclass` with fields: `transaction_id`, `section`, `seats`, `seat_id`, `timestamp_creation`, `ttl_secs`, `state`

**ConcertClient (Protocol Client):**
- Purpose: Network client with input validation, response validation, and typed exception mapping
- Files: `src/client/concert_client.py`
- Pattern: Methods mirror server actions (`reserve_seat`, `confirm`, `cancel`, `query`, `query_seat_map`); all raise domain-specific exceptions

## Entry Points

**Headless Server:**
- Location: `main.py`
- Triggers: `python main.py` or `scripts/run.sh server`
- Responsibilities: Creates `ConcertServer(port=9999)`, starts it, blocks on `time.sleep` loop until `Ctrl+C`

**Desktop Launcher (Server + TUI):**
- Location: `desktop_launcher.py`
- Triggers: `python desktop_launcher.py` or `scripts/run.sh both`
- Responsibilities: Starts server thread-synchronously, then opens `ConcertTextualApp` TUI; stops server when TUI exits

**TUI Only:**
- Location: `frontend_tui/__main__.py`
- Triggers: `python -m frontend_tui` or `scripts/run.sh tui`
- Responsibilities: Launches `ConcertTextualApp` standalone (expects server already running on port 9999)

## Architectural Constraints

- **Threading:** Multi-threaded with no thread pool; each `TransactionalThread` is a fresh `threading.Thread`. Monitor is a daemon thread. TUI spawns daemon worker threads for async requests.
- **Global state:** All shared state is owned by the single `ConcertServer` instance and passed by reference to child threads. No module-level singletons.
- **Lock hierarchy:** `table()` lock MUST always be acquired BEFORE `sections()` locks. Section locks MUST be acquired in `Section` enum value order (0, 1, 2). Violating this order would cause deadlocks.
- **Lock scope:** All lock acquisition is via `with` context managers — there is no manual `.acquire()` / `.release()` outside `lock_hierarcky.py`.
- **Circular imports:** None detected — utilities depend on nothing, shared resources depend on utilities, synchronization depends on shared resources, server depends on everything above.
- **One request per connection:** Each TCP connection is used for exactly one request/response cycle (`TransactionalThread` reads once, responds once, closes socket).

## Anti-Patterns

### Dead code after return in MonitorThread.expire_reservation

**What happens:** In `src/server/monitor_thread.py:46`, after `return` inside the `with` block, lines 49-56 are unreachable dead code. The section-release logic for expired reservations is never executed for multi-seat reservations.

**Why it's wrong:** The `return` at line 47 exits instantly, skipping the seat-release loop (lines 49-54), the `delete_reservation` call (line 56), and the semaphore release (lines 60-62). Only the initial check "is reservation ACTIVE" runs, but no cleanup happens — the expired tx stays in the table forever.

**Do this instead:** Remove the premature `return` on line 47. The indented block after the `return` should be at the same level as the `if` check, not nested inside it. See `archive/adr-0001-segment-a-locking-idempotency.md` for the ADR.

### Semaphore stale tracking

**What happens:** `ReservationTable.add_reservation()` acquires a semaphore slot (`semaphore_mgr.acquire(section, blocking=False)`), but if `add_reservation()` fails (exception), the semaphore is released in the catch block. However, the semaphore tracks *capacity*, not *used slots* — if a thread crashes between acquiring the semaphore and releasing the section lock, the semaphore is permanently decremented.

**Why it's wrong:** Semaphore slots are never reconciled against actual seat state. A crash leaves the semaphore permanently short by 1. Over many crashes, the semaphore can reach 0 even though seats are actually AVAILABLE.

**Do this instead:** Consider a capacity counter that is derived from seat state on startup (or periodically reconciled), rather than relying solely on semaphore acquire/release parity.

## Error Handling

**Strategy:** Three-tier response statuses — `SUCCESS`, `FAILURE` (business rejection), `ERROR` (technical/protocol failure). Client maps these to typed exceptions.

**Patterns:**
- `build_success_response(**kwargs)` — flexible kwargs-based success response builder (`src/utils/error_responses.py:15-39`)
- `build_failure_response(error_code, message)` — business logic rejection with deterministic error codes (`src/utils/error_responses.py:42-71`)
- `build_error_response(error_code, message)` — protocol violation / internal error (`src/utils/error_responses.py:74-104`)
- Client-side: `ERROR_CODE_TO_EXCEPTION` dict maps error codes to specific exception classes (`src/client/concert_client.py:62-67`)
- Server-side rollback: If RESERVE fails after marking seat, `handle_reserve` has a try/catch with explicit rollback of seat state and semaphore (`src/server/transactional_thread.py:165-185`)

## Cross-Cutting Concerns

**Logging:** `GlobalLog` (`src/shared_resources/global_log.py`) — thread-safe file appender with ISO timestamps. Written to `logs/system.log`. Used by `ConcertServer`, `ListenerThread`, `TransactionalThread`, `MonitorThread`. Each log entry has an event type tag (SERVER, THREAD, RESERVE, CONFIRM, CANCEL, EXPIRE, ERROR, RESERVE_BATCH).

**Validation:** `protocol_validator.py` (`src/utils/protocol_validator.py`) — centralized validation pipeline: `validate_request()` parses JSON → validates action → validates action-specific payload. Client-side `validate_response()` checks response schema.

**Authentication:** Not implemented. Server accepts all TCP connections with no authentication or authorization.

---

*Architecture analysis: 2026-06-01*
