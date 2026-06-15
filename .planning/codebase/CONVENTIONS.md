# Coding Conventions

**Analysis Date:** 2026-06-04

## Naming Patterns

**Files:**
- `snake_case.py` for all modules — e.g., `concert_server.py`, `protocol_validator.py`, `lock_hierarcky.py`
- `test_<feature>.py` for test files — e.g., `test_protocol_contract.py`, `test_reserve_batch.py`
- `__init__.py` used as barrel files to make directories importable packages

**Classes:**
- `PascalCase` — e.g., `ConcertServer`, `SeatMatrix`, `TransactionalThread`, `ListenerThread`, `UserSession`
- Exception classes suffixed with `Error` — e.g., `ConcertClientError`, `InvalidInputError`, `SeatNotAvailableError`

**Functions/Methods:**
- `snake_case` — e.g., `handle_reserve()`, `check_availability()`, `get_or_create()`, `_process_response()`
- Private methods prefixed with `_` — e.g., `_group_seats_by_section()`, `_initialize_seats()`
- Worker methods suffixed with `_worker` (frontend TUI) — e.g., `_reserve_single_seat_worker()`, `_refresh_query_worker()`
- Factory functions prefixed with `build_` or `error_`/`failure_` — e.g., `build_success_response()`, `error_invalid_section()`, `failure_seat_not_available()`

**Variables:**
- `snake_case` for local variables and attributes — e.g., `section_str`, `tx_id`, `ordered_sections`
- Private instance attributes prefixed with `_` — e.g., `self._sessions`, `self._lock`
- Mutex/lock attributes named explicitly — e.g., `self.mutex_table`, `self.rwlocks`, `self.mutex_sections`

**Constants:**
- `UPPER_CASE` module-level constants — e.g., `SECTION_CONFIG`, `RESERVATION_TTL`, `SERVER_PORT`
- `PascalCase` Enum classes with `UPPER_CASE` members — e.g., `SeatState.AVAILABLE`, `Section.VIP`
- Error code constants in a nested class — e.g., `ErrorCode.INVALID_PAYLOAD`

**Enums:**
- Located in `src/utils/enums.py`
- Values are string-based (not integer) for readability — e.g., `RESERVED = "RESERVED"`
- Cross-referenced by value (`.value`) in protocol messages and storage lookups

## Code Style

**Formatting:**
- Tool: black v26.3.1 (configured as dev dependency in `pyproject.toml`)
- Indentation: 4 spaces (consistent throughout)
- Line length: ~100 characters observed in practice (black default)
- No `.prettierrc` or `.flake8` config files detected — formatting and linting configured via `pyproject.toml` dependency groups only

**Linting:**
- Tool: flake8 v7.3.0 (configured as dev dependency)
- No explicit `.flake8` configuration file — defaults assumed
- F-string usage preferred for string interpolation (e.g., `f"Seat ({row}, {col}) out of bounds"`)

**Docstrings:**
- Triple-quoted docstrings on all public classes, methods, and functions
- Documented with section-style format: brief summary, blank line, detailed description, blank line, Args/Returns sections
- Type hints ARE present in docstring `Args` but are duplicated since actual Python type annotations are also used

Example:
```python
def validate_request_json(data: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validate that raw data is valid JSON.
    
    Args:
        data: UTF-8 encoded string (or already decoded)
        
    Returns:
        (is_valid, error_message, parsed_dict)
        - is_valid: True if JSON parses successfully
        - error_message: Human-readable error if invalid
        - parsed_dict: Parsed JSON dict if valid, else None
    """
```

**Section Separators:**
- Comments with `=` repeated for visual separation of logical sections:
```python
# ============================================================================
# ERROR CODE CONSTANTS
# ============================================================================
```

## Import Organization

**Order (observed pattern):**
1. Standard library imports (alphabetical) — `import json`, `import socket`, `import threading`, `import time`
2. `from __future__ import` (when present, at very top) — `from __future__ import annotations`
3. Third-party library imports — `import pytest`, `from textual.app import App`
4. Project/package imports (alphabetical) — `from src.utils.enums import Section, SeatState`

**Path Aliases:**
- No import path aliases configured (no `@src/` or similar shortcuts)
- All internal imports use full package paths: `from src.server.concert_server import ConcertServer`
- The `tests/` directory uses `src.` prefix for all internal imports
- Some test files manually inject project root into `sys.path`:
```python
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
```

**Import Style:**
- Always use explicit named imports — no wildcard `from module import *`
- Group related imports from same module on one line — `from typing import Dict, List, Optional, Tuple`
- Local/conditional imports used sparingly inside functions only when needed to break circularity or defer import cost

## Error Handling

**Strategy:** Three-tier protocol-based error model (SUCCESS / FAILURE / ERROR)

**Patterns:**
- **Centralized error factories** in `src/utils/error_responses.py` — functions like `build_success_response()`, `build_error_response()`, `build_failure_response()` return consistent `Dict[str, Any]` shapes
- **Convenience builders** for common errors — `error_invalid_section()`, `failure_seat_not_available()`, `error_internal()`, etc.
- **Protocol validation layer** in `src/utils/protocol_validator.py` — validates request JSON, actions, and payload-specific fields BEFORE business logic runs
- **Deterministic error codes** — `ErrorCode` class in `protocol_validator.py` with constants like `ERR_INVALID_PAYLOAD`, `ERR_SEAT_NOT_AVAILABLE`
- **Client-side exception hierarchy** in `src/client/concert_client.py` — `ConcertClientError` → `ServerError`, `ServerFailureError` → `SeatNotAvailableError`, etc.
- **Error code to exception mapping** — `ERROR_CODE_TO_EXCEPTION` dict maps `ErrorCode` constants to specific exception classes
- **Rollback on failure** in `TransactionalThread` — reserve handlers acquire locks, make state changes, and roll back all changes if any step fails (semaphore, seat state, etc.)
- **Try/except with finally** for socket cleanup — all request handlers close `client_socket` in `finally` block

**Do NOT:**
- Swallow exceptions silently — use `self.server.global_log.append("ERROR", ...)` to always log
- Pass empty `except:` — always catch specific exception types (`except socket.error as e:`, `except Exception as e:`)

## Logging

**Framework:** Custom `GlobalLog` class in `src/shared_resources/global_log.py`

**Patterns:**
- Thread-safe file-based logging using `threading.Lock()`
- Format: `[ISO_TIMESTAMP] [EVENT_TYPE] [TID:THREAD_ID] message`
- Event types used: `"SERVER"`, `"THREAD"`, `"ERROR"`, `"EXPIRE"`, `"CLEANUP"`, `"SHUTDOWN"`, `"RESERVE"`, `"CONFIRM"`, `"CANCEL"`, `"RESERVE_BATCH"`, `"QUERY_SEAT_MAP"`

**When to log:**
- Server lifecycle events (start, stop)
- Thread creation for each client connection
- Every successful operation (RESERVE, CONFIRM, CANCEL, etc.)
- Every error/exception encountered
- Cleanup operations (startup stale reservation release, shutdown session release)

**Note:** Standard `logging` module is not used. The custom `GlobalLog` is the only logging mechanism.

## Comments

**When to Comment:**
- Module-level docstrings at the top of every module describing purpose and version (e.g., `"Protocol validation utilities for ConcertSync JSON protocol (v1.0)."`)
- Docstrings on all public functions/classes (with Args/Returns)
- Inline comments only when behavior is non-obvious (e.g., `# bool is subclass of int`)
- Section separator comments for logical groupings
- Protocol contract references — e.g., `# Note: QUERY no longer returns "total" field (protocol-contract-v1 compliance)`

**JSDoc/TSDoc:**
- Not applicable (Python codebase). Uses standard Python docstrings with Args/Returns sections.

## Function Design

**Size:**
- Most functions are 10–50 lines
- Exception: `ConcertTextualApp._render_seat_map()` and worker methods in the TUI client are longer (~40–80 lines) due to UI logic
- Largest functions: `handle_reserve_batch()` (112 lines) and `handle_reserve_selected()` (99 lines) due to duplicate logic (notable technical debt)

**Parameters:**
- Single-purpose: functions accept only what they need
- Keyword-only parameters with `*` used for locked/unlocked mode switching — e.g., `def add_reservation(self, section, seats, seat_id=None, *, locked: bool = False):`
- Configuration accessed via module-level constants (`SECTION_CONFIG`, `RESERVATION_TTL`) rather than passed as parameters

**Return Values:**
- Validation functions: `Tuple[bool, Optional[str], Optional[...]]` pattern — `(is_valid, error_message, result)`
- Response builders: `Dict[str, Any]` with consistent `status` field
- Data accessors: Return objects or `None` for not-found

**Type Annotations:**
- Widespread use throughout — all public functions annotated
- `typing` imports: `Dict`, `List`, `Optional`, `Tuple`, `Any`, `Set`
- Return types always declared on public functions
- Some internal methods lack annotations (e.g., `_count_section_seats()` has docstring but no return type annotation)

## Module Design

**Exports:**
- No explicit `__all__` lists used
- Everything public is importable; private by convention (`_` prefix) only
- `__init__.py` files are empty (used only to mark packages)

**Barrel Files:**
- `src/utils/__init__.py`, `src/server/__init__.py`, `src/client/__init__.py`, `src/shared_resources/__init__.py`, `src/synchronization/__init__.py` — all empty (11-12 lines with just encoding/metadata)
- No re-exports in `__init__.py` — consumers import directly from submodule paths

**Package Structure:**
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

---

*Convention analysis: 2026-06-04*
