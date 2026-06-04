# Phase 2: Fix Expiration + Restart Cleanup — Research

**Researched:** 2026-06-01
**Domain:** Dead code repair, stale state cleanup, expiration reliability
**Confidence:** HIGH

## Summary

Phase 1 introduced session-based TTL with `expire_session()` as the active expiration path,
but left the old `expire_reservation()` method on disk with a **dead code bug** — lines that
mark seats AVAILABLE are indented after an unconditional `return`, making them unreachable.
Additionally, `expire_reservation()` references undefined variables (`ordered_sections`,
`seats_by_section`), so even if the indentation were fixed, the method would crash.

The server also has no startup-cleanup mechanism: if the process crashes while sessions
hold seats as RESERVED, those seats remain permanently blocked after restart.

**Primary recommendation:** Fix the dead code by rewriting `expire_reservation()` to be
a functional wrapper that delegates to `expire_session()` for backward compat, or remove it
entirely since nothing calls it. Add `startup_cleanup()` to `ConcertServer` that scans the
ReservationTable on boot and releases any stale seats.

### Why not keep expire_reservation?

The old method was deprecated in Phase 1 and is no longer called from `run()`. Its dead code
cannot be meaningfully fixed because it operates on `Reservation` objects, which are no
longer created by the session-based flow. The cleanest approach is to remove it and ensure
all expiration goes through `expire_session()`.

---

<user_constraints>
## User Constraints (from ROADMAP.md + REQUIREMENTS.md)

### Locked Decisions (from Phase 1 SUMMARYs + PROJECT.md)
- SessionManager is the single source of truth for active sessions
- No architectural redesign — minimal changes justified by specific requirements
- Old `expire_reservation` was deprecated but left for analysis — Phase 2 may remove it
- Startup cleanup must not race with client connections
- All existing tests must pass after Phase 2 changes
- ReservationTable still exists and must be handled for stale entries

### the agent's Discretion
- Whether to remove `expire_reservation()` or fix it as a delegate
- Where to hook startup cleanup (`__init__` vs `start()`)
- Implementation of the cleanup scan (ReservationTable iteration)
- Whether to add a test-only helper for injecting stale reservations

### Deferred Ideas (OUT OF SCOPE for Phase 2)
- Session persistence across server restarts (would require serialization)
- Removing ReservationTable entirely (may be used by other code paths)
- Phase 3 race conditions (buy near expiry, concurrent cancellation)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXP-01 | Fix dead code in `monitor_thread.py` that prevents seat release on expiration | `expire_reservation()` lines 73-78 unreachable after `return` on line 71; `ordered_sections`/`seats_by_section` undefined. Either remove or delegate to `expire_session()`. |
| EXP-02 | Expiration consistently releases all seats back to AVAILABLE | `expire_session()` already works correctly — double-check inside lock, semaphore release outside lock. The fix for EXP-01 ensures the old path can't be accidentally invoked. |
| EXP-03 | Expiration works correctly under concurrent load | Existing `expire_session()` uses proper lock ordering. Need concurrent tests to verify. |
| CLN-01 | On startup, detect stale temporary selections/reservations | ReservationTable may hold entries from pre-crash state. Scan on boot, release seats. |
| CLN-02 | Release/clean stale seats automatically | For each stale Reservation: mark seats AVAILABLE, release semaphores, delete reservation. |
| CLN-03 | Prevent seats from remaining permanently blocked after restart | Startup cleanup handles the crash-recovery case. Any missed seats would be from incomplete cleanup — thoroughness needed. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Dead code removal | Server/MonitorThread | — | `expire_reservation()` lives here |
| Session expiry | Server/MonitorThread | Server/SessionManager | `expire_session()` already correct |
| Startup cleanup | Server/ConcertServer | Shared/ReservationTable | Cleanup runs on boot before listener starts |
| Concurrent expiry tests | Tests | — | New concurrent test for EXP-03 |

## Standard Stack

### Core
| Component | Purpose |
|-----------|---------|
| `MonitorThread.expire_session()` | Active expiration path (already correct) |
| `MonitorThread.expire_reservation()` | Dead code to fix/remove |
| `ConcertServer.start()` | Hook for startup cleanup |
| `ReservationTable` | Source of stale entries on boot |

### Supporting
| Module | Purpose |
|--------|---------|
| `seat_matrix.py` | Mark seats AVAILABLE during cleanup |
| `semaphore_manager.py` | Release semaphores during cleanup |
| `global_log.py` | Log cleanup events |

## Common Pitfalls

### Pitfall 1: Startup Cleanup Racing with Client Connections
**What goes wrong:** The listener thread starts accepting connections before cleanup completes — a client sends RESERVE for a seat that's about to be released.
**Why it happens:** Cleanup runs in `start()` after `listen()` but before the listener thread starts.
**How to avoid:** Run cleanup BEFORE `self.listener_thread.start()`. The lock hierarchy already prevents concurrent access, but ordering avoids unnecessary lock contention.
**Warning signs:** Client RESERVE succeeds, then immediately the seat is released by cleanup.

### Pitfall 2: Forgetting to Release Semaphores During Cleanup
**What goes wrong:** Seats are marked AVAILABLE but the semaphore count stays decremented — over time, semaphore exhaustion blocks valid reservations.
**Why it happens:** SeatMatrix and SemaphoreManager are independent; cleanup must touch both.
**How to avoid:** For each stale reservation, count section seats released and call `semaphore_mgr.release_multiple()`.
**Warning signs:** Semaphore capacity decreases across server restarts without corresponding seat counts.

### Pitfall 3: Simultaneous ReservationTable Cleanup and Session Expiration
**What goes wrong:** SessionManager has no entries (they were ephemeral), but ReservationTable has stale entries from before sessions existed. Both need to be cleared.
**Why it happens:** Sessions are in-memory only (lost on crash), but ReservationTable may have persistent entries from pre-session code paths.
**How to avoid:** Clean up ReservationTable on startup. Sessions are already empty on fresh server start (no persistence). No coordination needed — they're independent data stores.

## Code Examples

### Fix expire_reservation (remove dead code)

```python
# Option A: Remove entirely — nothing calls it
# Delete expire_reservation() method from MonitorThread

# Option B: Replace with delegate to expire_session
def expire_reservation(self, tx_id):
    """Legacy wrapper — delegates to session-based expiry.
    
    DEPRECATED: No longer called from run(). SessionManager handles expiry.
    Kept as a safety wrapper in case external code references this method.
    """
    for session in self.server.session_manager._sessions.values():
        if session.session_id == tx_id:
            self.expire_session(session)
            return
    self.server.global_log.append(
        "EXPIRE", f"TX:{tx_id} not found in active sessions (already expired or confirmed)"
    )
```

### Startup Cleanup in ConcertServer

```python
def _cleanup_stale_reservations(self):
    """Release seats from stale ReservationTable entries on startup."""
    from src.utils.enums import SeatState
    
    stale_count = 0
    released_by_section = {}
    
    with self.reservation_table.mutex_table:
        expired_ids = list(self.reservation_table.reservations.keys())
        for tx_id in expired_ids:
            res = self.reservation_table.reservations.get(tx_id)
            if res and res.state in (ReservationStatus.ACTIVE,):
                # Determine section and seats
                seats = res.seats
                section = res.section
                
                if section not in released_by_section:
                    released_by_section[section] = 0
                
                for seat in seats:
                    if len(seat) == 3:
                        sec, row, col = seat
                    else:
                        row, col = seat
                        sec = section
                    
                    # Release seat if still RESERVED
                    if sec == section:
                        with self.seat_matrix.mutex_sections[section]:
                            if self.seat_matrix.seats[section][row][col] == SeatState.RESERVED:
                                self.seat_matrix.seats[section][row][col] = SeatState.AVAILABLE
                                released_by_section[section] += 1
                
                del self.reservation_table.reservations[tx_id]
                stale_count += 1
    
    for section, count in released_by_section.items():
        if count > 0:
            self.semaphore_mgr.release_multiple(section, count)
    
    if stale_count > 0:
        self.global_log.append("CLEANUP", f"Released {stale_count} stale reservation(s): {dict(released_by_section)}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `expire_reservation()` with dead code | `expire_session()` via SessionManager | Phase 1 (expire_session), Phase 2 (remove dead code) | Phase 2 eliminates dead code paths |
| No startup cleanup | `_cleanup_stale_reservations()` on boot | Phase 2 | Prevents permanently blocked seats after crash |

## Environment Availability

| Dependency | Required By | Available | Version |
|------------|------------|-----------|---------|
| Python 3.14+ | All code | ✓ | 3.14 |
| pytest | Testing | ✓ | ≥9.0.3 |
