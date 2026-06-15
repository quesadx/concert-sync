# Roadmap: ConcertSync

**Created:** 2026-06-04
**Granularity:** Coarse
**Mode:** MVP (Vertical Slices)

## Phase Map

| # | Phase | Goal | Requirements | Success Criteria |
|----|-------|------|--------------|------------------|
| 1 | PySide6 Frontend | 5/5 | Complete   | 2026-06-04 |
| 2 | Notifications & QR Tickets | 4/4 | Complete   | 2026-06-15 |

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

**Plans:** 5/5 plans complete

Plans:

- [x] 01-01-PLAN.md — PySide6 environment setup: install, config, directory skeleton, models
- [x] 01-02-PLAN.md — Backend surgical fixes: cancel idempotency, session reclaim, TTL expiration docs
- [x] 01-03-PLAN.md — GUI widgets & workers: seat map, section stats, connection panel, transaction panel, event log, network workers
- [x] 01-04-PLAN.md — MainWindow assembly & integration: layout, signal-slot wiring, polling, desktop launcher dual-frontend
- [x] 01-05-PLAN.md — Test suite: conftest, protocol tests, structure tests, widget tests, concurrency tests

**Canonical refs:**

- `review-by-teacher.md` — Teacher review identifying specific issues (Parte I) and rubric scoring (Parte II/III)
- `docs/protocol-contract-v1.md` — JSON protocol specification (if exists)

---

### Phase 2: Notifications & QR Tickets

**Goal:** Add real-time async notifications (TTL warning, confirm, expire, availability) and automatic QR ticket generation on purchase confirmation. Maintain thread safety and reutilize existing socket architecture.

**Mode:** standard

**Requirements:** NOTIF-01, NOTIF-02, NOTIF-03, NOTIF-04, NOTIF-05, NOTIF-06, NOTIF-07, TICKET-01, TICKET-02, TICKET-03, TICKET-04

**Success Criteria:**

1. Client receives push notification when its reservation is 30 seconds from expiry
2. Client receives push notification on successful CONFIRM
3. Client receives push notification when its reservation expires and seats are released
4. Client receives push notification when a previously full section has new availability
5. QR ticket PNG and TXT/PDF files are generated on every successful CONFIRM
6. Ticket QR is scannable by standard mobile camera apps
7. All notifications and ticket creations are logged in the system log
8. Zero races or deadlocks under concurrent load

**Plans:** 4/4 plans complete

Plans:

- [x] 02-01-PLAN.md — Notification infrastructure: NotificationManager, queue, subscription protocol
- [x] 02-02-PLAN.md — Notification hooks: TTL warnings, expiry, confirm, availability events
- [x] 02-03-PLAN.md — QR ticket generation module: QR code, ticket data, file output
- [x] 02-04-PLAN.md — Integration & tests: ticket hook in confirm, notification client, test suite

**Canonical refs:**

- `src/server/notification_manager.py` — New: async notification queue and subscriber management
- `src/utils/ticket_generator.py` — New: QR ticket generation with qrcode library
- `docs/protocol-contract-v1.md` — JSON protocol specification (SUBSCRIBE notification action)

---

*Roadmap created: 2026-06-04*
