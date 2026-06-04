# Plan 06-02: TUI disconnect detection + saturated zone pre-flight — Summary

**Phase:** 6 — Instance Closure + Saturated Zone + Audit Log
**Plan:** 06-02
**Wave:** 2
**Executed:** 2026-06-04
**Status:** Complete ✓

## What was built

### Task 1: Server disconnect detection (TUI)
- **`frontend_tui/app.py`**: Added `consecutive_failures` counter and `server_disconnected` flag in `__init__`.
- `_refresh_query_failed` increments on each query failure; after 3 consecutive failures, shows "DISCONNECTED — server unreachable" status and sets `server_disconnected = True`.
- `_refresh_query_succeeded` resets counter to 0 and clears disconnected flag, reverting connection status to "Connected to {host}:{port}...".
- All detection is TUI-side — zero `ConcertClient` changes.

### Task 2: Saturated zone pre-flight check
- **`frontend_tui/app.py`**: Added pre-flight check in `_reserve_pending_selections()` that validates each pending seat against the latest `seat_map_snapshot`.
- Non-AVAILABLE seats are removed from `pending_selections` with a `[SATURATED]` warning listing the specific conflict seats.
- Seat map re-renders after conflict removal; early return if all seats conflicted.
- Purely client-side — no server changes (SAT-02).

### Task 3: E2E tests
- **`tests/test_phase6_e2e.py`**: 4 new tests across two classes:
  - `TestDisconnectDetection` (2 tests): client raises `ConcertClientError` on stopped server; client recovers after server restart on new port
  - `TestSaturatedZone` (2 tests): pre-flight detects seat reserved by another user; pre-flight passes for genuinely available seats

## Requirements covered
- **CLS-01**: TUI detects server shutdown after 3 failed queries, shows disconnect UI
- **SAT-01**: Saturated zone pre-flight check runs before Reserve Pending
- **SAT-02**: No server-side changes — detection entirely client-side

## Verification
- ✅ 9/9 Phase 6 tests pass (5 from 06-01 + 4 from 06-02)
- ✅ `consecutive_failures` increments on failure, resets on success
- ✅ After 3 failures, disconnect UI activates; reconnection restores normal status
- ✅ Saturated zone check removes conflict seats with `[SATURATED]` warning
- ✅ Zero server-side changes for saturated zone detection
