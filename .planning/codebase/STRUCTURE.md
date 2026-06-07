# Codebase Structure

**Analysis Date:** 2026-06-04

## Directory Layout

```
concert-sync/
├── main.py                      # Server-only entry point
├── desktop_launcher.py          # Bundled server + TUI launcher
├── pyproject.toml               # Project metadata, pytest config, dependency groups
├── uv.lock                      # Locked dependencies (uv)
├── flake.nix                    # Nix development shell definition
├── flake.lock                   # Nix flake lock
├── .python-version              # Python version: 3.14
├── README.md                    # Project readme with usage instructions
│
├── src/                         # Core Python package
│   ├── __init__.py              # Package docstring
│   ├── server/                  # Server-side components
│   │   ├── __init__.py          # Exports ConcertServer
│   │   ├── concert_server.py    # Server lifecycle & orchestration
│   │   ├── listener_thread.py   # TCP accept loop → spawns threads
│   │   ├── transactional_thread.py  # Request dispatch & state mutation
│   │   ├── monitor_thread.py    # TTL expiration background sweep
│   │   └── session_manager.py   # UserSession tracking with TTL
│   ├── client/                  # Client library
│   │   ├── __init__.py          # Exports ConcertClient
│   │   └── concert_client.py    # High-level TCP client API
│   ├── shared_resources/        # In-memory state holders
│   │   ├── __init__.py          # Exports all shared resources
│   │   ├── seat_matrix.py       # 2D seat grid + per-section locks
│   │   ├── reservation_table.py # Legacy transaction table (stale)
│   │   ├── semaphore_manager.py # Per-section capacity semaphores
│   │   └── global_log.py        # File-backed thread-safe logger
│   ├── synchronization/         # Lock management
│   │   ├── __init__.py          # (empty)
│   │   ├── mutex_manager.py     # Context manager lock orchestration
│   │   └── lock_hierarcky.py    # Deadlock-free section lock ordering
│   └── utils/                   # Configuration, enums, protocol
│       ├── __init__.py          # Exports config constants and enums
│       ├── config.py            # Section dimensions, TTL, port
│       ├── enums.py             # Section, SeatState, ReservationStatus
│       ├── protocol_validator.py # JSON request/response validation
│       └── error_responses.py   # SUCCESS/FAILURE/ERROR response builders
│
├── frontend_tui/                # Textual terminal UI
│   ├── __init__.py              # Package docstring
│   ├── __main__.py              # TUI entry point (python -m frontend_tui)
│   ├── app.py                   # ConcertTextualApp (main TUI widget)
│   ├── login_screen.py          # LoginScreen (name capture modal)
│   └── styles.tcss              # Textual CSS theme
│
├── tests/                       # Test suite (14 files)
│   ├── test_protocol_contract.py    # Protocol validation unit tests
│   ├── test_deterministic_errors.py # Error code determinism tests
│   ├── test_lock_hierarchy_core.py  # Lock ordering/deadlock tests
│   ├── test_query_atomicity.py      # Query consistency under load
│   ├── test_query_seat_map.py       # Seat map response tests
│   ├── test_reserve_batch.py        # Batch reservation tests
│   ├── test_transaction_idempotency.py # CONFIRM/CANCEL idempotency
│   ├── test_transaction_races.py    # Race condition tests
│   ├── test_tui_seat_map.py         # TUI seat map rendering tests
│   ├── test_phase1_e2e.py           # Phase 1 end-to-end
│   ├── test_phase2_e2e.py           # Phase 2 end-to-end
│   ├── test_phase3_e2e.py           # Phase 3 end-to-end
│   ├── test_phase6_e2e.py           # Phase 6 end-to-end
│   └── concurrent_tests.py          # Concurrent client tests
│
├── scripts/                     # Build & run scripts
│   ├── run.sh                   # Main orchestrator (server/tui/both/test)
│   ├── run_avance2_evidence.sh  # Evidence generation script
│   └── build_windows_exe.ps1    # PyInstaller Windows .exe builder
│
├── docs/                        # Documentation
│   ├── protocol-contract-v1.md      # Formal JSON protocol specification
│   ├── adr-0001-segment-a-locking-idempotency.md  # Architecture decision record
│   ├── plan-maestro-implementacion-v2.md  # Master implementation plan (Spanish)
│   ├── manual-tecnico.md              # Technical manual (Spanish)
│   ├── project-roadmap.md             # Project roadmap
│   ├── proyecto-programado.md         # Course project doc (Spanish)
│   ├── avance-1.md                    # Milestone 1 (Spanish)
│   ├── avance-2-checklist.md          # Milestone 2 checklist (Spanish)
│   ├── avance-2-requerimientos.md     # Milestone 2 requirements (Spanish)
│   └── evidencia-fase2.md             # Phase 2 evidence (Spanish)
│
├── .planning/                   # GSD planning artifacts
│   └── codebase/                # Codebase map documents (this directory)
│
├── .github/                     # GitHub config
│   └── agents/agent.md          # Custom agent definition
│
├── .opencode/                   # Codegen tool config
├── .gitignore                   # Git ignore rules
└── .git/                        # Git repository
```

## Directory Purposes

**`src/`:**
- Purpose: Core Python package containing all business logic
- Contains: Server, client, shared resources, synchronization primitives, utilities
- Key files: `src/server/concert_server.py`, `src/server/transactional_thread.py`, `src/client/concert_client.py`

**`src/server/`:**
- Purpose: Server-side TCP listener, request dispatch, session management, TTL monitoring
- Contains: 5 Python modules + `__init__.py`
- Key files: `concert_server.py` (lifecycle), `transactional_thread.py` (all business logic for 6 actions)

**`src/client/`:**
- Purpose: Client-side TCP library with protocol validation and typed exceptions
- Contains: `ConcertClient` class + exception hierarchy
- Key files: `concert_client.py`

**`src/shared_resources/`:**
- Purpose: In-memory state objects — the "database" layer
- Contains: Seat grid, legacy reservation table, semaphore manager, file logger
- Key files: `seat_matrix.py` (seat states + per-section locks), `semaphore_manager.py`

**`src/synchronization/`:**
- Purpose: Deadlock-free lock acquisition patterns
- Contains: `MutexManager` context managers, lock hierarchy sorting
- Key files: `mutex_manager.py`, `lock_hierarcky.py`

**`src/utils/`:**
- Purpose: Constants, enums, and protocol infrastructure — no business logic
- Contains: Configuration, 3 enums, JSON validators, response builders
- Key files: `protocol_validator.py`, `error_responses.py`, `config.py`

**`frontend_tui/`:**
- Purpose: Textual-based terminal UI for interactive seat reservation
- Contains: 3 Python modules + CSS theme
- Key files: `app.py` (1126-line main application), `__main__.py` (entry point)

**`tests/`:**
- Purpose: Test suite covering protocol validation, concurrency, locking, idempotency, E2E scenarios
- Contains: 14 test files (pytest)
- Key files: `test_protocol_contract.py`, `test_transaction_races.py`, `test_phase6_e2e.py`

**`scripts/`:**
- Purpose: Shell/PowerShell scripts for running, building, and evidence generation
- Contains: 3 scripts
- Key files: `run.sh` (primary orchestrator)

**`docs/`:**
- Purpose: Project documentation, protocol specification, ADRs, milestone reports
- Contains: 10 markdown documents (mix of English and Spanish)
- Key files: `protocol-contract-v1.md`, `adr-0001-segment-a-locking-idempotency.md`

**`.planning/`:**
- Purpose: GSD-generated planning artifacts (codebase maps, phase plans)
- Contains: `codebase/` subdirectory with architecture documents
- Generated: Yes (by `/gsd-map-codebase` and `/gsd-plan-phase`)
- Committed: Yes

## Key File Locations

**Entry Points:**
- `main.py`: Server-only launcher (starts ConcertServer, blocks until Ctrl+C)
- `desktop_launcher.py`: Bundled server + TUI launcher (starts server, runs TUI, shuts down server on exit)
- `frontend_tui/__main__.py`: TUI-only entry point (`python -m frontend_tui`)
- `scripts/run.sh`: Script orchestrator supporting `server`, `tui`, `both`, `test` modes

**Configuration:**
- `src/utils/config.py`: `SECTION_CONFIG` (seat dimensions), `RESERVATION_TTL` (300s), `SERVER_PORT` (9999)
- `src/utils/enums.py`: `Section` (VIP=0, PREFERENTIAL=1, GENERAL=2), `SeatState`, `ReservationStatus`
- `pyproject.toml`: Project metadata, pytest config, dependency groups (`dev`, `tui`)
- `flake.nix`: Nix development shell with Python 3.14 and packages
- `frontend_tui/styles.tcss`: Textual CSS theme (dark navy/teal color scheme)

**Core Logic:**
- `src/server/transactional_thread.py`: All 6 request handlers (RESERVE, RESERVE_BATCH, RESERVE_SELECTED, CONFIRM, CANCEL, QUERY, QUERY_SEAT_MAP) — 625 lines
- `src/server/concert_server.py`: Server lifecycle, startup cleanup, shutdown release — 161 lines
- `src/client/concert_client.py`: Client API + exception mapping — 293 lines
- `src/utils/protocol_validator.py`: JSON parsing + field validation for all actions — 420 lines
- `src/utils/error_responses.py`: Response builder factory functions — 195 lines

**Frontend:**
- `frontend_tui/app.py`: Main Textual App with connection, reservation, session tracking, seat map, metrics — 1126 lines

**Testing:**
- `tests/test_protocol_contract.py`: Unit tests for JSON validation (423 lines)
- `tests/test_transaction_races.py`: Race condition testing
- `tests/test_phase6_e2e.py`: End-to-end integration tests
- `tests/concurrent_tests.py`: Multi-client concurrent scenario tests

## Naming Conventions

**Files:**
- `snake_case.py` for all Python modules (e.g., `concert_server.py`, `session_manager.py`, `lock_hierarcky.py`)
- Note: `lock_hierarcky.py` has a typo in the filename ("hierarcky" vs "hierarchy") — intentional or historical
- `__init__.py` files use re-exports via `from src.X import Y` and `__all__` lists
- Test files: `test_*.py` pattern (pytest discovery)

**Directories:**
- `snake_case` for all package directories (e.g., `shared_resources/`, `frontend_tui/`)
- One level of nesting under `src/` (e.g., `src/server/`, `src/utils/`)

**Classes:**
- `PascalCase`: `ConcertServer`, `ListenerThread`, `TransactionalThread`, `MonitorThread`, `SessionManager`, `SeatMatrix`, `ReservationTable`, `SemaphoreManager`, `GlobalLog`, `MutexManager`, `ConcertClient`, `ConcertTextualApp`, `LoginScreen`
- Exception classes: Suffixed with `Error` (`ConcertClientError`, `SeatNotAvailableError`, `NoCapacityError`, etc.)
- Dataclasses: `UserSession`, `Reservation`, `TrackedSession` (PascalCase)

**Functions/Methods:**
- `snake_case` for all methods: `handle_reserve()`, `handle_confirm()`, `send_request()`, `_cleanup_stale_reservations()`
- Private methods prefixed with `_` (e.g., `_initialize_seats()`, `_refresh_query_worker()`, `_track_session()`)
- "Magic" methods use standard dunder names (`__init__`, `__main__`)

**Variables:**
- `snake_case` for local variables and instance attributes (e.g., `seat_matrix`, `session_manager`, `mutex_sections`)
- Constants: `UPPER_SNAKE_CASE` (`RESERVATION_TTL`, `SERVER_PORT`, `SECTION_CONFIG`)
- Enum members: `UPPER_SNAKE_CASE` values (`SeatState.AVAILABLE`, `Section.VIP`)

**Enums:**
- Enum class names: `PascalCase` (`Section`, `SeatState`, `ReservationStatus`)
- Enum member values: Strings matching member name for display/debugging (e.g., `AVAILABLE = "AVAILABLE"`)
- `Section` uses integer values for hierarchy ordering (`VIP = 0`, `PREFERENTIAL = 1`, `GENERAL = 2`)

**Imports:**
- Absolute imports from `src.*` package root (e.g., `from src.server.concert_server import ConcertServer`)
- Standard library imports first, then third-party, then local `src.*` imports
- `from __future__ import annotations` used in TUI files that use forward references

## Where to Add New Code

**New Server Action (e.g., REPORT):**
- Primary code: Add `handle_report()` method to `src/server/transactional_thread.py`, add routing in `run()` method
- Protocol validation: Add `validate_report_payload()` to `src/utils/protocol_validator.py`, register in `validate_request()`
- Error codes: Add constants to `ErrorCode` class in `src/utils/protocol_validator.py`
- Response builders: Add convenience function(s) to `src/utils/error_responses.py`
- Client method: Add `report()` method to `src/client/concert_client.py`
- Tests: Create `tests/test_report.py`

**New Shared Resource (e.g., Waitlist):**
- Implementation: Create `src/shared_resources/waitlist.py`
- Export: Add to `src/shared_resources/__init__.py`
- Lock orchestration: Add new context manager to `src/synchronization/mutex_manager.py` if new lock patterns needed
- Use in server: Import in `src/server/concert_server.py` `__init__`, access via `self.waitlist` in `TransactionalThread`

**New Utility Module (e.g., metrics):**
- Implementation: Create `src/utils/metrics.py`
- Export: Add to `src/utils/__init__.py` if publicly exported

**New TUI Screen (e.g., AdminPanel):**
- Implementation: Create `frontend_tui/admin_panel.py` with a `Screen` subclass
- Wire up: Push screen from `ConcertTextualApp` via `push_screen(AdminPanel())`

**New Test File:**
- Location: `tests/test_<feature>.py` (must match `test_*.py` pattern for pytest discovery)
- Run: `bash scripts/run.sh test` or `uv run pytest tests/test_<feature>.py`

## Special Directories

**`logs/`:**
- Purpose: Runtime log output (created by `GlobalLog` at `logs/system.log`)
- Generated: Yes (at runtime)
- Committed: No (`.gitignore` should exclude)

**`.venv/`:**
- Purpose: Python virtual environment (created by `run.sh` or manually)
- Generated: Yes
- Committed: No

**`dist/`:**
- Purpose: PyInstaller build output (created by `build_windows_exe.ps1`)
- Generated: Yes
- Committed: No

**`.opencode/`:**
- Purpose: Codegen tool configuration
- Generated: Yes (by opencode)
- Committed: Yes

**`.gsd-installed`:**
- Purpose: GSD installation marker file (empty)
- Generated: Yes
- Committed: Yes

---

*Structure analysis: 2026-06-04*
