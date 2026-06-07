<!-- GSD:project-start source:PROJECT.md -->
## Project

**ConcertSync**

ConcertSync is a TCP-based concurrent seat reservation system for a concert venue. A Python server manages seat state across three sections (VIP, PREFERENTIAL, GENERAL) using threading, lock hierarchies, and semaphores. The client frontend connects via JSON over TCP sockets on port 9999. The current frontend is a Textual terminal-based TUI being replaced with a PySide6 desktop GUI.

**Core Value:** Multiple concurrent users can reserve, confirm, and cancel seats without race conditions — the seat matrix always reflects accurate availability, and no seat gets double-sold.

### Constraints

- **Backend stability**: `src/server/`, `src/shared_resources/`, `src/synchronization/`, `src/utils/` must not change significantly — frontend replacement only
- **Protocol compatibility**: The PySide6 client must use the same JSON-over-TCP protocol as the Textual client
- **Tech stack**: Python 3.14, PySide6 (Qt for Python), uv package manager, Nix dev shell
- **Frontend scope**: Only `frontend_tui/` is replaced; a new `frontend_pyside6/` directory is created
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.14 - Entire codebase (server, client, TUI frontend, tests, scripts)
- None - The application is pure Python. (Node.js/pnpm appear in `flake.nix` only as tooling for GSD/OpenCode, not for the application.)
## Runtime
- Python 3.14 (pinned in `.python-version`)
- Nix flake (`flake.nix`) provides reproducible dev environment with nixpkgs unstable
- uv (primary, lockfile: `uv.lock` committed)
- pip + venv (fallback in `scripts/run.sh`)
## Frameworks
- None — The server uses raw `socket` (TCP) with `threading` for concurrency. No web framework, ASGI, or HTTP layer.
- Textual >= 0.70.0 - Terminal UI for seat reservation client (`frontend_tui/app.py`)
- pytest >= 9.0.3 - Test runner and fixture support
- black >= 26.3.1 - Code formatter
- flake8 >= 7.3.0 - Linter
- Nix (`flake.nix`) - Reproducible development shells
## Key Dependencies
- *None beyond Python standard library.* The entire server and client use only `socket`, `threading`, `json`, `uuid`, `time`, `dataclasses`, `enum`, `pathlib`, `collections`, `contextlib`, and `typing` from the standard library.
- black 26.3.1 - Code formatting enforcement
- flake8 7.3.0 - Python linting
- pytest 9.0.3 - Test framework
- textual >= 0.70.0 - Terminal user interface framework
## Configuration
- No `.env` files detected
- All configuration is in-code at `src/utils/config.py`:
- `pyproject.toml` — Project metadata, dependency groups, pytest config
- `flake.nix` + `flake.lock` — Nix development environment
- `.python-version` — Python version pin (3.14)
- `.gitignore` — Standard Python gitignore (venv, __pycache__, logs, etc.)
- `scripts/build_windows_exe.ps1` — Windows packaging (PowerShell)
- `scripts/run.sh` — Cross-platform run script (server, tui, both, test modes)
- `desktop_launcher.py` — Single-process launcher that runs server + TUI together
## Platform Requirements
- Python 3.14 (or 3.13+ likely compatible)
- uv package manager (recommended) or pip + venv
- Optional: Nix with flakes enabled for `nix develop`
- Python 3.14 runtime
- Local filesystem access (for logs at `logs/system.log`)
- No external services required — fully self-contained
- Port 9999 available for TCP
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- `snake_case.py` for all modules — e.g., `concert_server.py`, `protocol_validator.py`, `lock_hierarcky.py`
- `test_<feature>.py` for test files — e.g., `test_protocol_contract.py`, `test_reserve_batch.py`
- `__init__.py` used as barrel files to make directories importable packages
- `PascalCase` — e.g., `ConcertServer`, `SeatMatrix`, `TransactionalThread`, `ListenerThread`, `UserSession`
- Exception classes suffixed with `Error` — e.g., `ConcertClientError`, `InvalidInputError`, `SeatNotAvailableError`
- `snake_case` — e.g., `handle_reserve()`, `check_availability()`, `get_or_create()`, `_process_response()`
- Private methods prefixed with `_` — e.g., `_group_seats_by_section()`, `_initialize_seats()`
- Worker methods suffixed with `_worker` (frontend TUI) — e.g., `_reserve_single_seat_worker()`, `_refresh_query_worker()`
- Factory functions prefixed with `build_` or `error_`/`failure_` — e.g., `build_success_response()`, `error_invalid_section()`, `failure_seat_not_available()`
- `snake_case` for local variables and attributes — e.g., `section_str`, `tx_id`, `ordered_sections`
- Private instance attributes prefixed with `_` — e.g., `self._sessions`, `self._lock`
- Mutex/lock attributes named explicitly — e.g., `self.mutex_table`, `self.rwlocks`, `self.mutex_sections`
- `UPPER_CASE` module-level constants — e.g., `SECTION_CONFIG`, `RESERVATION_TTL`, `SERVER_PORT`
- `PascalCase` Enum classes with `UPPER_CASE` members — e.g., `SeatState.AVAILABLE`, `Section.VIP`
- Error code constants in a nested class — e.g., `ErrorCode.INVALID_PAYLOAD`
- Located in `src/utils/enums.py`
- Values are string-based (not integer) for readability — e.g., `RESERVED = "RESERVED"`
- Cross-referenced by value (`.value`) in protocol messages and storage lookups
## Code Style
- Tool: black v26.3.1 (configured as dev dependency in `pyproject.toml`)
- Indentation: 4 spaces (consistent throughout)
- Line length: ~100 characters observed in practice (black default)
- No `.prettierrc` or `.flake8` config files detected — formatting and linting configured via `pyproject.toml` dependency groups only
- Tool: flake8 v7.3.0 (configured as dev dependency)
- No explicit `.flake8` configuration file — defaults assumed
- F-string usage preferred for string interpolation (e.g., `f"Seat ({row}, {col}) out of bounds"`)
- Triple-quoted docstrings on all public classes, methods, and functions
- Documented with section-style format: brief summary, blank line, detailed description, blank line, Args/Returns sections
- Type hints ARE present in docstring `Args` but are duplicated since actual Python type annotations are also used
- Comments with `=` repeated for visual separation of logical sections:
## Import Organization
- No import path aliases configured (no `@src/` or similar shortcuts)
- All internal imports use full package paths: `from src.server.concert_server import ConcertServer`
- The `tests/` directory uses `src.` prefix for all internal imports
- Some test files manually inject project root into `sys.path`:
- Always use explicit named imports — no wildcard `from module import *`
- Group related imports from same module on one line — `from typing import Dict, List, Optional, Tuple`
- Local/conditional imports used sparingly inside functions only when needed to break circularity or defer import cost
## Error Handling
- **Centralized error factories** in `src/utils/error_responses.py` — functions like `build_success_response()`, `build_error_response()`, `build_failure_response()` return consistent `Dict[str, Any]` shapes
- **Convenience builders** for common errors — `error_invalid_section()`, `failure_seat_not_available()`, `error_internal()`, etc.
- **Protocol validation layer** in `src/utils/protocol_validator.py` — validates request JSON, actions, and payload-specific fields BEFORE business logic runs
- **Deterministic error codes** — `ErrorCode` class in `protocol_validator.py` with constants like `ERR_INVALID_PAYLOAD`, `ERR_SEAT_NOT_AVAILABLE`
- **Client-side exception hierarchy** in `src/client/concert_client.py` — `ConcertClientError` → `ServerError`, `ServerFailureError` → `SeatNotAvailableError`, etc.
- **Error code to exception mapping** — `ERROR_CODE_TO_EXCEPTION` dict maps `ErrorCode` constants to specific exception classes
- **Rollback on failure** in `TransactionalThread` — reserve handlers acquire locks, make state changes, and roll back all changes if any step fails (semaphore, seat state, etc.)
- **Try/except with finally** for socket cleanup — all request handlers close `client_socket` in `finally` block
- Swallow exceptions silently — use `self.server.global_log.append("ERROR", ...)` to always log
- Pass empty `except:` — always catch specific exception types (`except socket.error as e:`, `except Exception as e:`)
## Logging
- Thread-safe file-based logging using `threading.Lock()`
- Format: `[ISO_TIMESTAMP] [EVENT_TYPE] [TID:THREAD_ID] message`
- Event types used: `"SERVER"`, `"THREAD"`, `"ERROR"`, `"EXPIRE"`, `"CLEANUP"`, `"SHUTDOWN"`, `"RESERVE"`, `"CONFIRM"`, `"CANCEL"`, `"RESERVE_BATCH"`, `"QUERY_SEAT_MAP"`
- Server lifecycle events (start, stop)
- Thread creation for each client connection
- Every successful operation (RESERVE, CONFIRM, CANCEL, etc.)
- Every error/exception encountered
- Cleanup operations (startup stale reservation release, shutdown session release)
## Comments
- Module-level docstrings at the top of every module describing purpose and version (e.g., `"Protocol validation utilities for ConcertSync JSON protocol (v1.0)."`)
- Docstrings on all public functions/classes (with Args/Returns)
- Inline comments only when behavior is non-obvious (e.g., `# bool is subclass of int`)
- Section separator comments for logical groupings
- Protocol contract references — e.g., `# Note: QUERY no longer returns "total" field (protocol-contract-v1 compliance)`
- Not applicable (Python codebase). Uses standard Python docstrings with Args/Returns sections.
## Function Design
- Most functions are 10–50 lines
- Exception: `ConcertTextualApp._render_seat_map()` and worker methods in the TUI client are longer (~40–80 lines) due to UI logic
- Largest functions: `handle_reserve_batch()` (112 lines) and `handle_reserve_selected()` (99 lines) due to duplicate logic (notable technical debt)
- Single-purpose: functions accept only what they need
- Keyword-only parameters with `*` used for locked/unlocked mode switching — e.g., `def add_reservation(self, section, seats, seat_id=None, *, locked: bool = False):`
- Configuration accessed via module-level constants (`SECTION_CONFIG`, `RESERVATION_TTL`) rather than passed as parameters
- Validation functions: `Tuple[bool, Optional[str], Optional[...]]` pattern — `(is_valid, error_message, result)`
- Response builders: `Dict[str, Any]` with consistent `status` field
- Data accessors: Return objects or `None` for not-found
- Widespread use throughout — all public functions annotated
- `typing` imports: `Dict`, `List`, `Optional`, `Tuple`, `Any`, `Set`
- Return types always declared on public functions
- Some internal methods lack annotations (e.g., `_count_section_seats()` has docstring but no return type annotation)
## Module Design
- No explicit `__all__` lists used
- Everything public is importable; private by convention (`_` prefix) only
- `__init__.py` files are empty (used only to mark packages)
- `src/utils/__init__.py`, `src/server/__init__.py`, `src/client/__init__.py`, `src/shared_resources/__init__.py`, `src/synchronization/__init__.py` — all empty (11-12 lines with just encoding/metadata)
- No re-exports in `__init__.py` — consumers import directly from submodule paths
- `src/` — root package containing all application code
- `src/server/` — server-side request handling (listener, transactional threads, monitor, session management)
- `src/client/` — client-side HTTP client and error hierarchy
- `src/shared_resources/` — shared state (seat matrix, reservation table, semaphore manager, log)
- `src/synchronization/` — lock hierarchy and mutex manager
- `src/utils/` — configuration, enums, protocol validation, error response builders
- `frontend_tui/` — Textual-based terminal UI (separate top-level package)
## Threading Conventions
- All shared mutable state protected by `threading.Lock()` or `threading.RLock()`
- Lock acquisition follows a strict hierarchy: table lock → section locks (ordered by `Section.value`)
- `@contextmanager` decorator used extensively for lock scoping (`with self.mutex_manager.table_and_sections(...):`)
- Double-check pattern inside locks to prevent TOCTOU races — e.g., re-query session state after acquiring lock
- Daemon threads used for background workers and TUI refresh operations
- `threading.Barrier` used in concurrency tests to synchronize parallel operations
- `call_from_thread()` used in Textual TUI to safely update UI from worker threads
## Socket/Network Conventions
- Raw TCP sockets used throughout (no HTTP framework) — `socket.AF_INET`, `socket.SOCK_STREAM`
- JSON-encoded request/response messages exchanged over TCP
- Server listens on configurable port (`SERVER_PORT = 9999` default)
- Client connects per-request (short-lived connections) — `with socket.socket(...) as s:` pattern in `ConcertClient.send_request()`
- Server accepts connections in a loop, spawning a `TransactionalThread` per client
- Receive buffer: 4096 bytes, looped until no more data
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
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
- **Thread-per-connection model:** Each TCP client gets a dedicated `TransactionalThread` spawned by `ListenerThread`
- **Lock hierarchy deadlock prevention:** All section locks acquired in `Section` enum value order (VIP=0 → PREFERENTIAL=1 → GENERAL=2) via `lock_hierarcky.py`; locks released in reverse order
- **Atomic transactions:** RESERVE, RESERVE_BATCH, CONFIRM, and CANCEL acquire all needed locks before mutating state; full rollback on any failure
- **Tri-state response protocol:** Every response has `status` ∈ {`SUCCESS`, `FAILURE`, `ERROR`} with deterministic error codes matching `protocol-contract-v1.md`
- **In-memory only:** No database; all seat state, sessions, and semaphores live in Python data structures
- **TTL-based reservation expiry:** Active reservations expire after 300s; `MonitorThread` sweeps every 1s and releases seats
- **Dual-layer validation:** Client (`ConcertClient`) validates inputs locally before sending; Server (`TransactionalThread`) validates on receipt
## Layers
- Purpose: Terminal user interface for interactive seat reservation
- Location: `frontend_tui/`
- Contains: Textual `App` subclass, `Screen` subclass, CSS theme
- Depends on: `src/client/concert_client.py`, `src/utils/config.py`, `src/utils/enums.py`
- Used by: End users (run via `python -m frontend_tui` or `desktop_launcher.py`)
- Purpose: High-level Python API for the JSON-over-TCP protocol; wraps socket communication, validates responses, maps error codes to typed exceptions
- Location: `src/client/`
- Contains: `ConcertClient` class, exception hierarchy (`ConcertClientError` → `SeatNotAvailableError`, `NoCapacityError`, `TransactionNotFoundError`, etc.)
- Depends on: `src/utils/protocol_validator.py`
- Used by: `frontend_tui/app.py`, external scripts/tests
- Purpose: Accept TCP connections, parse JSON requests, orchestrate state mutations through shared resources
- Location: `src/server/`
- Contains: `ConcertServer` (lifecycle), `ListenerThread` (accept loop), `TransactionalThread` (request dispatch), `MonitorThread` (expiry sweep), `SessionManager` (user sessions)
- Depends on: `src/shared_resources/`, `src/synchronization/`, `src/utils/`
- Used by: `main.py`, `desktop_launcher.py`
- Purpose: In-memory state holders with thread-safe access; the "database" of the system
- Location: `src/shared_resources/`
- Contains: `SeatMatrix` (seat grid + locks), `ReservationTable` (legacy tx table), `SemaphoreManager` (capacity bounds), `GlobalLog` (file logger)
- Depends on: `src/utils/config.py`, `src/utils/enums.py`
- Used by: Server layer (exclusively)
- Purpose: Centralized lock orchestration enforcing deadlock-free section lock ordering
- Location: `src/synchronization/`
- Contains: `MutexManager` (context managers), `lock_hierarcky.py` (lock sort + acquire/release)
- Depends on: Nothing external
- Used by: Server layer's `TransactionalThread` and `MonitorThread`
- Purpose: Configuration constants, enums, protocol validation, error response factories
- Location: `src/utils/`
- Contains: `config.py` (dimensions, TTL, port), `enums.py` (Section, SeatState, ReservationStatus), `protocol_validator.py` (request/response validation), `error_responses.py` (response builders)
- Depends on: Only Python stdlib
- Used by: All other layers
## Data Flow
### Primary Request Path (RESERVE single seat)
### Transaction Confirmation Path
### TTL Expiration Path (background)
### Query Path (refresh)
- All state is in-memory (no database). Server restart loses all reservations.
- `SeatMatrix.seats`: 3-level dict → `{Section: [[SeatState, ...], ...]}` — co-located with per-section `threading.Lock` instances in `mutex_sections`
- `SessionManager._sessions`: `Dict[str, UserSession]` protected by `threading.Lock` — maps `user_id` → session
- `SemaphoreManager.s_sections`: `Dict[Section, threading.Semaphore]` — no explicit lock needed (Semaphore is atomic)
- `ReservationTable.reservations`: Legacy `Dict[str, Reservation]` with `mutex_table` lock — used only for startup stale cleanup
- `GlobalLog`: file-backed with `mutex_log` thread lock
## Key Abstractions
- Purpose: Grid representation of all seats across 3 sections (VIP: 5×10, PREFERENTIAL: 10×15, GENERAL: 20×20)
- Examples: `src/shared_resources/seat_matrix.py`
- Pattern: Each section has its own `threading.Lock` (`mutex_sections`) and `threading.RLock` (`rwlocks`); state values are `SeatState` enum members. The `mutex_sections` locks are the primary synchronization primitive used throughout the system.
- Purpose: Tracks per-user reservation sessions with TTL; creates UUID session IDs, provides lookup by user_id or session_id
- Examples: `src/server/session_manager.py`
- Pattern: `UserSession` is a `@dataclass` with `seats: List[Tuple[Section, int, int]]`, `state: ReservationStatus`, and `last_activity: float` for TTL calculation. Protected by `threading.Lock`.
- Purpose: Provides context managers (`table()`, `sections()`, `table_and_sections()`) that acquire locks in deadlock-free hierarchy order
- Examples: `src/synchronization/mutex_manager.py`, `src/synchronization/lock_hierarcky.py`
- Pattern: Section locks sorted by `Section.value` (VIP=0 < PREFERENTIAL=1 < GENERAL=2); acquired in ascending order, released in reverse. Table lock always acquired before section locks.
- Purpose: Centralized JSON request/response validation with deterministic error codes
- Examples: `src/utils/protocol_validator.py`
- Pattern: `validate_request()` is the single entry point — it chains `validate_request_json()` → `validate_action()` → action-specific validators (`validate_reserve_payload()`, `validate_confirm_payload()`, etc.). Returns `(bool, str, dict)` tuples.
- Purpose: Ensure all server responses conform to protocol-contract-v1.md schema
- Examples: `src/utils/error_responses.py`
- Pattern: Three builder functions (`build_success_response`, `build_failure_response`, `build_error_response`) plus convenience wrappers (`error_invalid_section`, `failure_seat_not_available`, etc.) that internally import `ErrorCode` constants.
## Entry Points
- Location: `main.py`
- Triggers: `python main.py`
- Responsibilities: Instantiates `ConcertServer(port=9999)`, calls `start()`, blocks on `while True: time.sleep(1)` until Ctrl+C, then calls `stop()`
- Location: `frontend_tui/__main__.py`
- Triggers: `python -m frontend_tui`
- Responsibilities: Instantiates `ConcertTextualApp`, calls `app.run()`. User must connect to a running server via the Connect button.
- Location: `desktop_launcher.py`
- Triggers: `python desktop_launcher.py`
- Responsibilities: Starts `ConcertServer` in background, then runs `ConcertTextualApp`; shuts down server when TUI exits. Used for single-machine demos.
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
### Per-request socket connection in ConcertClient
### Duplicate seat-counting logic
## Error Handling
- **SUCCESS:** Operation completed; includes action-specific payload (e.g., `transaction_id`, `ttl`, `sections`, `seat_map`)
- **FAILURE:** Business logic rejection (seat not available, no capacity, transaction not found/active) — client can retry with different parameters
- **ERROR:** Technical problem (invalid JSON, unknown action, internal exception) — client must fix payload or retry later
- Each `handle_*()` method returns a response dict directly; the `run()` method sends it
- Validation failures return `build_error_response(ErrorCode.INVALID_PAYLOAD, msg)` early
- State mutations inside `with mutex_manager.table_and_sections():` blocks — exceptions cause rollback
- Unexpected exceptions caught at method level, logged via `global_log.append("ERROR", ...)`, return `error_internal(str(e))`
- `ConcertClient.send_request()` calls `_process_response()` which maps `error_code` to typed exceptions (`SeatNotAvailableError`, `NoCapacityError`, etc.)
- Local validation via `validate_*_payload()` raises `InvalidInputError` before sending
- Socket errors raise `ConcertClientError`
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
