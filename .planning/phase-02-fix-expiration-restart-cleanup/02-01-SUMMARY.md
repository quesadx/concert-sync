---
phase: 02-fix-expiration-restart-cleanup
plan: 01
subsystem: server
tags: [expiration, startup-cleanup, monitor-thread, reservation-table, semaphore]
requires:
  - phase: 01-user-id-session-ttl
    provides: SessionManager, expire_session, session-based TTL
provides:
  - Fixed expire_reservation() with no dead code
  - Startup cleanup via _cleanup_stale_reservations()
  - 5 E2E tests for expiration + cleanup correctness
affects:
  - phase: 03-buy-near-expiry-cancellation
tech-stack:
  added: []
  patterns:
    - "Delegate legacy method to session-based path (backward compat)"
    - "Startup cleanup runs before listener thread (crash recovery)"
key-files:
  created:
    - tests/test_phase2_e2e.py
  modified:
    - src/server/monitor_thread.py
    - src/server/concert_server.py
key-decisions:
  - "Replaced broken expire_reservation() with lightweight wrapper that delegates to expire_session() — preserves public API while removing dead code"
  - "Cleanup runs after monitor_thread.start() but before listener_thread.start() — ensures no client connections during stale state release"
  - "Handles both 2-tuple (row, col) and 3-tuple (section, row, col) seat formats for backward compat with pre-session reservation entries"
patterns-established:
  - "Legacy method preservation: keep public signature but delegate internally"
  - "Crash recovery hook: cleanup before accepting connections"
requirements-completed: [EXP-01, EXP-02, CLN-01, CLN-02, CLN-03]
duration: 15min
completed: 2026-06-01
---

# Phase 2 Plan 01: Fix expire_reservation dead code + startup cleanup + E2E tests

**Removed unreachable code in `expire_reservation()`, added startup cleanup to `ConcertServer`, and 5 E2E tests verifying both expiration fix and stale reservation cleanup**

## Performance

- **Duration:** 15 min
- **Started:** 2026-06-01T22:45:00Z
- **Completed:** 2026-06-01T23:00:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Fixed `expire_reservation()` dead code in monitor_thread.py — replaced broken method (unreachable code after `return`, undefined `ordered_sections`/`seats_by_section` variables) with a lightweight safety wrapper that delegates to `expire_session()` via session_id lookup
- Added `_cleanup_stale_reservations()` to ConcertServer — iterates ReservationTable on startup, releases any ACTIVE reservations back to AVAILABLE, restores semaphore capacity per section, and logs to global_log with "CLEANUP" tag. Handles both 2-tuple and 3-tuple seat formats.
- Hooked cleanup in `start()` after `monitor_thread.start()` but before `listener_thread.start()` — ensures stale state is cleared before any client connections are accepted
- 5 new E2E tests cover: calling expire_reservation with nonexistent tx_id, delegation to expire_session via session_id lookup, stale reservation cleanup, semaphore restoration, and session-based seat release

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix/remove expire_reservation dead code** - `bba792c` (fix)
2. **Task 2: Add startup cleanup to ConcertServer** - `790f41a` (feat)
3. **Task 3: Write E2E tests** - `0e02cce` (test)

## Files Created/Modified

- `src/server/monitor_thread.py` - Replaced broken expire_reservation() (24 lines removed, 8 added)
- `src/server/concert_server.py` - Added _cleanup_stale_reservations() + startup hook (46 lines added)
- `tests/test_phase2_e2e.py` - 5 new E2E tests (169 lines, NEW)

## Decisions Made

- **Proxy over removal**: Kept `expire_reservation()` public signature but made it delegate to `expire_session()` — preserves backward compatibility if any external code references it
- **Cleanup timing**: Between monitor thread and listener thread start — monitor's session polling is harmless on fresh boot (empty session_manager), listener runs last so clients see clean state
- **Seat format flexibility**: Handles both 2-tuple `(row, col)` and 3-tuple `(section, row, col)` — pre-session code stored seats differently from session-based code

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- **Pre-existing test failures**: Several test files (`test_protocol_contract.py`, `test_reserve_batch.py`, `test_query_seat_map.py`) have pre-existing failures caused by the Phase 1 user_id validation requirement. These tests were not updated to include `user_id` in their request payloads when Phase 1 added mandatory user_id validation. Not caused by this plan's changes. Logged in `deferred-items.md`.

## Stub Tracking

No stubs found — all code is fully wired.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary surface introduced. The `_cleanup_stale_reservations()` method runs before the listener thread starts, so it operates with zero concurrent network input.

## Next Phase Readiness

- Expiration dead code fixed and tested
- Startup cleanup implemented and tested
- Ready for Plan 02-02: Concurrent load test for expiration reliability

---

*Phase: 02-fix-expiration-restart-cleanup*
*Completed: 2026-06-01*
