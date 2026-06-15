---
phase: quick-260604-qlg
plan: "01"
subsystem: frontend
tags: [pyside6, sessions, persistence, ux]

provides:
  - Auto-load user sessions on connect (no manual reclaim needed)
  - TX ID auto-filled for one-click confirm/cancel
  - TTL countdown stays in sync with server on every poll
  - Removed dead Reclaim Session UI

tech-stack:
  added: []
  patterns:
    - Server QUERY_SEAT_MAP returns user_session field with session_id, seats, ttl_secs, last_activity
    - Client parses user_session on every poll, updates TTL, creates TrackedSession on first detection

key-files:
  modified:
    - src/server/transactional_thread.py
    - frontend_pyside6/main_window.py
    - frontend_pyside6/workers/network_worker.py
    - frontend_pyside6/widgets/connection_panel.py

key-decisions:
  - "Return user_session in QUERY_SEAT_MAP response rather than adding a new protocol action — minimal server change, backward-compatible"
  - "Update TTL on every poll by refreshing created_at from server's last_activity — keeps client countdown in sync"
  - "Set TX ID on every poll so it stays current even after user clears it"

duration: ~2min
completed: 2026-06-05
---

# Quick Task 260604-qlg: Auto-load user sessions, remove manual reclaim

**Each user now gets their reservations automatically displayed on connect — just enter your user ID and click Connect.**

## Changes

1. **Server: QUERY_SEAT_MAP now returns `user_session`** (`transactional_thread.py:643-658`)
   - When the requesting user has an active session, the response includes `user_session: {session_id, seats, ttl_secs, last_activity}`
   - Backward-compatible — existing clients ignore the extra field

2. **Client: Parse `user_session` on every poll** (`main_window.py:_sync_user_session`)
   - Creates `TrackedSession` entries from server data on first detection
   - Updates `created_at` from `last_activity` on every poll — keeps TTL countdown accurate
   - Auto-fills TX ID input for one-click confirm/cancel
   - Persists session_id via QSettings for cross-session continuity

3. **Client: Removed manual session reclaim** (`connection_panel.py`)
   - Removed Session ID display label, reclaim input, and Reclaim Session button
   - Removed `reclaim_requested` signal and `_on_reclaim_session` handler
   - Simplified to just User ID + Host + Port + Connect

4. **Client: PollWorker emits `user_session`** (`network_worker.py:158`)
   - `finished` signal carries third argument for user session data

## Files Modified
- `src/server/transactional_thread.py` — Added `user_session` to QUERY_SEAT_MAP response
- `frontend_pyside6/main_window.py` — Added `_sync_user_session`, updated `_on_poll_success`, removed reclaim wiring
- `frontend_pyside6/workers/network_worker.py` — Updated `PollWorker` to emit `user_session`
- `frontend_pyside6/widgets/connection_panel.py` — Removed reclaim UI

## Commit
- `ee954b3` — feat: auto-load user sessions on connect via QUERY_SEAT_MAP, remove manual session reclaim

---

*Quick task: 260604-qlg*
*Completed: 2026-06-05*
