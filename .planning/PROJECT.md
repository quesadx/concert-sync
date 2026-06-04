# ConcertSync

## What This Is

ConcertSync is a multi-threaded TCP server-client concert seat reservation system. Users connect via a Textual TUI client, select seats from a venue grid, and reserve/purchase them. The server manages shared in-memory state (seat matrix, reservation table, semaphores) protected by a lock hierarchy.

## Core Value

Multiple users can concurrently browse, select, and purchase concert seats without double-booking or losing reservations.

## Requirements

### Validated

- ✓ User can browse seat grid via TUI — existing
- ✓ User can select/deselect individual seats — existing
- ✓ User can reserve a seat via individual mode — existing
- ✓ User can reserve seats via block mode — existing
- ✓ Server manages concurrent clients via thread-per-connection — existing
- ✓ Seats have TTL-based automatic expiration — existing (buggy)
- ✓ Server broadcasts state changes to connected clients — existing
- ✓ Venue layout loaded from config — existing
- ✓ Reservation data persisted to file — existing

### Active

- [ ] **USR-01**: User identification mechanism (simple prompt, no auth system)
- [ ] **SES-01**: Session-based TTL (TTL per user session, not per seat)
- [ ] **EXP-01**: Fix dead code in TTL expiration (monitor_thread.py)
- [ ] **CLN-01**: Cleanup stale reservations on server restart
- [ ] **PCH-01**: Fix purchase near TTL expiration (race condition)
- [ ] **CNC-01**: Fix concurrent cancellation synchronization
- [ ] **UI-01**: Visual differentiation of own vs others' selected seats
- [ ] **CON-01**: Reservation consistency (individual vs block modes)
- [ ] **CLS-01**: Handle instance closure (cleanup or recovery)
- [ ] **SAT-01**: Early conflict detection in saturated zones
- [ ] **LOG-01**: Improved audit log clarity and concurrency traceability
- [ ] **CR-01**: Concurrency robustness review and fixes

### Out of Scope

- Full authentication system (login/password/OAuth) — simple user ID prompt sufficient
- Web/mobile frontend — TUI-only for this iteration
- Database backend — in-memory + file persistence is sufficient
- Horizontal scaling — single-server architecture
- Payment processing — purchase is logical only

## Context

ConcertSync is a university project for an Operating Systems course. It was graded based on functionality and concurrency correctness. Professor feedback identified 12 specific issues ranging from dead code in expiration logic to missing synchronization in cancellation. The existing system works in basic scenarios but shows weaknesses under concurrent load.

Codebase is Python 3.14+, uses raw `socket` library for TCP, `threading` for concurrency, Textual for TUI. No web framework. In-memory state with lock hierarchy.

## Constraints

- **No architectural redesign**: Professor explicitly stated unnecessary logic changes reduce grade
- **Minimal changes**: Each modification must be justified by specific feedback item
- **Preserve existing logic**: Structure, workflows, and behavior should change as little as possible
- **One phase at a time**: Must test and commit each phase before proceeding

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Phase 1: User ID + Session TTL | User ID is prerequisite for UI differentiation; session TTL is prerequisite for fixing expiration logic | — Pending |
| Simple string user ID (no auth) | Full auth is overkill; only need to distinguish users for session ownership | — Pending |
| Session TTL replaces per-seat TTL | Single timer per user session, reset on any seat selection change | — Pending |

---

*Last updated: 2026-06-01 after initialization*
