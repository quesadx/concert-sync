---
phase: 4
plan: 01
subsystem: server
tags: [ownership, query, enum]
key-files:
  created:
    - src/utils/enums.py
    - src/server/session_manager.py
    - src/server/transactional_thread.py
metrics:
  tasks: 2
  commits: 2
---

## Summary

Added server-side ownership differentiation to QUERY_SEAT_MAP so a user's own RESERVED seats are tagged as `OWN_RESERVED` in the response.

### Commits

| Task | Hash | Description |
|------|------|-------------|
| 1 | a1c6788 | Add OWN_RESERVED to SeatState enum + get_by_user_id to SessionManager |
| 2 | 8c1dd69 | Enrich handle_query_seat_map with ownership cross-reference |

### Deviations

None.

## Self-Check

- [x] SeatState.OWN_RESERVED exists and is view-only
- [x] SessionManager.get_by_user_id returns None for unknown user, never creates sessions
- [x] handle_query_seat_map tags requesting user's RESERVED seats as OWN_RESERVED
- [x] Other users' RESERVED seats remain RESERVED
- [x] Seat matrix never stores OWN_RESERVED internally
- [x] Anonymous queries get all RESERVED without ownership data

**Status:** PASSED
