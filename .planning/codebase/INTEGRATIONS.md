# External Integrations

**Analysis Date:** 2026-06-01

## APIs & External Services

**Third-Party APIs:**
- None detected. The project uses no external REST, gRPC, or GraphQL APIs.

**SDK/Client Libraries:**
- None detected. No Stripe, Supabase, AWS, or other SDK dependencies.

## Data Storage

**Databases:**
- None. All state is stored in-memory via Python data structures:
  - `SeatMatrix` (`src/shared_resources/seat_matrix.py`) — Nested list of `SeatState` enums, protected by per-section `RLock`/`Lock`
  - `ReservationTable` (`src/shared_resources/reservation_table.py`) — In-memory dict of `Reservation` dataclass instances, protected by `threading.Lock`
  - `SemaphoreManager` (`src/shared_resources/semaphore_manager.py`) — Per-section `threading.Semaphore` for capacity control

**File Storage:**
- `GlobalLog` (`src/shared_resources/global_log.py`) — Writes timestamped log entries to `logs/system.log`
- No persistent data storage — all reservation state is ephemeral (lost on restart)

**Caching:**
- None. No Redis, Memcached, or in-memory cache layer.

## Authentication & Identity

**Auth Provider:**
- None. The TCP protocol has no authentication, tokens, or identity layer. Any client that can connect to the port can issue requests.

## Monitoring & Observability

**Error Tracking:**
- None. No Sentry, Datadog, or similar service.

**Logs:**
- File-based logging via `GlobalLog` to `logs/system.log`
- Log format: `[timestamp] [EVENT_TYPE] message`
- Event types: `SERVER`, `THREAD`, `ERROR`, `RESERVE`, `RESERVE_BATCH`, `CONFIRM`, `CANCEL`, `EXPIRE`

## CI/CD & Deployment

**Hosting:**
- Currently no production deployment target. Designed for local execution only.

**CI Pipeline:**
- None detected (no `.github/workflows/` directory, no CI config files).

## Environment Configuration

**Required env vars:**
- None. All configuration is hardcoded in `src/utils/config.py`:
  - `SERVER_PORT = 9999`
  - `RESERVATION_TTL = 300`
  - Per-section dimensions (VIP 5×10, PREFERENTIAL 10×15, GENERAL 20×20)

**Secrets location:**
- Not applicable — no secrets, API keys, or credentials exist in the codebase.

## Webhooks & Callbacks

**Incoming:**
- None. The server is a request-response TCP server with no webhook/callback mechanism.

**Outgoing:**
- None. The server does not call external endpoints.

## Protocol

**Transport:**
- JSON over TCP
  - Raw TCP sockets (`socket.AF_INET`, `socket.SOCK_STREAM`)
  - Default port: 9999
  - Frame format: Complete JSON object per send/receive (no delimiters)
  - UTF-8 encoding
- Protocol version: v1.0 (documented in `docs/protocol-contract-v1.md`)

**Protocol Actions:**
| Action | Description |
|--------|-------------|
| `RESERVE` | Reserve single seat, returns `transaction_id` with TTL |
| `RESERVE_BATCH` | Atomic multi-seat reservation (up to 10 seats) |
| `CONFIRM` | Convert reservation to permanent SOLD state |
| `CANCEL` | Release reservation, revert seats to AVAILABLE |
| `QUERY` | Fetch seat availability counts by section |
| `QUERY_SEAT_MAP` | Fetch full seat-state matrix |

**Error Codes:**
| Code | HTTP-like Semantics | Trigger |
|------|-------------------|---------|
| `ERR_INVALID_PAYLOAD` | 400 | Missing fields or unparseable JSON |
| `ERR_INVALID_SECTION` | 400 | Section not in enum |
| `ERR_INVALID_COORDINATES` | 400 | row/col not int or negative |
| `ERR_SEAT_OUT_OF_BOUNDS` | 400 | row/col exceeds section bounds |
| `ERR_INVALID_ACTION` | 400 | Unknown action |
| `ERR_SEAT_NOT_AVAILABLE` | 409 | Seat not AVAILABLE |
| `ERR_NO_CAPACITY` | 409 | No semaphore slots in section |
| `ERR_TRANSACTION_NOT_FOUND` | 404 | tx_id not in table |
| `ERR_TRANSACTION_NOT_ACTIVE` | 409 | tx_id not ACTIVE state |
| `INTERNAL_ERROR` | 500 | Unexpected exception |

## Concurrency Architecture

**Synchronization primitives (all stdlib `threading`):**
- `threading.Lock` — Reservation table, section mutexes, log mutex
- `threading.RLock` — Per-section reentrant lock for seat matrix reads
- `threading.Semaphore` — Per-section capacity gates
- `threading.Condition` — Reservation table condition variable (for monitor thread notification)
- `threading.Thread` — Listener, monitor, and transactional worker threads
- `threading.Barrier` — Used only in race condition tests

**Thread model:**
- 1 listener thread (accepts TCP connections, spawns transactional threads)
- 1 monitor thread (daemon, polls expired reservations every second)
- N transactional threads (one per client connection, short-lived)

---

*Integration audit: 2026-06-01*
