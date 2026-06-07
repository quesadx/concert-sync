---
status: complete
task_id: 260604-r7u
---

# Quick Task 260604-r7u: Fix per-seat TTL tracking

**Description:** Each reserved seat now gets its own independent TTL. When a seat's TTL expires, only that seat is released — not all seats in the session. Race conditions in the monitor expiry double-check are also fixed.

## Changes

### 1. Per-seat timestamps (`session_manager.py`)
- Added `seat_timestamps: Dict[Tuple[Section, int, int], float]` to `UserSession`
- Added `has_expired_seats` property (at least one seat expired)
- Added `get_expired_seats()` method (list of expired seat keys)
- Added `record_seat_timestamp()` method
- Changed `is_expired` to check per-seat timestamps with fallback to `last_activity`
- Changed `get_expired()` to use `has_expired_seats`

### 2. Monitor expiry fixes (`monitor_thread.py`)
- Fixed double-check: added `get_expired_seats()` check to prevent premature release of TTL-refreshed seats
- Changed `expire_session()` to release only expired seats, not all seats
- Session stays alive if any unexpired seats remain
- Only removed from session_manager when all seats are released

### 3. Reserve handlers (`transactional_thread.py`)
- All three handlers (RESERVE, RESERVE_BATCH, RESERVE_SELECTED) now:
  - Record per-seat timestamps via `record_seat_timestamp()` instead of blanket `reset_ttl()`
  - Re-fetch session inside table lock to prevent orphaned reservations

### 4. SQLite persistence (`sqlite_store.py`)
- Added `reserved_at` column to `session_seats` table
- Migration for existing databases
- `save_all_sessions()` persists per-seat timestamps
- `load_all_sessions()` restores per-seat timestamps

### 5. Session restoration (`concert_server.py`)
- Passes `seat_timestamps` when reconstructing `UserSession` from DB

### 6. Test fix (`test_session_persistence.py`)
- Updated `test_expired_session_not_reclaimable` to age per-seat timestamps

## Race conditions fixed

1. **Premature expiry:** Monitor double-check now verifies seats are still expired under lock
2. **Orphaned reservations:** Reserve handlers re-fetch session inside table lock
