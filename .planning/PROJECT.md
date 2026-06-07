# ConcertSync

## What This Is

ConcertSync is a TCP-based concurrent seat reservation system for a concert venue. A Python server manages seat state across three sections (VIP, PREFERENTIAL, GENERAL) using threading, lock hierarchies, and semaphores. The client frontend connects via JSON over TCP sockets on port 9999. The current frontend is a Textual terminal-based TUI being replaced with a PySide6 desktop GUI.

## Core Value

Multiple concurrent users can reserve, confirm, and cancel seats without race conditions — the seat matrix always reflects accurate availability, and no seat gets double-sold.

## Requirements

### Validated

- ✓ TCP server on port 9999 accepting concurrent client connections — existing
- ✓ JSON protocol (v1.0) with RESERVE, RESERVE_BATCH, CONFIRM, CANCEL, QUERY, QUERY_SEAT_MAP actions — existing
- ✓ Thread-per-connection model with lock hierarchy deadlock prevention — existing
- ✓ Tri-state response protocol (SUCCESS/FAILURE/ERROR) with deterministic error codes — existing
- ✓ Per-section capacity enforcement via semaphores — existing
- ✓ TTL-based reservation expiry via background monitor thread — existing
- ✓ File-backed thread-safe global event log — existing

### Active

- [ ] Replace Textual TUI frontend with PySide6 desktop GUI
- [ ] Visual distinction between user's own selected seats and seats selected by other users
- [ ] Fix reservation expiration mechanism (seats must reliably release on TTL expiry)
- [ ] Fix concurrent cancel-while-modify errors (cancel operations must be race-free)
- [ ] Session persistence across client close/reopen (reserved seats survive disconnect)
- [ ] Fix individual vs batch reservation confusion (both modes must work consistently)
- [ ] Clearer, more intuitive event log/bitácora for concurrent events

### Out of Scope

- Login/authentication system — not part of this phase
- Database persistence — system remains in-memory
- Real-time WebSocket push — stays polling-based
- Mobile/web client — desktop only (PySide6)

## Context

This project was built for a university concurrency course. The backend implements formal concurrency patterns: lock hierarchy ordering, atomic multi-lock transactions with rollback, semaphore-based capacity control, and thread-per-connection TCP server. The teacher's review (review-by-teacher.md) identified specific frontend and concurrency issues that need fixing: visual ambiguity in the seat map, unreliable TTL expiration, cancel-race errors, session loss on disconnect, and reservation mode confusion. The teacher scored the implementation at 60/100 ("Aceptable") and explicitly permitted replacing Textual with PySide6 as long as the backend remains stable.

## Constraints

- **Backend stability**: `src/server/`, `src/shared_resources/`, `src/synchronization/`, `src/utils/` must not change significantly — frontend replacement only
- **Protocol compatibility**: The PySide6 client must use the same JSON-over-TCP protocol as the Textual client
- **Tech stack**: Python 3.14, PySide6 (Qt for Python), uv package manager, Nix dev shell
- **Frontend scope**: Only `frontend_tui/` is replaced; a new `frontend_pyside6/` directory is created

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| PySide6 over Textual | Terminal TUI is buggy to debug; Qt provides proper widget toolkit for visual distinction, layouts, and event handling | — Pending |
| New frontend directory | Keep Textual frontend as reference; create `frontend_pyside6/` alongside it | — Pending |
| Backend stays | Teacher confirmed backend logic doesn't need to change; frontend swap is permitted | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-04 after initialization*
