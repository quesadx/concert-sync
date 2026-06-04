# Codebase Structure

**Analysis Date:** 2026-06-01

## Directory Layout

```
concert-sync/
├── .github/
│   └── agents/
│       └── agent.md                 # GSD agent configuration
├── .planning/                       # GSD planning artifacts
│   └── codebase/                    # Codebase map documents
├── docs/                            # Project documentation
│   ├── adr-0001-segment-a-locking-idempotency.md
│   ├── protocol-contract-v1.md      # Formal protocol specification
│   ├── plan-maestro-implementacion-v2.md
│   └── ...
├── frontend_tui/                    # Textual TUI frontend
│   ├── __init__.py
│   ├── __main__.py                  # TUI entry point
│   ├── app.py                       # ConcertTextualApp (main TUI)
│   └── styles.tcss                  # Textual CSS stylesheet
├── logs/
│   └── system.log                   # Runtime log output
├── scripts/
│   ├── run.sh                       # Unified launcher (server/tui/both/test)
│   ├── run_avance2_evidence.sh
│   └── build_windows_exe.ps1
├── src/                             # Main source code
│   ├── __init__.py
│   ├── client/                      # TCP client
│   │   ├── __init__.py
│   │   └── concert_client.py        # ConcertClient + exceptions
│   ├── server/                      # TCP server + threads
│   │   ├── __init__.py
│   │   ├── concert_server.py        # ConcertServer orchestrator
│   │   ├── listener_thread.py       # Accepts TCP connections
│   │   ├── monitor_thread.py        # TTL expiry daemon
│   │   └── transactional_thread.py  # Per-connection request handler
│   ├── shared_resources/            # Thread-safe data structures
│   │   ├── __init__.py
│   │   ├── global_log.py            # Thread-safe file logger
│   │   ├── reservation_table.py     # In-memory transaction store
│   │   ├── seat_matrix.py           # 2D seat state grids
│   │   └── semaphore_manager.py     # Per-section capacity semaphores
│   ├── synchronization/             # Lock orchestration
│   │   ├── __init__.py
│   │   ├── lock_hierarcky.py        # Lock hierarchy acquisition
│   │   └── mutex_manager.py         # Context-manager wrappers
│   └── utils/                       # Pure utilities
│       ├── __init__.py
│       ├── config.py                # SECTION_CONFIG, RESERVATION_TTL, SERVER_PORT
│       ├── enums.py                 # Section, SeatState, ReservationStatus
│       ├── error_responses.py       # Response factory functions
│       └── protocol_validator.py    # Request/response validation
├── tests/                           # Test suite
│   ├── concurrent_tests.py          # Multi-threaded stress tests
│   ├── test_deterministic_errors.py
│   ├── test_lock_hierarchy_core.py
│   ├── test_protocol_contract.py    # Protocol validation tests
│   ├── test_query_atomicity.py
│   ├── test_query_seat_map.py
│   ├── test_reserve_batch.py
│   ├── test_transaction_idempotency.py
│   └── test_transaction_races.py
├── desktop_launcher.py              # Server + TUI combined launcher
├── main.py                          # Headless server entry point
├── pyproject.toml                   # Python project config
├── flake.nix                        # Nix development shell
├── flake.lock
├── uv.lock                          # Dependency lock file
├── .python-version                  # Python version pin
└── .gitignore
```

## Directory Purposes

**`src/client/`:**
- Purpose: TCP client implementation with typed exception handling
- Contains: Client class, exception hierarchy, protocol validation calls
- Key files: `concert_client.py` — all client-side logic (270 lines)

**`src/server/`:**
- Purpose: Multi-threaded TCP server with connection handling
- Contains: Server orchestrator, listener, transaction handler, monitor daemon
- Key files:
  - `concert_server.py` — owns shared resources, starts threads (61 lines)
  - `listener_thread.py` — accept loop (31 lines)
  - `transactional_thread.py` — request dispatch and handlers (500 lines)
  - `monitor_thread.py` — TTL expiry (69 lines)

**`src/shared_resources/`:**
- Purpose: Thread-safe in-memory state shared across server threads
- Contains: Seat grid, reservation table, semaphores, logger
- Key files:
  - `seat_matrix.py` — per-section 2D arrays + locks (64 lines)
  - `reservation_table.py` — `dict` of `Reservation` dataclasses (75 lines)
  - `semaphore_manager.py` — per-section `Semaphore` objects (24 lines)
  - `global_log.py` — thread-safe file appender (16 lines)

**`src/synchronization/`:**
- Purpose: Deadlock-free lock acquisition helpers
- Contains: `MutexManager` context managers, `acquire_section_locks` generator
- Key files:
  - `mutex_manager.py` — `table()`, `sections()`, `table_and_sections()` (31 lines)
  - `lock_hierarcky.py` — sort sections by enum value, acquire in order (23 lines)

**`src/utils/`:**
- Purpose: Pure utility code with no internal dependencies
- Contains: Enums, config, validation, response factories
- Key files:
  - `config.py` — `SECTION_CONFIG`, `RESERVATION_TTL=300`, `SERVER_PORT=9999` (12 lines)
  - `enums.py` — `Section(VIP=0, PREFERENTIAL=1, GENERAL=2)`, `SeatState`, `ReservationStatus` (21 lines)
  - `protocol_validator.py` — master `validate_request()` pipeline and `validate_response()` (412 lines)
  - `error_responses.py` — `build_success/failure/error_response()` factories (195 lines)

**`frontend_tui/`:**
- Purpose: Textual-based terminal UI
- Contains: Main app, stylesheet, module entry point
- Key files: `app.py` — 940-line `ConcertTextualApp` with dashboard UI

**`tests/`:**
- Purpose: Test suite (pytest)
- Organization: Flat directory, no subdirectories
- Naming: `test_*.py` for pytest files, `concurrent_tests.py` for manual stress runner

**`docs/`:**
- Purpose: Project documentation and ADRs
- Contains: Protocol contract spec, ADRs, roadmap, evidence

**`scripts/`:**
- Purpose: Shell scripts for running and building
- Key files: `run.sh` — multi-mode launcher (server/tui/both/test)

## Key File Locations

**Entry Points:**
- `main.py`: Headless server (starts `ConcertServer` on port 9999, blocks until Ctrl+C)
- `desktop_launcher.py`: Combined server + TUI launch
- `frontend_tui/__main__.py`: Standalone TUI launch

**Configuration:**
- `pyproject.toml`: Project metadata, dev dependencies (black, flake8, pytest), TUI dependency (textual)
- `src/utils/config.py`: Runtime constants — section dimensions, port, TTL
- `flake.nix`: Nix development environment (Python 3.14, uv, pytest, black, flake8, textual, GSD SDK)
- `.python-version`: Python version pin

**Core Logic:**
- `src/server/transactional_thread.py`: All 6 action handlers (RESERVE, RESERVE_BATCH, CONFIRM, CANCEL, QUERY, QUERY_SEAT_MAP)
- `src/client/concert_client.py`: Client-side send/receive and input validation
- `src/utils/protocol_validator.py`: Master validation pipeline

**Testing:**
- `tests/test_protocol_contract.py`: 423 lines — tests validation functions
- `tests/concurrent_tests.py`: 173 lines — multi-threaded stress test runner

## Naming Conventions

**Files:**
- `snake_case.py` for all Python files
- Test files: `test_<feature>.py` (pytest convention)
- Config files: `pyproject.toml`, `flake.nix`, `.python-version`

**Directories:**
- `snake_case` for all project directories (`src/shared_resources/`, `src/synchronization/`, `frontend_tui/`)
- No nested test directories (all tests flat in `tests/`)

**Classes:**
- `PascalCase` — `ConcertServer`, `ListenerThread`, `TransactionalThread`, `MonitorThread`, `ConcertClient`, `SeatMatrix`, `ReservationTable`, `SemaphoreManager`, `MutexManager`, `GlobalLog`, `ConcertTextualApp`, `TrackedSession`, `LogTailer`, `Reservation`
- Exception classes: `PascalCase` with `Error` suffix — `SeatNotAvailableError`, `NoCapacityError`, `TransactionNotFoundError`, `TransactionNotActiveError`, `ConcertClientError`, `ServerError`, `ServerFailureError`, `InvalidInputError`

**Functions/Methods:**
- `snake_case` — `handle_reserve()`, `handle_confirm()`, `send_request()`, `reserve_seat()`, `_group_reservation_seats_by_section()`
- Private methods: prefixed with `_` — `_process_response()`, `_initialize_seats()`, `_ordered_sections()`, `_refresh_every_second()`
- Action handlers in `TransactionalThread`: `handle_reserve`, `handle_reserve_batch`, `handle_confirm`, `handle_cancel`, `handle_query`, `handle_query_seat_map`
- Response builders in `error_responses.py`: `build_success_response`, `build_failure_response`, `build_error_response`, plus convenience helpers: `error_invalid_section`, `failure_seat_not_available`, `failure_no_capacity`, etc.

**Variables/Constants:**
- `UPPER_SNAKE_CASE` for configuration constants — `RESERVATION_TTL`, `SERVER_PORT`, `SECTION_CONFIG`, `ErrorCode.INVALID_PAYLOAD`
- `snake_case` for local variables and instance attributes — `section_str`, `tx_id`, `semaphore_acquired`

**Types/Enums:**
- `PascalCase` for enum classes — `Section`, `SeatState`, `ReservationStatus`, `ErrorCode`
- Enum members: `UPPER_SNAKE_CASE` — `Section.VIP`, `SeatState.AVAILABLE`, `ReservationStatus.ACTIVE`

## Where to Add New Code

**New Feature (e.g., new action type):**
- Add action enum to `src/utils/enums.py` if needed
- Add action constant to `valid_actions` set in `src/utils/protocol_validator.py:94`
- Add payload validation function in `protocol_validator.py` (pattern: `validate_<action>_payload`)
- Add response builder factory in `src/utils/error_responses.py` if needed
- Add handler method in `src/server/transactional_thread.py` (pattern: `handle_<action>`)
- Wire handler into the dispatch chain in `run()` method at line 50-63
- Add client method in `src/client/concert_client.py` (pattern: `def <action>()`)
- Tests: `tests/test_<feature>.py`

**New Section (seating area):**
- Add entry to `Section` enum in `src/utils/enums.py` (with value maintaining hierarchy order)
- Add dimensions to `SECTION_CONFIG` in `src/utils/config.py`
- No other changes needed — `SeatMatrix`, `SemaphoreManager`, and all handlers iterate over `Section` members automatically

**New Shared Resource:**
- Create file in `src/shared_resources/<name>.py`
- Add lock/mutex as instance attribute for thread safety (pattern: `threading.Lock()`)
- Expose instantiation in `ConcertServer.__init__()` at `src/server/concert_server.py`
- Add synchronization context manager in `src/synchronization/mutex_manager.py` if needed

**New Test:**
- Create `tests/test_<feature>.py` (pytest file)
- Or add to `tests/concurrent_tests.py` for multi-threaded stress testing
- Fixture pattern: `concert_server_instance` in `test_transaction_idempotency.py` — creates server on random port, yields `(server, port)`, stops on teardown

**New Utility:**
- Create file in `src/utils/<name>.py`
- Must have zero imports from `src/` internals (pure utility constraint)

## Special Directories

**`logs/`:**
- Purpose: Runtime log output from `GlobalLog`
- Generated: Yes (created on first server start)
- Committed: No (tracked in `.gitignore`? — No, but `logs/system.log` is currently checked in)

**`__pycache__/` directories:**
- Purpose: Python bytecode cache
- Generated: Yes
- Committed: No (in `.gitignore` via `__pycache__/`)

**`.pytest_cache/`:**
- Purpose: Pytest cache
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-06-01*
