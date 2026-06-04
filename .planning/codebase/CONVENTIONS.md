# Coding Conventions

**Analysis Date:** 2026-06-01

## Naming Patterns

**Files:**
- `snake_case.py` — All Python source files (`concert_server.py`, `transactional_thread.py`, `reservation_table.py`)
- Test files prefixed with `test_` (`test_protocol_contract.py`, `test_reserve_batch.py`)
- Exception files use full words in snake_case (`error_responses.py`)

**Classes:**
- PascalCase — `ConcertServer`, `ConcertClient`, `SeatMatrix`, `ReservationTable`, `SemaphoreManager`, `MutexManager`, `GlobalLog`, `TransactionalThread`, `ListenerThread`, `MonitorThread`, `LogTailer`, `TrackedSession`
- Exception classes: `ConcertClientError`, `InvalidInputError`, `ServerError`, `ServerFailureError`, `SeatNotAvailableError`, `NoCapacityError`, `TransactionNotFoundError`, `TransactionNotActiveError`

**Functions/Methods:**
- `snake_case` — `reserve_seat()`, `send_request()`, `handle_reserve()`, `_process_response()`, `check_availability()`, `build_success_response()`, `validate_reserve_payload()`, `_initialize_seats()`
- Private methods prefixed with single underscore: `_process_response()`, `_initialize_seats()`, `_refresh_every_second()`, `_render_section_table()`
- Test helper functions prefixed with underscore: `_run_parallel()`, `_wait_for_server()`, `_check_invariants()`
- Static methods decorated with `@staticmethod` and use `snake_case`: `_build_empty_seat_map()`, `_seat_token()`, `_render_sparkline()`

**Variables:**
- `snake_case` everywhere — `tx_id`, `section_str`, `max_rows`, `semaphore_acquired`, `seat_objects`, `reserved_seats`, `released_counts`
- Boolean flags: `is_valid`, `blocking`, `silent`, `locked`, `semaphore_acquired`
- Loop indices: `idx`, `i`

**Constants:**
- `UPPER_SNAKE_CASE` — `RESERVATION_TTL = 300`, `SERVER_PORT = 9999`, `SECTION_CONFIG`, `ITERATIONS = 50`, `THREADS_PER_SECTION = 10`
- Error code strings defined as class attributes: `ErrorCode.INVALID_PAYLOAD = "ERR_INVALID_PAYLOAD"`

**Enums:**
- PascalCase for enum class, UPPER_SNAKE_CASE for members: `SeatState.AVAILABLE`, `Section.VIP`, `ReservationStatus.ACTIVE`, `ErrorCode.INVALID_PAYLOAD`

**Test classes/methods:**
- Test class: PascalCase prefixed with `Test` — `TestRequestJsonParsing`, `TestReserveBatchAtomicity`, `TestErrorResponseStructure`
- Test method: `snake_case` prefixed with `test_` — `test_valid_json_object()`, `test_one_seat_unavailable_reserves_none()`

## Code Style

**Formatting:**
- Tool: Black >=26.3.1 (declared in `pyproject.toml` as `[dependency-groups] dev = ["black>=26.3.1"]`)
- No `.prettierrc` or `pyproject.toml [tool.black]` config present — Black defaults apply (88 char line length)
- Standard 4-space indentation — **with exceptions noted below**
- No `.editorconfig` file detected

**Indentation Inconsistency:**
- Most files use PEP 8 4-space indentation
- `src/synchronization/lock_hierarcky.py` and `src/synchronization/mutex_manager.py` use **tab indentation** (inconsistent with the rest of the codebase)
- Before editing these files, run `black` on them to normalize

**Linting:**
- Tool: Flake8 >=7.3.0 (declared in `pyproject.toml`)
- No `.flake8` config file present — Flake8 defaults apply

**String Quotes:**
- Production code (`src/`): Mixed usage — double quotes preferred in some files (`concert_client.py`, `protocol_validator.py`, `error_responses.py`), single quotes in `concert_server.py`, `seat_matrix.py`
- Test files (`tests/`): Primarily single quotes for test strings (`test_reserve_batch.py`, `test_query_atomicity.py`)
- New code should follow Black's auto-formatting (Black normalizes to double quotes by default when re-formatting)

## Import Organization

**Order (observed consistently across all files):**
1. Python standard library imports (`import socket`, `import json`, `import threading`, `import time`, `import uuid`, `from dataclasses import dataclass`, `from typing import ...`, `from collections import defaultdict`)
2. Third-party library imports (`import pytest`, `from textual.app import App`)
3. Internal package imports (`from src.server.listener_thread import ListenerThread`, `from src.utils.enums import Section`)
4. Groups separated by blank lines
5. Within groups: roughly alphabetical by module name

**Path Aliases:**
- Uses full `src.` prefixed absolute imports throughout (`from src.utils.config import SERVER_PORT`, `from src.shared_resources.seat_matrix import SeatMatrix`)
- No relative imports (no `from ..utils.enums import Section`)
- All `__init__.py` files are empty (or nearly empty) — they don't re-export

**Import Style:**
- Multi-line import from the same module: uses parentheses with explicit names
```python
from src.utils.error_responses import (
    build_success_response,
    build_failure_response,
    build_error_response,
)
```
- Single-line for one or two imports: `from src.utils.enums import Section, SeatState`

## Error Handling

**Patterns:**
- **Client side** (`concert_client.py`): Custom exception hierarchy rooted at `ConcertClientError`. Methods validate input locally, then call `send_request()`. Server FAILURE/ERROR responses are translated to exceptions via `_process_response()`:
```python
ERROR_CODE_TO_EXCEPTION = {
    ErrorCode.SEAT_NOT_AVAILABLE: SeatNotAvailableError,
    ErrorCode.NO_CAPACITY: NoCapacityError,
    ErrorCode.TRANSACTION_NOT_FOUND: TransactionNotFoundError,
    ErrorCode.TRANSACTION_NOT_ACTIVE: TransactionNotActiveError,
}
```

- **Server side** (`transactional_thread.py`): All handler methods return response dicts (never raise). Top-level `run()` wraps everything in try/except and catches `Exception`. Error responses are built using factory functions from `error_responses.py`.

- **Validation functions** (`protocol_validator.py`): Return `Tuple[bool, Optional[str]]` — first element is valid flag, second is error message. This is consistent across all validation functions.

- **Server exception handling** pattern:
```python
try:
    # ... operation ...
    return build_success_response(...)
except Exception as e:
    self.server.global_log.append("ERROR", f"OP failed: {str(e)}")
    return error_internal(str(e))
```

- **Rollback pattern** in `transactional_thread.py`:
  - On failure during reserve: rollback seat state inside a `with self.server.mutex_manager.sections([section])` block
  - On semaphore exhaustion: revert any made changes before returning failure
  - On `reserve_batch` failure: rollback ALL seats and ALL acquired semaphores

## Logging

**Framework:** Custom `GlobalLog` class (`src/shared_resources/global_log.py`) — NOT Python's `logging` module.

**Patterns:**
```python
self.server.global_log.append("EVENT_TYPE", f"message with {details}")
```

**Standard event types used:**
- `"SERVER"` — Server lifecycle events
- `"RESERVE"` / `"RESERVE_BATCH"` — Reservation operations
- `"CONFIRM"` / `"CANCEL"` — Transaction state changes
- `"EXPIRE"` — TTL expiration events
- `"THREAD"` — Thread lifecycle
- `"ERROR"` — Failure/exception logging

**Log file:** Writes to `logs/system.log` by default, uses `Path` for filesystem operations.

## Comments

**When to Comment:**
- Public functions/methods: Always have a docstring (Google-style)
- Section headers: Visual separators `# ===================================================` used to divide logical sections (especially in `protocol_validator.py`, `error_responses.py`, `concert_client.py`, and all test files)
- Inline comments: Used to explain "why" not "what" — e.g., `# bool is subclass of int`, `# Socket already closed or unreachable`

**Docstrings:**
Google-style with `Args:`, `Returns:`, `Raises:` sections. Always triple double-quotes `"""..."""`.
```python
def send_request(self, request):
    """
    Send request and receive response from server.
    
    Args:
        request: Dict with action and parameters
        
    Returns:
        Parsed response dict
        
    Raises:
        ConcertClientError: If network or protocol error occurs
    """
```

**Module-level docstrings:**
Used in test files to describe the test battery:
```python
"""
Tests for ConcertSync JSON protocol contract (v1.0).

Validates:
- Request payload structure and validation
- Response schema compliance
- Round-trip client-server protocol adherence
"""
```

## Function Design

**Size:** Functions range from small (5-15 lines for getters/setters) to large (50-150 lines for request handlers). Handler methods in `transactional_thread.py` (`handle_reserve`, `handle_confirm`, `handle_reserve_batch`) are the largest in the codebase.

**Parameters:** Functions use explicit named parameters. Some long-running operations pass state as positional args. The `*, locked: bool = False` keyword-only pattern is used for the `locked` parameter in `ReservationTable` methods.

**Return Values:**
- Validation functions: `Tuple[bool, Optional[str]]` or `Tuple[bool, Optional[str], Optional[Dict]]`
- Response builders: `Dict[str, Any]`
- Business operations: Either a dict (server) or the object (shared resources)
- `None` on failure/success in many shared resource methods

**Context Managers:** Used extensively for lock management:
```python
@contextmanager
def table(self):
    table_lock = self.reservation_table.mutex_table
    table_lock.acquire()
    try:
        yield
    finally:
        table_lock.release()

@contextmanager
def sections(self, sections):
    with acquire_section_locks(self.seat_matrix.mutex_sections, sections) as ordered_sections:
        yield ordered_sections
```

## Module Design

**Package structure:** `src/` has subpackages: `server/`, `client/`, `shared_resources/`, `synchronization/`, `utils/`. Each has an `__init__.py` (mostly empty).

**Exports:** No `__all__` declarations. Classes and functions are imported directly by path.

**Barrel Files:** Not used. Each file explicitly imports what it needs:
```python
from src.utils.protocol_validator import (
    validate_reserve_payload,
    validate_confirm_payload,
    ...
)
```

**Internal imports:** Every module imports from `src.*` — no circular dependency issues observed.

## Synchronization Patterns

**Lock types used:**
- `threading.Lock()` — Section-level mutexes, table mutex
- `threading.RLock()` — Per-section reentrant lock for read operations (`check_availability`)
- `threading.Condition()` — On reservation table for monitor notification
- `threading.Semaphore()` — Section capacity management
- `threading.Barrier()` — Used in test concurrency helpers

**Lock hierarchy (deadlock prevention):**
1. Table lock (outermost) — `self.server.mutex_manager.table()`
2. Section locks (inner) — always acquired in enum value order via `acquire_section_locks()` / `sort_sections()`
3. Lock order: TABLE → VIP → PREFERENTIAL → GENERAL

**Wait-free pattern:** `blocking=False` on semaphore `acquire()` to avoid indefinite blocking

## Test Conventions

- **Test framework:** pytest (>=9.0.3)
- **Server fixtures:** Create server on random port to enable parallel test execution
- **Test classes:** Used to group related tests by feature/behavior
- **Test names:** Descriptive `test_<behavior>_<condition>` naming
- **Assertions:** Plain `assert` statements (no `self.assertEqual`)
- **Exception testing:** `pytest.raises()` context manager for expected exceptions
- **Concurrent tests:** `threading.Thread` + `threading.Barrier` patterns

## Style Quirks & Inconsistencies

1. **Tab indentation:** `src/synchronization/lock_hierarcky.py` and `src/synchronization/mutex_manager.py` use tabs; rest of codebase uses 4 spaces
2. **Dead code in `monitor_thread.py`** (line 49+): Code inside the `with` block after `return` is unreachable — the `reservation.state = ReservationStatus.EXPIRED` and seat-release logic is orphaned
3. **String quote style:** Inconsistent between single and double quotes across files
4. **Static methods:** Sometimes wrapped in `try/call_from_thread` with bare `except Exception` fallback in TUI code

---

*Convention analysis: 2026-06-01*
