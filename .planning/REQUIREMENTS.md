# Requirements: ConcertSync

**Defined:** 2026-06-01
**Core Value:** Multiple users can concurrently browse, select, and purchase concert seats without double-booking or losing reservations.

## v1 Requirements

### User Identification

- [ ] **USR-01**: User is prompted for a display name on startup (no auth system)
- [ ] **USR-02**: User ID is sent with all requests to identify session ownership

### Session Management

- [ ] **SES-01**: Each user has exactly one selection session with a single TTL timer
- [ ] **SES-02**: TTL is reset whenever user selects a new seat
- [ ] **SES-03**: All selected seats in a session share the same expiration timer
- [ ] **SES-04**: Expired session releases all selected seats atomically

### TTL Expiration

- [ ] **EXP-01**: Fix dead code in `monitor_thread.py` that prevents seat release on expiration
- [ ] **EXP-02**: Expiration consistently releases all seats back to AVAILABLE
- [ ] **EXP-03**: Expiration works correctly under concurrent load

### Cleanup on Restart

- [ ] **CLN-01**: On startup, detect stale temporary selections/reservations
- [ ] **CLN-02**: Release/clean stale seats automatically
- [ ] **CLN-03**: Prevent seats from remaining permanently blocked after restart

### Purchase Near Expiration

- [ ] **PCH-01**: Purchase near TTL expiration works correctly
- [ ] **PCH-02**: No race condition between purchase and expiration for same session

### Concurrent Cancellation

- [ ] **CNC-01**: Cancellation releases seats correctly while other users modify seats concurrently
- [ ] **CNC-02**: No inconsistent seat states after concurrent cancellation

### Visual Differentiation

- [ ] **UI-01**: User's own selected seats visually distinct from other users' selections
- [ ] **UI-02**: Clear legend/indicator explaining seat state colors
- [ ] **UI-03**: Preserve existing UI style — no large redesign

### Reservation Consistency

- [ ] **CON-01**: Individual reservation mode reserves ALL selected seats (not just last)
- [ ] **CON-02**: Block reservation mode works correctly with multiple selections
- [ ] **CON-03**: Consistent behavior between individual and block modes

### Saturated Zone Handling

- [ ] **SAT-01**: Detect potential conflicts before final reservation button press
- [ ] **SAT-02**: Avoid redesigning the reservation flow

### Instance Closure

- [ ] **CLS-01**: Closing the application properly cleans up or recovers selected seats

### Audit Log

- [ ] **LOG-01**: Log entries are clear and human-readable
- [ ] **LOG-02**: Concurrent events are traceable (timestamps, thread IDs, user IDs)
- [ ] **LOG-03**: Preserve existing logging infrastructure

### Concurrency Robustness

- [ ] **CR-01**: Race conditions identified and fixed
- [ ] **CR-02**: Missing synchronization added where needed
- [ ] **CR-03**: Stale resource handling verified
- [ ] **CR-04**: Lock misuse eliminated
- [ ] **CR-05**: Thread safety of all shared data structures confirmed

## v2 Requirements

(None deferred — all known issues are v1)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full authentication with passwords | Overkill; simple display name prompt sufficient |
| Web/mobile frontend | TUI-only, not required by specification |
| Database backend | In-memory + file persistence works for single-server |
| Horizontal scaling | Single-server architecture by design |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| USR-01 | Phase 1 | Pending |
| USR-02 | Phase 1 | Pending |
| SES-01 | Phase 1 | Pending |
| SES-02 | Phase 1 | Pending |
| SES-03 | Phase 1 | Pending |
| SES-04 | Phase 1 | Pending |
| EXP-01 | Phase 2 | Pending |
| EXP-02 | Phase 2 | Pending |
| EXP-03 | Phase 2 | Pending |
| CLN-01 | Phase 2 | Pending |
| CLN-02 | Phase 2 | Pending |
| CLN-03 | Phase 2 | Pending |
| PCH-01 | Phase 3 | Pending |
| PCH-02 | Phase 3 | Pending |
| CNC-01 | Phase 3 | Pending |
| CNC-02 | Phase 3 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |
| CON-01 | Phase 5 | Planned |
| CON-02 | Phase 5 | Planned |
| CON-03 | Phase 5 | Planned |
| CLS-01 | Phase 6 | Pending |
| SAT-01 | Phase 6 | Pending |
| SAT-02 | Phase 6 | Pending |
| LOG-01 | Phase 6 | Pending |
| LOG-02 | Phase 6 | Pending |
| LOG-03 | Phase 6 | Pending |
| CR-01 | Phase 7 | Pending |
| CR-02 | Phase 7 | Pending |
| CR-03 | Phase 7 | Pending |
| CR-04 | Phase 7 | Pending |
| CR-05 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---

*Requirements defined: 2026-06-01*
*Last updated: 2026-06-01 after initial definition*
