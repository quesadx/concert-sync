# Phase 5 — Plan 01 Summary: RESERVE_SELECTED handler + client method

**Wave:** 1
**Status:** Executed ✓
**Commit:** 59462b3

## Changes

### src/server/transactional_thread.py
- Added `RESERVE_SELECTED` route in `run()` dispatch block
- Added `handle_reserve_selected()`: validates all seats AVAILABLE inside `table_and_sections` lock, marks RESERVED, acquires semaphore slots, appends to session — all-or-nothing rollback. Mirrors `handle_reserve_batch` pattern.

### src/client/concert_client.py
- Added `reserve_selected(seats)` method sending `{"action": "RESERVE_SELECTED", "seats": [...]}`

## Verification
- `RESERVE_SELECTED` action dispatched in `run()`
- `handle_reserve_selected` validates bounds, checks availability, marks RESERVED, acquires semaphores atomically
- `ConcertClient.reserve_selected()` sends correct action
- Existing `RESERVE` and `RESERVE_BATCH` paths unchanged

## Requirements Covered
- CON-01 (individual mode reserves all seats atomically)
- CON-03 (both modes produce consistent results)
