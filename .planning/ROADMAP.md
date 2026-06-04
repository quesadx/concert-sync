# Roadmap: ConcertSync

**Created:** 2026-06-01
**Granularity:** Standard (5-8 phases)
**Execution:** Sequential (one phase at a time)

---

### Phase 1: User ID + Session-Based TTL
**Goal:** Establish user identification and migrate TTL from per-seat to per-session model
**Mode:** mvp

**Requirements:** USR-01, USR-02, SES-01, SES-02, SES-03, SES-04

**Success Criteria:**
1. User prompted for display name on startup, ID sent with all requests
2. Each user has exactly one selection session with single TTL
3. Selecting a new seat resets session TTL
4. All selected seats in session share same expiration timer
5. Expired session releases all selected seats atomically
6. Existing reservation logic preserved — only timer ownership changes

**Plans:** 2 plans in 2 waves

**Wave 1** *(foundation — no dependencies)*
- [x] `01-01-PLAN.md` — LoginScreen + SessionManager + user_id injection + session-aware RESERVE

**Wave 2** *(blocked on Wave 1 completion)*
- [x] `01-02-PLAN.md` — Session-aware batch/confirm/cancel + MonitorThread session expiry + TUI TTL tracking

**Cross-cutting constraints:**
- All plans: Session ownership verification (`session.user_id == request.user_id`) on every CONFIRM/CANCEL
- All plans: SessionManager lock protects against concurrent get_or_create race
- All plans: Old per-seat TTL expiry code remains untouched (Phase 2 fixes it)

**Risks:**
- Session TTL must not break existing reservation flow
- Concurrent session creation needs synchronization
- Existing tests may need updates for new TTL model

---

### Phase 2: Fix Expiration + Restart Cleanup
**Goal:** Fix dead code in TTL expiration and add startup cleanup of stale reservations

**Requirements:** EXP-01, EXP-02, EXP-03, CLN-01, CLN-02, CLN-03

**Success Criteria:**
1. Dead code in `monitor_thread.py` expiration logic fixed — seats actually released
2. Expiration consistently releases all seats under concurrent load
3. On server startup, stale reservations detected and cleaned
4. No seats remain permanently blocked after restart
5. All existing tests pass

**Files likely modified:**
- `src/server/monitor_thread.py` — Fix dead code, add startup cleanup
- `src/server/concert_server.py` — Cleanup on init

**Risks:**
- Startup cleanup must not race with client connections
- Expiration fix changes behavior — verify against all test cases

**Plans:** 2 plans in 2 waves

**Wave 1** *(foundation — no dependencies)*
- [x] `02-01-PLAN.md` — Fix expire_reservation dead code + startup cleanup + E2E tests

**Wave 2** *(blocked on Wave 1 completion)*
- [x] `02-02-PLAN.md` — Concurrent load test for expiration reliability

**Cross-cutting constraints:**
- All plans: `expire_reservation` dead code must be fixed before concurrent tests (EXP-01 → EXP-03)
- All plans: startup cleanup runs before listener thread — no races with client connections
- All plans: semaphores released during cleanup (not just seat state)

---

### Phase 3: Fix Buy Near Expiry + Concurrent Cancellation ✓
**Goal:** Eliminate race conditions in purchase-near-expiration and concurrent cancellation

**Status:** Executed ✓

**Requirements:** PCH-01, PCH-02, CNC-01, CNC-02

**Success Criteria:**
1. ✅ Purchase completes correctly even when session TTL expires concurrently
2. ✅ No race between purchase handler and expiration monitor
3. ✅ Cancellation releases seats correctly while other users modify seats
4. ✅ No inconsistent seat states after concurrent cancellation
5. ✅ All synchronization is correct under concurrent load

**Plans:** 2 plans in 2 waves

**Wave 1** *(foundation — no dependencies)*
- [x] `03-01-PLAN.md` — Fix race conditions: semaphore release inside lock in expire_session + handle_cancel; concurrent cancel/expire stress test

**Wave 2** *(blocked on Wave 1 completion)*
- [x] `03-02-PLAN.md` — E2E tests: purchase-near-expiry (3 tests) + concurrent cancellation (3 tests); update race tests to use real expire_session path

**Cross-cutting constraints:**
- All plans: semaphore release must be inside `table_and_sections` lock (not after) to prevent seat-AVAILABLE but semaphore-unavailable window
- All plans: `session.seats` read outside lock is safe for section-set computation; actual seat state verified inside lock
- All plans: `table_and_sections` serialization via `mutex_table` prevents concurrent double-expire/confirm/cancel on overlapping sections

**Files modified:**
- `src/server/monitor_thread.py` — expire_session: semaphore release inside lock
- `src/server/transactional_thread.py` — handle_cancel: semaphore release inside lock
- `tests/concurrent_tests.py` — Added test_concurrent_cancel_and_expire stress test
- `tests/test_transaction_races.py` — Use real expire_session path (not legacy expire_reservation)
- `tests/test_phase3_e2e.py` (NEW) — 6 E2E tests for purchase-near-expiry + concurrent cancellation

**Risks:**
- ~~Fixing races may introduce deadlocks if lock ordering wrong~~ — Mitigated: all operations use `table_and_sections` with same lock ordering (`mutex_table` → sections in enum order)
- ~~Changes to cancellation affect concurrent seat state~~ — Mitigated: CANCEL and RESERVE serialize on `table_and_sections`; stress test verifies no double-booking or seat loss

---

### Phase 4: Visual Differentiation ✓
**Goal:** Users can distinguish own selected seats from other users' selections

**Status:** Executed ✓

**Requirements:** UI-01, UI-02, UI-03

**Success Criteria:**
1. ✅ Own selected seats display in teal bold "Y" vs others' amber bold "R"
2. ✅ Legend updated to "A=AVAILABLE  R=RESERVED  Y=YOURS  S=SOLD"
3. ✅ Existing UI style preserved — no layout changes, no new widgets, no CSS changes

**Plans:** 2 plans in 2 waves

**Wave 1** *(foundation — no dependencies)*
- [x] `04-01-PLAN.md` — Server-side OWN_RESERVED: SeatState enum extension + get_by_user_id helper + enriched handle_query_seat_map

**Wave 2** *(blocked on Wave 1 completion)*
- [x] `04-02-PLAN.md` — TUI per-state color rendering: _seat_cell() with per-cell Style via update_cell_at() + legend update

**Cross-cutting constraints:**
- All plans: OWN_RESERVED is view-only — never stored in SeatMatrix (only in query response)
- All plans: handle_query_seat_map must only tag the requesting user's OWN sessions — never expose another user's ownership

---

### Phase 5: Reservation Consistency
**Goal:** Individual mode reserves ALL selected seats, not just the last one

**Requirements:** CON-01, CON-02, CON-03

**Success Criteria:**
1. Individual reservation reserves all selected seats atomically
2. Block mode continues to work correctly
3. Both modes produce consistent results
4. Existing workflows preserved

**Files likely modified:**
- `src/server/concert_server.py` — Reservation handler
- `src/shared_resources/` — Reservation logic
- `src/client/concert_client.py` — Reservation request format

**Risks:**
- Changing individual mode behavior may confuse existing clients
- Atomic multi-seat reservation needs proper transaction semantics

---

### Phase 6: Instance Closure + Saturated Zone + Audit Log
**Goal:** Handle application closure, early conflict detection, improved logging

**Requirements:** CLS-01, SAT-01, SAT-02, LOG-01, LOG-02, LOG-03

**Success Criteria:**
1. Closing application properly cleans up or recovers selected seats
2. Conflicts detectable before final reservation button (if feasible without redesign)
3. Log entries clear, human-readable, with concurrency traceability
4. Existing logging infrastructure preserved

**Files likely modified:**
- `src/server/concert_server.py` — Shutdown cleanup
- `src/client/concert_client.py` — Client disconnect handling
- `frontend_tui/app.py` — Saturated zone feedback
- `src/shared_resources/` — Logging utilities

**Risks:**
- Shutdown cleanup must not block or hang
- Saturated zone changes must not redesign the flow

---

### Phase 7: Concurrency Robustness Review
**Goal:** Final audit and fixes for remaining concurrency issues

**Requirements:** CR-01, CR-02, CR-03, CR-04, CR-05

**Success Criteria:**
1. All identified race conditions fixed
2. Missing synchronization added where needed
3. Stale resource handling verified
4. No lock misuse remains
5. All shared data structures confirmed thread-safe
6. All existing tests pass

**Files likely modified:**
- All server-side files — concurrency audit fixes
- `src/shared_resources/` — Lock/synchronization review

**Risks:**
- Last-phase changes could regress earlier fixes
- Must not introduce architectural changes

---

## Phase Dependency Graph

```
Phase 1 (User ID + Session TTL)
  └── Phase 2 (Fix Expiration + Cleanup) — needs session TTL
  └── Phase 3 (Buy Near Expiry + Cancellation) — needs session TTL
  └── Phase 4 (Visual Diff) — needs User ID
        └── Phase 5 (Reservation Consistency) — independent
              └── Phase 6 (Closure + Saturated + Log) — independent
                    └── Phase 7 (Concurrency Review) — needs all fixes in place
```

## Coverage

| # | Phase | Requirements | Success Criteria |
|---|-------|-------------|------------------|
| 1 | User ID + Session TTL | 6 | 6 |
| 2 | Fix Expiration + Cleanup | 6 | 5 |
| 3 | Buy Near Expiry + Cancellation | 4 | 5 |
| 4 | Visual Differentiation | 3 | 3 |
| 5 | Reservation Consistency | 3 | 4 |
| 6 | Closure + Saturated + Log | 5 | 4 |
| 7 | Concurrency Review | 5 | 5 |
|   | **Total** | **32** | **32** |

---

*Last updated: 2026-06-01 after initial definition*
