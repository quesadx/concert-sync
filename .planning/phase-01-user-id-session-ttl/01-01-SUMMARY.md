# Plan 01-01 SUMMARY: User ID + Session TTL Foundation

## What Was Built

**Status:** Complete

**Objective:** Establish user identification and session-TTL foundation — TUI login, user_id injection, SessionManager, session-aware RESERVE.

## Files Created
- `frontend_tui/login_screen.py` — LoginScreen widget (welcome, name input, Join button, error handling)
- `src/server/session_manager.py` — UserSession dataclass + SessionManager (thread-safe get_or_create, get_by_session_id, get_expired, remove)
- `tests/test_phase1_e2e.py` — 5 E2E tests for session-TTL behavior (currently skipped, will pass after Plan 01-02)

## Files Modified
- `frontend_tui/app.py` — Push LoginScreen on mount, _on_login callback, ConcertClient with user_id
- `src/server/concert_server.py` — Added SessionManager instance
- `src/server/transactional_thread.py` — handle_reserve uses SessionManager (get_or_create, appends seat, resets TTL, returns session_id)
- `src/utils/protocol_validator.py` — user_id presence validation (skipped for QUERY/QUERY_SEAT_MAP)
- `src/client/concert_client.py` — user_id parameter in __init__, auto-injected in send_request
- `tests/test_reserve_batch.py` — Updated ConcertClient calls for new constructor signature

## Key Design Decisions
- UserSession seats stored as `List[Tuple[Section, int, int]]` for cross-section reserves
- SessionManager.get_or_create uses `threading.Lock` around check-and-create (prevents T-01-02 race)
- user_id validated as non-empty string for all non-QUERY actions (generic error message per T-01-03)
- ConcertClient injects user_id in send_request before serialization (not per-method)

## Requirements Covered
- USR-01: User prompted for display name on startup ✓
- USR-02: User ID sent with all requests ✓
- SES-01: Each user has one session with single TTL ✓
- SES-02: TTL reset on new seat select ✓
- SES-03: All seats in session share same expiration ✓

## Missing (deferred to Plan 01-02)
- Session-aware CONFIRM/CANCEL with ownership check
- Session-aware RESERVE_BATCH
- MonitorThread session expiry
- TUI session tracking for session_id reuse
- e2e tests enabled (skip decorators removed)
