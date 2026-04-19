# Feature Plan: reserve-multiple-seats

**Roadmap Item:** #6  
**Status:** Planning  
**Date:** 2026-04-18

---

## Objective

Allow users to reserve multiple specific seats in a single atomic request, with deterministic rollback on partial failure.

**Key Requirement:** No inconsistent partial reserves—either all seats reserve successfully or none do.

---

## Design Approach

### 1. Protocol Extension

Introduce new action `RESERVE_BATCH` as complement to existing `RESERVE`:

```json
{
  "action": "RESERVE_BATCH",
  "seats": [
    {"section": "VIP", "row": 0, "col": 0},
    {"section": "VIP", "row": 0, "col": 1},
    {"section": "PREFERENTIAL", "row": 5, "col": 10}
  ]
}
```

**Constraints:**
- At least 1 seat required in payload
- Max 10 seats per batch (configurable)
- Seats can span multiple sections
- Duplicate coordinates rejected

**Response on Success:**

```json
{
  "status": "SUCCESS",
  "transaction_id": "<tx_id>",
  "reserved_seats": [
    {"section": "VIP", "row": 0, "col": 0},
    {"section": "VIP", "row": 0, "col": 1},
    {"section": "PREFERENTIAL", "row": 5, "col": 10}
  ],
  "ttl": 300
}
```

**Response on Failure:**
- If ANY seat unavailable: `FAILURE` with `error_code`
- No changes to seat_matrix
- No transaction created

---

### 2. Implementation Strategy

#### Lock Acquisition Order (Hierarchy Preservation)

1. Determine all unique sections involved in batch
2. Sort sections in enum order: `VIP → PREFERENTIAL → GENERAL`
3. Acquire locks in that strict order
4. Validate ALL seats while holding all locks
5. Mark ALL seats as RESERVED atomically
6. Acquire semaphore slots for each section
7. If semaphore acquisition fails for ANY section → rollback ALL (revert seats + release acquired semaphores)

#### Atomicity Guarantees

- **All-or-nothing:** Either all seats transition from AVAILABLE → RESERVED, or none do
- **No deadlock:** Respects lock hierarchy
- **No race conditions:** Validation + state change under lock

#### Rollback Strategy

If semaphore acquire fails partway through:
1. Release all acquired semaphore slots (in reverse order)
2. Revert all seats from RESERVED back to AVAILABLE
3. Return deterministic `FAILURE` response with `ERR_NO_CAPACITY`

---

### 3. Files to Modify

| File | Changes |
|------|---------|
| `docs/protocol-contract-v1.md` | Add RESERVE_BATCH request/response schemas |
| `src/utils/protocol_validator.py` | Add `validate_reserve_batch_payload()` |
| `src/utils/error_responses.py` | Add `failure_reserve_batch_partial()` (if needed) |
| `src/server/transactional_thread.py` | Add `handle_reserve_batch()` dispatcher + logic |
| `tests/test_protocol_contract.py` | Add RESERVE_BATCH validation tests (10+ tests) |
| `tests/test_reserve_batch.py` (NEW) | Add atomicity + edge case tests |
| `src/client/concert_client.py` | Add `reserve_batch()` method with typed exceptions |

---

### 4. Test Plan

**Protocol Validation Tests (in test_protocol_contract.py):**
- ✓ Valid RESERVE_BATCH with 1 seat
- ✓ Valid RESERVE_BATCH with 3 seats (mixed sections)
- ✓ Empty seats array → FAILURE
- ✓ Duplicate seat coordinates → FAILURE
- ✓ Invalid section in seats array → FAILURE
- ✓ Seat coordinates out of bounds → FAILURE
- ✓ Non-array seats field → FAILURE
- ✓ Missing seats field → FAILURE

**Atomicity Tests (in test_reserve_batch.py, new file):**
- ✓ All seats available → all reserved successfully
- ✓ First seat unavailable → no seats reserved (abort)
- ✓ Middle seat unavailable → no seats reserved (abort)
- ✓ Section at capacity during batch → no seats reserved (rollback)
- ✓ Concurrent RESERVE_BATCH requests → no conflicts
- ✓ RESERVE_BATCH + single RESERVE race condition → no inconsistency
- ✓ CONFIRM after successful RESERVE_BATCH → all seats confirmed

---

### 5. Execution Sequence

1. **Phase 1: Protocol & Validation**
   - Update `docs/protocol-contract-v1.md` with RESERVE_BATCH schema
   - Add `validate_reserve_batch_payload()` to protocol_validator.py
   - Add protocol validation tests (expect ~8 test failures before impl)

2. **Phase 2: Server Implementation**
   - Implement `handle_reserve_batch()` in transactional_thread.py
   - Ensure lock hierarchy + atomicity
   - Create new test_reserve_batch.py with atomicity tests

3. **Phase 3: Client Support**
   - Add `reserve_batch()` method to concert_client.py
   - Add typed exception handling
   - Update concurrent_tests.py to stress-test batch reserves

4. **Phase 4: Verification**
   - Run all 100+ existing tests (protocol + deterministic errors + query atomicity)
   - Run new ~15 RESERVE_BATCH-specific tests
   - Run concurrent_tests.py with batch operations mixed in

---

### 6. Success Criteria

- [ ] ✅ 8 protocol validation tests passing for RESERVE_BATCH
- [ ] ✅ 7+ atomicity tests passing for RESERVE_BATCH
- [ ] ✅ Concurrent stress test with batch + single reserves (no corruption)
- [ ] ✅ All existing 100 tests still passing
- [ ] ✅ Feature branch mergeable with documented commit history

---

## Risk & Mitigation

| Risk | Mitigation |
|------|-----------|
| Lock acquisition deadlock | Strict enum-order lock acquisition verified in code review |
| Partial semaphore acquire failure | Test explicitly for rollback path; mock semaphore failures |
| Race condition between batch validates + acquires | Validation + acquire happen atomically under lock |
| Client confusion (RESERVE vs RESERVE_BATCH) | Clear API naming + typed exceptions + documentation |

---

## Next Steps

1. ✅ Review this plan for feasibility
2. → Update `docs/protocol-contract-v1.md` with RESERVE_BATCH schema
3. → Add validation logic to `protocol_validator.py`
4. → Implement `handle_reserve_batch()` in transactional_thread.py
5. → Write comprehensive tests
6. → Run full test suite
