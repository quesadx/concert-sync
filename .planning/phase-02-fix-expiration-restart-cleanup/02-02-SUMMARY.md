---
phase: 02-fix-expiration-restart-cleanup
plan: 02
subsystem: testing
tags: [concurrency, expiration, stress-test, pytest]

# Dependency graph
requires:
  - phase: 02-fix-expiration-restart-cleanup
    provides: expire_reservation fix, startup cleanup, E2E test fixtures
provides:
  - Concurrent expiration stress test verifying seat release under concurrent RESERVE load
affects:
  - phase: 03-fix-buy-near-expiry-concurrent-cancel
  - phase: 07-concurrency-robustness-review

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Session TTL manipulation for fast expiration testing (set ttl_secs + last_activity post-creation)"
    - "Barrier-synchronized concurrent reserve burst pattern"

key-files:
  created: []
  modified:
    - tests/concurrent_tests.py
key-decisions:
  - "Used post-hoc session TTL manipulation (set ttl_secs=2, last_activity=-3s) instead of importlib.reload — dataclass field defaults are baked at class definition time, cannot be monkey-patched after import"
  - "Barrier synchronization ensures all 5 clients hit server simultaneously"
  - "Test validates three invariants: no leaked RESERVED seats, semaphore counts restored, capacity invariant maintained"

requirements-completed: [EXP-03]

# Metrics
duration: 5min
completed: 2026-06-01
---

# Phase 2 Plan 2: Concurrent load test for expiration reliability

**Concurrent expiration stress test verifies MonitorThread releases all seats under concurrent RESERVE + expire cycle, with semaphore restoration and no leaked RESERVED seats**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-01T18:03:10Z
- **Completed:** 2026-06-01T18:08:24Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `test_expiration_releases_seats_under_concurrent_reserve()` to concurrent_tests.py — a stress test with 5 concurrent clients using `threading.Barrier` for synchronized reservation burst
- Test forces session TTL=2s with `last_activity` set to 3s in the past, then waits 4s for MonitorThread poll cycle to expire sessions naturally
- Verifies no leaked RESERVED seats, semaphore counts restored to full capacity, and seat accounting invariant maintained
- Test executes in ~5 seconds and runs only when explicitly invoked (not in the default test suite)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add concurrent expiration stress test to concurrent_tests.py** - `ae30000` (test/02-02)

**Plan metadata:** (committed in next step)

## Files Created/Modified

- `tests/concurrent_tests.py` - Added `test_expiration_releases_seats_under_concurrent_reserve()` function with barrier-synchronized concurrent reserve burst, session TTL forcing, and three-way invariant verification

## Decisions Made

- **Post-hoc session TTL manipulation:** Attempted `__dataclass_fields__['ttl_secs'].default` monkey-patch first, but discovered Python dataclasses bake defaults into the generated `__init__` at class definition time — changing `__dataclass_fields__` metadata does NOT affect new instances. Instead, set `session.ttl_secs = 2` and `session.last_activity = time.time() - 3` on sessions after reservation phase completes. This still exercises the real MonitorThread `run()` → `get_expired()` → `expire_session()` path.
- **Barrier synchronization:** All 5 threads start simultaneously via `threading.Barrier(5)`, ensuring concurrent pressure on server.
- **Three verification layers:** (1) `_check_invariants()` for capacity/semaphore consistency, (2) explicit `stats["reserved"] == 0` per section, (3) explicit `sem_value == capacity` per section.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Dataclass field default not patchable via __dataclass_fields__**
- **Found during:** Task 1 (first test run failed — RESERVED seats not expiring)
- **Issue:** Monkey-patching `UserSession.__dataclass_fields__['ttl_secs'].default = 2` after module import had no effect. Python dataclasses bake default values into the compiled `__init__` at class definition time. New `UserSession()` calls still used `ttl_secs=300`.
- **Fix:** Removed `__dataclass_fields__` patching and instead set `session.ttl_secs = 2` + `session.last_activity = time.time() - 3` on all sessions after the reservation phase completes. This still exercises the exact same MonitorThread expiration path (poll → get_expired → expire_session → seat release).
- **Files modified:** tests/concurrent_tests.py
- **Verification:** Test passes — MonitorThread expires sessions and releases all seats.
- **Committed in:** ae30000 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking by Rule 3)
**Impact on plan:** Fix was isolated to the TTL mechanism; no scope creep. The end-to-end test path (MonitorThread poll + expire_session) is identical.

## Issues Encountered

- **Protocol contract test failure is pre-existing:** `tests/test_protocol_contract.py::TestCoordinatedRequestValidation::test_valid_reserve_request` fails with `assert False is True` on `validate_request()` — this test was failing before Plan 02-02 changes (confirmed by testing commit without concurrent_tests.py changes). Not caused by this plan.

## Known Stubs

None — test produces real assertions against live server state.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: test-only | tests/concurrent_tests.py | New concurrent test — no new production endpoints or network surface |

## Next Phase Readiness

- Phase 2 is complete after this plan (both 02-01 and 02-02 executed)
- Expiration reliability verified under concurrent load
- Ready for Phase 3: Buy Near Expiry + Concurrent Cancellation

## Self-Check: PASSED

- ✅ SUMMARY.md exists at `.planning/phase-02-fix-expiration-restart-cleanup/02-02-SUMMARY.md`
- ✅ Commit `ae30000` exists in git log (test(02-02): add concurrent expiration stress test)
- ✅ `python -m pytest tests/concurrent_tests.py -x -v -k test_expiration_releases_seats` passes
- ✅ `python -c "import tests.concurrent_tests"` imports without error
- ✅ Phase 2 E2E tests pass (5/5)
- ✅ Phase 1 E2E tests pass (5/5)

## Execution Notes

- **Pre-existing failure:** `tests/test_protocol_contract.py::TestCoordinatedRequestValidation::test_valid_reserve_request` — was failing before this plan's changes (protocol validation regression, not caused by 02-02). Scope-boundary rule applies; not fixed.
- **Deviation (Rule 3):** Dataclass field defaults baked at class-definition time, monkey-patch via `__dataclass_fields__` ineffective. Fixed via post-hoc session TTL manipulation. See Deviations section.

---

*Phase: 02-fix-expiration-restart-cleanup*
*Completed: 2026-06-01*
