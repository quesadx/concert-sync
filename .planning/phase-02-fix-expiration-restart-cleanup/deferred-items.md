# Deferred Items — Phase 2, Plan 02-01

## Pre-existing Test Failures (Not Caused by Phase 2 Changes)

The following test failures exist in the test suite but are **pre-existing** from Phase 1's user_id validation requirement. Phase 1 added mandatory `user_id` for non-QUERY actions in `validate_request()`, but several test files were not updated to include `user_id` in their request payloads.

**Plan 02-01 does not touch any of these test files.**

### Failing Tests

| Test File | Test Name | Root Cause |
|-----------|-----------|------------|
| `test_protocol_contract.py` | `test_valid_reserve_request` | RESERVE payload missing `user_id` |
| `test_query_seat_map.py` | `test_query_seat_map_reflects_reserve` | RESERVE payload missing `user_id` |
| `test_query_seat_map.py` | `test_query_seat_map_reflects_cancel` | CANCEL payload missing `user_id` |
| `test_query_seat_map.py` | `test_query_seat_map_reflects_reserve_and_confirm` | RESERVE/CONFIRM payload missing `user_id` |
| `test_reserve_batch.py` | All `TestReserveBatchProtocolValidation` tests | RESERVE_BATCH protocol validation tests use raw `validate_request()` without `user_id` |
| `test_reserve_batch.py` | All `TestReserveBatchAtomicity` tests | RESERVE_BATCH server tests don't send `user_id` |
| `test_reserve_batch.py` | All `TestReserveBatchEdgeCases` tests | Same — missing `user_id` |
| `test_reserve_batch.py` | `test_concurrent_batch_reserves_no_double_booking` | Same |

### Recommended Fix (Deferred)

Add `"user_id": "test_user"` to request payloads in these tests, or use `ConcertClient(user_id="test_user")` where possible.

### Tests That Pass With Phase 2 Changes

- `tests/test_phase1_e2e.py` — 5/5 pass (already use ConcertClient with user_id)
- `tests/test_deterministic_errors.py` — All pass
- `tests/test_lock_hierarchy_core.py` — All pass
- `tests/test_phase2_e2e.py` — 5/5 pass (NEW)
