# Roadmap: ConcertSync

**Created:** 2026-06-04
**Granularity:** Coarse
**Mode:** MVP (Vertical Slices)

## Phase Map

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | PySide6 Frontend | Replace Textual TUI with PySide6 GUI, fix all teacher-flagged issues | FRNT-01..03, VIS-01..02, EXPR-01..02, CANC-01, SESS-01..02, RSRV-01, LOG-01..02 | 5 |

**Coverage:** 13/13 requirements mapped ✓

---

### Phase 1: PySide6 Frontend

**Goal:** Replace the Textual terminal TUI with a PySide6 desktop GUI that fixes all teacher-identified issues — visual seat distinction, TTL expiration, cancel races, session persistence, reservation consistency, and a clearer event log.

**Mode:** mvp

**Requirements:** FRNT-01, FRNT-02, FRNT-03, VIS-01, VIS-02, EXPR-01, EXPR-02, CANC-01, SESS-01, SESS-02, RSRV-01, LOG-01, LOG-02

**Success Criteria:**
1. PySide6 app connects to ConcertServer on port 9999 and performs all protocol actions (RESERVE, RESERVE_BATCH, CONFIRM, CANCEL, QUERY, QUERY_SEAT_MAP)
2. Seat map visually distinguishes three seat states: available, reserved-by-current-user, reserved-by-other-user, sold
3. Reservation TTL expiration releases seats within 1 second of expiry under concurrent load (passes Prueba 3)
4. User disconnecting and reconnecting with their session ID reclaims reserved seats (passes Prueba 8)
5. Individual and batch reservation modes produce consistent results — all selected seats reserved regardless of confirmation mode

**Plans:** 5 plans in 4 waves

Plans:
- [ ] 01-01-PLAN.md — PySide6 environment setup: install, config, directory skeleton, models
- [ ] 01-02-PLAN.md — Backend surgical fixes: cancel idempotency, session reclaim, TTL expiration docs
- [ ] 01-03-PLAN.md — GUI widgets & workers: seat map, section stats, connection panel, transaction panel, event log, network workers
- [ ] 01-04-PLAN.md — MainWindow assembly & integration: layout, signal-slot wiring, polling, desktop launcher dual-frontend
- [ ] 01-05-PLAN.md — Test suite: conftest, protocol tests, structure tests, widget tests, concurrency tests

**Canonical refs:**
- `review-by-teacher.md` — Teacher review identifying specific issues (Parte I) and rubric scoring (Parte II/III)
- `docs/protocol-contract-v1.md` — JSON protocol specification (if exists)

---

*Roadmap created: 2026-06-04*
