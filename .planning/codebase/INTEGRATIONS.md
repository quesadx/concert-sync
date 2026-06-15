# External Integrations

**Analysis Date:** 2026-06-04

## APIs & External Services

**None.** The ConcertSync system is fully self-contained. It communicates exclusively over raw TCP sockets using a custom JSON protocol (defined in `docs/protocol-contract-v1.md`). No third-party APIs, SaaS services, or external HTTP endpoints are used.

The system consists of:
- **Server:** `src/server/concert_server.py` — Binds to `localhost:9999` (configurable), accepts TCP connections, spawns `TransactionalThread` per client
- **Client:** `src/client/concert_client.py` — Opens TCP socket to server, sends/receives JSON
- **Protocol:** JSON over TCP, with actions: `RESERVE`, `RESERVE_BATCH`, `RESERVE_SELECTED`, `CONFIRM`, `CANCEL`, `QUERY`, `QUERY_SEAT_MAP`

## Data Storage

**Databases:**
- None. All state is in-memory using Python data structures:
  - `SeatMatrix` (`src/shared_resources/seat_matrix.py`) — 2D lists per section with `SeatState` enums
  - `ReservationTable` (`src/shared_resources/reservation_table.py`) — `dict` mapping transaction IDs to `Reservation` dataclasses
  - `SessionManager` (`src/server/session_manager.py`) — `dict` mapping user IDs to `UserSession` dataclasses
  - `SemaphoreManager` (`src/shared_resources/semaphore_manager.py`) — `threading.Semaphore` per section
  - `GlobalLog` (`src/shared_resources/global_log.py`) — Appends to `logs/system.log` on disk

**Data persistence:**
- The `GlobalLog` writes to `logs/system.log` (text file, append-only). This is the only on-disk data.
- No database, ORM, or persistent storage layer exists. Server restart loses all reservations.

**File Storage:**
- Local filesystem only. Logs at `logs/system.log`, TUI CSS at `frontend_tui/styles.tcss`.

**Caching:**
- None. All state queries (QUERY, QUERY_SEAT_MAP) read directly from in-memory data structures under appropriate locks.

## Authentication & Identity

**Auth Provider:**
- Custom. No authentication provider or token system.
- Identity is a simple `user_id` string provided by the client at connection time.
- The TUI frontend prompts for a display name (`frontend_tui/login_screen.py`) and uses it as `user_id`.
- Ownership checks in `TransactionalThread` (`src/server/transactional_thread.py`) compare `user_id` from request against session's `user_id` — purely string comparison.
- No passwords, tokens, sessions (HTTP-style), or encryption.

## Monitoring & Observability

**Error Tracking:**
- None. No Sentry, Datadog, or external error tracking service.

**Logs:**
- File-based logging via `GlobalLog` (`src/shared_resources/global_log.py`)
  - Output: `logs/system.log` (configured at init, path overridable)
  - Format: `[ISO timestamp] [EVENT_TYPE] [TID:thread_id] message`
  - Thread-safe via `threading.Lock`
  - Event types logged: `SERVER`, `THREAD`, `ERROR`, `RESERVE`, `RESERVE_BATCH`, `RESERVE_SELECTED`, `CONFIRM`, `CANCEL`, `EXPIRE`, `CLEANUP`, `SHUTDOWN`
- The TUI frontend tails this log file for a live event stream (`LogTailer` in `frontend_tui/app.py`)

**Metrics:**
- In-TUI only: sparkline charts for request/thread/error counts per tick (`frontend_tui/app.py` `_render_metrics_panels`)

## CI/CD & Deployment

**Hosting:**
- Local execution only. No cloud deployment or containerization detected (no Dockerfile, no Docker Compose, no Kubernetes manifests).

**CI Pipeline:**
- No CI pipeline detected. No GitHub Actions workflows, no CI config files in `.github/`.

**Deployment scripts:**
- `scripts/run.sh` — Multi-mode launcher: `server`, `tui`, `both`, `test`
- `scripts/build_windows_exe.ps1` — Windows executable packaging
- `desktop_launcher.py` — Single-process launcher embedding server + TUI
- `main.py` — Server-only entry point

## Environment Configuration

**Required env vars:**
- None. The application requires no environment variables.

**Configuration in code:**
- Server port: `src/utils/config.py` (`SERVER_PORT = 9999`)
- Reservation TTL: `src/utils/config.py` (`RESERVATION_TTL = 300`)
- Section dimensions: `src/utils/config.py` (`SECTION_CONFIG`)

**Secrets location:**
- No secrets. The application has no authentication, API keys, or credentials.

## Webhooks & Callbacks

**Incoming:**
- None. TCP server listens for client connections but does not expose any webhook endpoints.

**Outgoing:**
- None. The server does not make outbound HTTP requests or call external webhooks.

---

*Integration audit: 2026-06-04*
