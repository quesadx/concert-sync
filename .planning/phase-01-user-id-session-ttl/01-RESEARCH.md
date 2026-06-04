# Phase 1: User ID + Session-Based TTL — Research

**Researched:** 2026-06-01
**Domain:** User identification, session management, TTL ownership migration
**Confidence:** HIGH

## Summary

ConcertSync currently has no user identification and uses per-seat TTL (each `RESERVE` creates an independent `Reservation` with its own 300s timer). Phase 1 must introduce **user identity through the protocol** and **migrate TTL ownership from individual reservations to user sessions** — a single TTL per user that resets on any new seat selection and expires all user-held seats atomically.

**Key insight:** The session concept replaces independent per-seat reservations with one `UserSession` per user. The session holds ALL seats the user has selected, owns the single TTL timer, and its ID serves as the `transaction_id` for CONFIRM/CANCEL — preserving backward compatibility with the existing protocol flow.

**Primary recommendation:** Add a `SessionManager` in `ConcertServer` + `user_id` field to the protocol. `ReservationTable` continues to work internally but sessions become the unit of TTL management. The `MonitorThread` expires sessions instead of individual reservations.

### Why not keep per-seat TTL under sessions?
Per-seat TTL means if a user has 3 seats selected, each expires independently. User loses seat A after 300s, seat B after 180s (selected later), etc. SES-03 explicitly requires "all selected seats share the same expiration timer" — only a session-level TTL achieves this.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for Phase 1. All constraints come from PROJECT.md, REQUIREMENTS.md, ROADMAP.md, and explicit scope boundaries.

### Locked Decisions (from PROJECT.md)
- Simple string user ID (no auth system — full auth is overkill)
- Session TTL replaces per-seat TTL (single timer per user, reset on any seat selection change)
- No architectural redesign — minimal changes justified by specific requirements
- One phase at a time — test and commit before proceeding

### the agent's Discretion
- Implementation details (SessionManager class design, protocol field naming, TUI prompt UX)
- Whether to modify ReservationTable or create separate SessionManager module
- Whether MonitorThread gets new `expire_session` method or modified `expire_reservation`

### Deferred Ideas (OUT OF SCOPE for Phase 1)
- Fixing dead code bug in monitor_thread.py (EXP-01 — Phase 2)
- Full authentication/password system (explicitly OOS per REQUIREMENTS.md)
- Changing architectural approach (thread-per-connection, lock hierarchy, etc.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| USR-01 | User prompted for display name on startup (no auth) | TUI Prompt: Textural `Screen` + `Input` dialog on mount; ConcertClient stores `user_id` |
| USR-02 | User ID sent with all requests to identify session ownership | Protocol: Add `user_id` field to every request; ConcertClient.send_request() injects it; server extracts before dispatch |
| SES-01 | Each user has exactly one selection session with a single TTL timer | SessionManager: Dict[user_id → UserSession]. RESERVE looks up existing session before creating new one |
| SES-02 | TTL reset whenever user selects a new seat | On RESERVE/RESERVE_BATCH: session.last_activity = time.time(), session.ttl_secs = RESERVATION_TTL |
| SES-03 | All selected seats in session share the same expiration timer | Session-level TTL: get_expired_sessions() checks session.last_activity + session.ttl_secs, not per-seat timestamps |
| SES-04 | Expired session releases all selected seats atomically | MonitorThread.expire_session() acquires table lock + ALL section locks, marks all seats AVAILABLE, releases semaphores |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| User ID collection | Browser/Client (TUI) | — | TUI prompts on startup before any server interaction |
| User ID transmission | Client layer | — | ConcertClient injects user_id into every request payload |
| Session orchestration | Server/TransactionalThread | — | handle_reserve()/handle_confirm() manage session lifecycle |
| Session registry | Server/ConcertServer | — | SessionManager lives in ConcertServer, passed to threads by reference |
| TTL expiry scan | Server/MonitorThread | — | Daemon thread polls sessions for expiry, releases seats |
| Seat release on expiry | Shared Resources | Server/MonitorThread | Session seat list iterated, SeatMatrix.markAvailable(), SemaphoreManager.release() |
| Protocol validation | Utilities | — | protocol_validator checks user_id presence/type in all requests |

## Standard Stack

### Core
| Component | Purpose | Why Standard |
|-----------|---------|--------------|
| `SessionManager` (new) | Registry of active sessions, thread-safe CRUD | Centralizes session lifecycle — single source of truth for "which user holds which seats" |
| `UserSession` (new dataclass) | In-memory session record per user | Lightweight, no DB needed — follows existing `Reservation` dataclass pattern |
| `ConcertServer.sessions` | Dict keyed by user_id | Passed to child threads via `self.server` reference (existing pattern) |

### Supporting
| Module | Purpose | When to Use |
|--------|---------|-------------|
| `protocol_validator.py` | Validate `user_id` in all requests | Extend `validate_request()` and each payload validator |
| `concert_client.py` | Inject `user_id` into all outbound requests | Store `self.user_id`, add to `send_request()` |
| `ConcertTextualApp` | User ID prompt on startup | New screen/modal on `on_mount()` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Separate SessionManager class | Inline session dict in ConcertServer | SessionManager encapsulates locking — cleaner separation |
| user_id in every request payload | Tuple-based protocol (user_id in TCP header) | Minimal protocol change. Adding to JSON payload is simpler, preserves single-JSON format |
| Textual Screen for prompt | App-level Input widget | Screen is cleaner UX (blocks until user responds) |

## Package Legitimacy Audit

> **No external packages required for Phase 1.** All changes are within the existing Python stdlib + Textual stack. No new `pip install` dependencies.

| Package | Registry | Verdict | Notes |
|---------|----------|---------|-------|
| (none) | — | — | All features use existing dependencies |

## Architecture Patterns

### System Architecture Diagram

```text
┌──────────────────────────────────────────────────────────────┐
│                     Textual TUI (frontend_tui/app.py)          │
│                                                                 │
│  ┌────────────┐    ┌─────────────────────────────────────┐    │
│  │ User ID    │───▶│ ConcertClient(user_id="Alice")       │    │
│  │ Prompt     │    │ send_request({"user_id":"Alice",     │    │
│  │ (Screen)   │    │              "action":"RESERVE",...}) │    │
│  └────────────┘    └──────────────┬──────────────────────┘    │
│                                   │ JSON-over-TCP               │
└───────────────────────────────────┼──────────────────────────┘
                                    │
┌───────────────────────────────────┼──────────────────────────┐
│  Server Layer                     ▼                           │
│  ┌──────────────────────────────────────────────┐            │
│  │ TransactionalThread                           │            │
│  │  extracts user_id → session_mgr.get_or_create │            │
│  │  → adds seat to session → resets TTL          │            │
│  └──────────────────────┬───────────────────────┘            │
│                         │                                     │
│  ┌──────────────────────▼───────────────────────┐            │
│  │ ConcertServer                                 │            │
│  │  ┌──────────────────────────────────────┐    │            │
│  │  │ SessionManager                        │    │            │
│  │  │  sessions: Dict[str, UserSession]     │    │            │
│  │  │  lock: threading.Lock                 │    │            │
│  │  │  get_or_create(user_id) → session     │    │            │
│  │  │  add_seat(session, seat)              │    │            │
│  │  │  get_expired_sessions() → list        │    │            │
│  │  └──────────────────────────────────────┘    │            │
│  └──────────────────────┬───────────────────────┘            │
│                         │                                     │
│  ┌──────────────────────▼───────────────────────┐            │
│  │ MonitorThread                                 │            │
│  │  run():                                       │            │
│  │    expired = sessions.get_expired()           │            │
│  │    for session: expire_session(session)       │            │
│  │      → acquires table + section locks         │            │
│  │      → marks seats AVAILABLE                  │            │
│  │      → releases semaphores                    │            │
│  │      → removes session                        │            │
│  └──────────────────────────────────────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

### Flow: RESERVE with Session TTL

```text
Client                          Server
  │   RESERVE(user_id, seat)      │
  │──────────────────────────────▶│
  │                               │ 1. Extract user_id, validate payload
  │                               │ 2. Acquire table lock
  │                               │ 3. session = session_mgr.get_or_create(user_id)
  │                               │    └─ if new: create UserSession, generate session_id
  │                               │    └─ if existing: use current session
  │                               │ 4. Validate seat AVAILABLE
  │                               │ 5. Add seat to session.seats list
  │                               │ 6. Reset session.last_activity = now()
  │                               │    (effectively resets TTL — SES-02)
  │                               │ 7. Mark seat RESERVED in SeatMatrix
  │                               │ 8. Acquire semaphore
  │                               │ 9. Release lock
  │  {status:SUCCESS,             │
  │   session_id, ttl=300}        │
  │◀──────────────────────────────│
  │                               │
  │   RESERVE(user_id, seat2)     │  ← Same session, TTL RESETS
  │──────────────────────────────▶│
  │                               │ 1. session = session_mgr.get_or_create(user_id)
  │                               │    └─ finds existing session
  │                               │ 2. Add seat2, reset last_activity
  │                               │ 3. Both seat and seat2 share this TTL
  │  {same session_id, ttl=300}   │
  │◀──────────────────────────────│
```

### Flow: CONFIRM entire session

```text
Client                          Server
  │   CONFIRM(user_id, session_id) │
  │──────────────────────────────▶│
  │                               │ 1. session = session_mgr.get(session_id)
  │                               │ 2. Verify session.user_id matches request.user_id
  │                               │ 3. Acquire table + ALL relevant section locks
  │                               │ 4. Mark all session.seats as SOLD
  │                               │ 5. Remove session
  │  {status:SUCCESS}             │
  │◀──────────────────────────────│
```

### Flow: Session Expiration

```text
MonitorThread (every 1s)
  │  expired = session_mgr.get_expired_sessions()
  │    └─ checks: now - session.last_activity > session.ttl_secs
  │
  │  for each expired session:
  │    expire_session(session):
  │      1. Acquires table lock
  │      2. Acquires ALL section locks (in order)
  │      3. For each seat in session.seats:
  │           seat_matrix.seats[section][row][col] = AVAILABLE
  │           semaphore_mgr.release(section)
  │      4. Remove session from registry
  │      5. Log EXPIRE event
```

### Recommended Project Structure

No new files need to be created — the session management can be implemented within existing files. However, for clean separation, a new module is recommended:

```
src/
└── server/
    ├── concert_server.py         # Add session_manager instance
    ├── transactional_thread.py   # Session-aware handlers
    ├── monitor_thread.py         # Session expiry (not reservation expiry)
    └── session_manager.py        # NEW: UserSession class + SessionManager
```

### Pattern 1: Session as TTL-owning Container

**What:** A `UserSession` dataclass holds all seats a user has selected, owns the single TTL, and its ID doubles as the transaction_id for confirm/cancel.

```python
@dataclass
class UserSession:
    user_id: str
    session_id: str          # UUID, serves as transaction_id for CONFIRM/CANCEL
    seats: list              # List of (Section, row, col) tuples
    last_activity: float     # time.time() — TTL measured from here
    ttl_secs: int            # RESERVATION_TTL (300)
    state: ReservationStatus # ACTIVE, CONFIRMED, CANCELLED, EXPIRED
    
    @property
    def is_expired(self) -> bool:
        return time.time() - self.last_activity > self.ttl_secs
```

**When to use:** Every RESERVE/RESERVE_BATCH operation must use this pattern. The server never creates a new Reservation per seat — it adds to the session.

### Pattern 2: SessionManager with Single Lock

**What:** A thread-safe registry that manages session CRUD. Single `threading.Lock` protects the sessions dict — sessions are accessed from TransactionalThread and MonitorThread concurrently.

```python
class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, UserSession] = {}
        self._lock = threading.Lock()
    
    def get_or_create(self, user_id: str) -> UserSession:
        with self._lock:
            if user_id in self._sessions:
                return self._sessions[user_id]
            session = UserSession(
                user_id=user_id,
                session_id=str(uuid.uuid4()),
                seats=[],
                last_activity=time.time(),
                ttl_secs=RESERVATION_TTL,
                state=ReservationStatus.ACTIVE,
            )
            self._sessions[user_id] = session
            return session
    
    def get_by_session_id(self, session_id: str) -> Optional[UserSession]:
        with self._lock:
            for session in self._sessions.values():
                if session.session_id == session_id:
                    return session
            return None
    
    def get_expired(self) -> List[UserSession]:
        with self._lock:
            now = time.time()
            return [
                s for s in self._sessions.values()
                if s.state == ReservationStatus.ACTIVE and s.is_expired
            ]
    
    def remove(self, user_id: str) -> Optional[UserSession]:
        with self._lock:
            return self._sessions.pop(user_id, None)
```

**When to use:** Any code that needs to look up or modify a user's session.

### Pattern 3: User ID Injection at Client Layer

**What:** `ConcertClient` stores `user_id` once and injects it into every `send_request()` JSON payload, transparent to all callers.

```python
class ConcertClient:
    def __init__(self, user_id: str, host='localhost', port=9999):
        self.user_id = user_id
        self.host = host
        self.port = port
    
    def send_request(self, request):
        # Inject user_id into every request
        request["user_id"] = self.user_id
        # ... rest of existing send_request logic
```

**When to use:** Every client-side operation automatically includes user_id without each caller needing to add it.

### Pattern 4: TUI Login Screen

**What:** A Textual `Screen` subclass that blocks until the user enters a display name. Overrides the default `ConcertTextualApp` `on_mount` flow.

```python
from textual.screen import Screen
from textual.widgets import Input, Button, Label

class LoginScreen(Screen):
    def compose(self):
        yield Label("Enter your display name:")
        yield Input(placeholder="e.g., Alice", id="name-input")
        yield Button("Join", id="join-btn")
    
    def on_button_pressed(self, event):
        name = self.query_one("#name-input").value.strip()
        if name:
            self.dismiss(name)  # Returns name to app
```

**When to use:** App startup — push this screen before any connection is established.

### Anti-Patterns to Avoid

- **Session per connection vs per user:** A user might reconnect (TCP disconnect + reconnect). The session should persist in the server's `SessionManager`, not be tied to the TCP socket. Session cleanup happens via TTL expiry, not client disconnect.
- **Creating a new session on every RESERVE:** Must check for existing session first. If `get_or_create` always creates, the user gets multiple sessions defeating SES-01.
- **Resetting TTL on deselect/deseat:** SES-02 says "reset whenever user selects a new seat" — it does NOT say anything about deselecting. TTL should NOT reset on deselect (that would allow indefinite extension by toggling).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread-safe session dict | Custom lock class | `threading.Lock` + session dict (existing pattern) | Simple critical section is sufficient — no reader-writer optimization needed |
| UUID generation | Custom ID scheme | `uuid.uuid4()` (existing pattern) | Already used for transaction IDs — consistent |
| TTL timer | Custom scheduling | Polling loop with `time.time()` comparison (existing pattern) | Already implemented in MonitorThread — just change what it polls |

**Key insight:** This phase introduces NO new technology or libraries. Every mechanism already exists in the codebase (JSON-over-TCP, threading.Lock, time-based expiry, dataclasses). The change is purely about *reorganizing ownership* of TTL from per-seat to per-session.

## Common Pitfalls

### Pitfall 1: Session Race Condition on Concurrent RESERVE
**What goes wrong:** Two threads simultaneously call `get_or_create` for the same `user_id` — if the check-and-create is not atomic, two sessions are created for one user.
**Why it happens:** The `user_id not in self.sessions` check and `self.sessions[user_id] = new_session` assignment are not a single atomic operation without a lock.
**How to avoid:** Always protect `get_or_create` with the SessionManager lock. Use `with self._lock:` around the entire check-or-create block.
**Warning signs:** A user appears to have multiple active sessions in logs.

### Pitfall 2: CONFIRM/CANCEL Without Verifying Session Ownership
**What goes wrong:** User A can confirm/cancel User B's session by guessing their session_id.
**Why it happens:** The server currently accepts any transaction_id from any client. With sessions, it must verify `session.user_id == request.user_id`.
**How to avoid:** In handle_confirm/handle_cancel, after looking up the session, verify the requesting user_id matches. Return `failure_transaction_not_found` if mismatch (don't reveal who owns the session).
**Warning signs:** A user confirms someone else's seats.

### Pitfall 3: MonitorThread Expiring Session While handle_confirm Is Running
**What goes wrong:** A session expires, MonitorThread starts releasing its seats, but simultaneously handle_confirm enters with the same tx_id/session_id.
**Why it happens:** No cross-coordination between MonitorThread and TransactionalThread beyond the lock hierarchy.
**How to avoid:** Two options:
1. MonitorThread can check-and-delete session atomically: `with session_lock: if session.state != CONFIRMED: expire_and_delete()`
2. The confirm handler can check session state under the table lock before proceeding.
   Since both threads must acquire the table lock, the ordering guarantees atomicity: the one holding the table lock sees a consistent state.

### Pitfall 4: Forgetting to Reset Session TTL After Batch Reserve
**What goes wrong:** A batch reserve adds multiple seats to a session but only the first seat addition resets the TTL.
**Why it happens:** The TTL reset should happen once per RESERVE/RESERVE_BATCH operation, not once per seat.
**How to avoid:** Reset `session.last_activity = time.time()` as part of the handler, after all seats are added, not inside the individual seat loop.
**Warning signs:** Batch reserves expire faster than single reserves.

### Pitfall 5: Protocol Validation Rejects Valid user_id
**What goes wrong:** The validator for RESERVE returns `INVALID_PAYLOAD` because `user_id` is not a recognized field.
**Why it happens:** The existing `validate_reserve_payload()` checks only `section`, `row`, `col` — any extra field is silently accepted (the validator doesn't reject extras). But if we add `user_id` validation that's too strict, valid requests might be rejected.
**How to avoid:** Add `user_id` as an optional-but-recommended field at the `validate_request()` level (check action-level payload in each handler, not in the protocol validator). Or add it to all payload validators consistently. The safer approach: validate `user_id` presence at the request level (after action validation) in `validate_request()`.

## Code Examples

### Session Manager Implementation

```python
# src/server/session_manager.py
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.utils.config import RESERVATION_TTL
from src.utils.enums import ReservationStatus, Section


@dataclass
class UserSession:
    user_id: str
    session_id: str
    seats: List[Tuple[Section, int, int]] = field(default_factory=list)
    last_activity: float = field(default_factory=time.time)
    ttl_secs: int = RESERVATION_TTL
    state: ReservationStatus = ReservationStatus.ACTIVE

    @property
    def is_expired(self) -> bool:
        if self.state != ReservationStatus.ACTIVE:
            return False
        return time.time() - self.last_activity > self.ttl_secs

    def reset_ttl(self) -> None:
        self.last_activity = time.time()


class SessionManager:
    """
    Thread-safe registry of user sessions.
    
    One session per user_id. Sessions own the TTL timer and hold all
    seats the user has selected.
    """
    def __init__(self):
        self._sessions: Dict[str, UserSession] = {}
        self._lock = threading.Lock()

    def get_or_create(self, user_id: str) -> UserSession:
        """Return existing session for user_id, or create a new one."""
        with self._lock:
            if user_id in self._sessions:
                return self._sessions[user_id]
            session = UserSession(
                user_id=user_id,
                session_id=str(uuid.uuid4()),
            )
            self._sessions[user_id] = session
            return session

    def get_by_session_id(self, session_id: str) -> Optional[UserSession]:
        """Find session by its session_id (for CONFIRM/CANCEL by tx_id)."""
        with self._lock:
            for session in self._sessions.values():
                if session.session_id == session_id:
                    return session
            return None

    def get_expired(self) -> List[UserSession]:
        """Return all expired ACTIVE sessions."""
        with self._lock:
            now = time.time()
            return [
                s for s in self._sessions.values()
                if s.state == ReservationStatus.ACTIVE and s.is_expired
            ]

    def remove(self, user_id: str) -> Optional[UserSession]:
        """Remove and return a session by user_id."""
        with self._lock:
            return self._sessions.pop(user_id, None)
```

### Protocol Validator — user_id Check

```python
# In validate_request(), after action validation, add:
def validate_request(data):
    # ...existing JSON parse and action validation...
    
    # Step 3: Validate user_id presence (all requests except maybe QUERY)
    if "user_id" not in parsed:
        return False, "Missing required field: user_id", None
    
    user_id = parsed["user_id"]
    if not isinstance(user_id, str) or not user_id.strip():
        return False, "Field 'user_id' must be a non-empty string", None
    
    # Step 4: Validate action-specific payload (existing)
    ...
```

### ConcertClient — user_id Injection

```python
class ConcertClient:
    def __init__(self, user_id: str, host='localhost', port=9999):
        self.user_id = user_id
        self.host = host
        self.port = port
    
    def send_request(self, request):
        # Inject user_id into every outbound request
        request["user_id"] = self.user_id
        # ... rest of existing send_request ...
```

### TUI Login Screen

```python
# frontend_tui/login_screen.py
from textual.screen import Screen
from textual.widgets import Input, Button, Label, Header, Footer
from textual.app import ComposeResult


class LoginScreen(Screen):
    """Screen shown on startup to collect user display name."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label("Welcome to ConcertSync", id="welcome-label")
        yield Label("Enter your display name to join:")
        yield Input(placeholder="e.g., Alice", id="name-input")
        yield Button("Join", id="join-btn", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._submit_name()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "name-input":
            self._submit_name()

    def _submit_name(self) -> None:
        name = self.query_one("#name-input", Input).value.strip()
        if name:
            self.dismiss(name)
        else:
            self.query_one("#welcome-label", Label).update(
                "Name cannot be empty! Enter your display name:"
            )
```

In `app.py`, the `on_mount()` would push this screen:

```python
def on_mount(self) -> None:
    self.push_screen(LoginScreen(), self._on_login)
    
def _on_login(self, user_id: str) -> None:
    self.user_id = user_id
    self.client = ConcertClient(user_id=user_id, host=..., port=...)
    self.title = f"ConcertSync — {user_id}"
    # ...rest of existing on_mount setup...
```

### TransactionalThread — Session-Aware RESERVE

```python
def handle_reserve(self, request):
    # Validate payload
    is_valid, error_msg = validate_reserve_payload(request)
    if not is_valid:
        return build_error_response(ErrorCode.INVALID_PAYLOAD, error_msg)

    try:
        user_id = request["user_id"]
        section_str = request["section"]
        row = int(request["row"])
        col = int(request["col"])
        section = Section[section_str]
        
        # Get or create session for user (SES-01)
        session = self.server.session_manager.get_or_create(user_id)
        
        with self.server.mutex_manager.table_and_sections([section]):
            seats = self.server.seat_matrix.seats[section]
            
            if seats[row][col] != SeatState.AVAILABLE:
                return failure_seat_not_available(...)
            
            # Check if seat already in user's session
            seat_tuple = (section, row, col)
            if seat_tuple in session.seats:
                return build_failure_response(...)
            
            seats[row][col] = SeatState.RESERVED
            
            semaphore_acquired = self.server.semaphore_mgr.acquire(section, blocking=False)
            if not semaphore_acquired:
                seats[row][col] = SeatState.AVAILABLE
                return failure_no_capacity(section_str)
            
            # Add seat to session (SES-03) and reset TTL (SES-02)
            session.seats.append(seat_tuple)
            session.reset_ttl()
        
        return build_success_response(
            transaction_id=session.session_id,
            ttl=RESERVATION_TTL,
        )
    except Exception as e:
        # ...rollback...
```

### MonitorThread — Session Expiry

```python
def run(self):
    while self.server.running:
        time.sleep(1)
        expired = self.server.session_manager.get_expired()
        for session in expired:
            self.expire_session(session)

def expire_session(self, session: UserSession):
    """
    Expire an entire session — release all seats atomically.
    
    Note: This is NEW code for Phase 1. The old expire_reservation
    (with dead code bug) remains untouched for Phase 2 to fix.
    """
    released_counts = {}
    
    # Group seats by section for lock acquisition order
    seats_by_section = {}
    for section, row, col in session.seats:
        seats_by_section.setdefault(section, []).append((row, col))
    
    ordered = [s for s in Section if s in seats_by_section]
    
    with self.server.mutex_manager.table_and_sections(ordered):
        # Verify session still active (could have been confirmed concurrently)
        current = self.server.session_manager.get_by_session_id(session.session_id)
        if not current or current.state != ReservationStatus.ACTIVE:
            return
        
        # Mark all seats AVAILABLE
        for section, seat_list in seats_by_section.items():
            released_counts[section] = 0
            for row, col in seat_list:
                if self.server.seat_matrix.seats[section][row][col] == SeatState.RESERVED:
                    self.server.seat_matrix.seats[section][row][col] = SeatState.AVAILABLE
                    released_counts[section] += 1
        
        # Remove session from registry
        self.server.session_manager.remove(session.user_id)
    
    # Release semaphores (outside lock — safe, semaphore is atomic)
    for section, count in released_counts.items():
        if count > 0:
            self.server.semaphore_mgr.release_multiple(section, count)
    
    self.server.global_log.append(
        "EXPIRE",
        f"Session:{session.session_id} User:{session.user_id} "
        f"seats_released:{sum(released_counts.values())}"
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-seat TTL (each Reservation has independent timer) | Per-session TTL (one timer per user, shared across all seats) | Phase 1 | TTL ownership shifts from Reservation dataclass to UserSession. All seats in a session expire together. |
| No user identification (anonymous TCP connections) | User ID in every request | Phase 1 | Client prompts on startup. Server validates user_id. Prepares for visual differentiation (Phase 4). |
| ReservationTable stores individual seat transactions | SessionManager stores sessions; each session holds multiple seats | Phase 1 | ReservationTable still used for CONFIRM/CANCEL lookups by session_id, but TTL expiry is driven by sessions, not reservations. |

**Deprecated/outdated:**
- `MonitorThread.expire_reservation()` with dead code bug — deprecated by Phase 1's `expire_session()`. Phase 2 will fix/remove the old method. For now it remains but is no longer called in the `run()` loop.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The TUI LoginScreen pattern (Screen subclass with dismiss) is the standard Textual way to prompt for input before the main app | Code Examples | Low — alternative is an Input in the compose tree; both work, Screen is cleaner |
| A2 | Adding `user_id` to all existing protocol validators won't break existing tests because tests can provide a dummy user_id | Standard Stack | Medium — existing tests that call validate_request directly with no user_id will fail. Tests that spin up a full server+client will also fail. All tests need updating. |
| A3 | SessionManager can be a new standalone module without disrupting existing ReservationTable | Architecture Patterns | Low — ReservationTable continues working for CONFIRM/CANCEL lookups; SessionManager is additive |
| A4 | The `user_id` should be validated at the request level (in `validate_request()`) not per-action | Code Examples | Low — either approach works. Request-level validation is simpler (one check for all actions) |

## Open Questions

1. **Should user_id be required for QUERY and QUERY_SEAT_MAP?**
   - What we know: These are read-only operations. Currently any client can query without identification.
   - What's unclear: USR-02 says "sent with all requests." But QUERY is also used for initial server discovery (before user ID is sent). Non-TUI clients might not have a user concept.
   - Recommendation: Require user_id for all requests except QUERY/QUERY_SEAT_MAP (which can be anonymous). QUERY is read-only and doesn't create sessions.

2. **Should the old ReservationTable be preserved or replaced?**
   - What we know: SessionManager stores seats directly on UserSession. ReservationTable is currently used for CONFIRM/CANCEL by tx_id lookup.
   - What's unclear: Can we bypass ReservationTable entirely and look up sessions by session_id directly? The old expiry code uses ReservationTable.get_expired_reservations() — with sessions, get_expired() lives on SessionManager.
   - Recommendation: Preserve ReservationTable for backward compatibility (other code may reference it). SessionManager handles session lifecycle. Phase 2 can remove any unused paths.

3. **Should CONFIRM/CANCEL operate on session_id (the whole session) or individual seats within a session?**
   - What we know: SES-04 says "expired session releases all seats atomically." SES-03 says "all selected seats share same expiration."
   - What's unclear: Should CONFIRM confirm ALL session seats, or can the user confirm individual seats within a session?
   - Recommendation: Keep it simple — CONFIRM/CANCEL on the session_id confirms/cancels ALL seats in the session. This matches the existing batch semantics and is the minimum change. Individual seat management can be added later if needed.

## Environment Availability

> No external tools required. All changes are within Python stdlib (threading, uuid, time, dataclasses, json, socket) and Textual (already installed as dependency).

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14+ | All code | ✓ | 3.14 | — |
| Textual | TUI | ✓ | ≥0.70.0 | — |
| pytest | Testing | ✓ | ≥9.0.3 | — |

**Missing dependencies with no fallback:** None

## Security Domain

> `nyquist_validation` is `false` in config.json — skip Validation Architecture section per protocol.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | partial | Display-name identification (not password auth). User ID is self-asserted, not verified. |
| V4 Access Control | partial | Session ownership check: CONFIRM/CANCEL validates `request.user_id == session.user_id` |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Session ID guessing (User A cancels User B's seats) | Tampering | CONFIRM/CANCEL verifies user_id matches session owner |
| Session hijacking (User A sends user_id="Bob") | Spoofing | No mitigation in Phase 1 (simple display name — no auth). If needed, Phase 4+ could add server-assigned tokens. |
| Race: confirm vs expire | Time of check/time of use | MonitorThread checks session state inside table lock after acquiring it — confirm either beats the expiry or vice versa |

## Sources

### Primary (HIGH confidence)
- Codebase analysis: All 15 source files read and understood (STACK.md, ARCHITECTURE.md, CONVENTIONS.md, STRUCTURE.md plus all `.py` source files)
- PROJECT.md: Validated constraints, decisions, and scope boundaries
- REQUIREMENTS.md: Phase 1 requirement IDs USR-01, USR-02, SES-01 through SES-04
- ROADMAP.md: Phase 1 success criteria and dependency relationships

### Secondary (MEDIUM confidence)
- [ASSUMED] Textual Screen API — based on training data knowledge of Textual patterns (push_screen, dismiss, compose). Verified against common Textual usage patterns in the codebase (the TUI already imports from textual.screen indirectly via App).

### Tertiary (LOW confidence)
- None — all findings are either verified against the actual codebase or explicitly tagged as assumptions.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Every recommendation is based on actual code analysis. No third-party libraries needed.
- Architecture: HIGH — SessionManager pattern directly mirrors existing ReservationTable pattern. Lock hierarchy is unchanged.
- Pitfalls: HIGH — All pitfalls are derived from actual code races and concurrency patterns observed in the source.
- Protocol changes: MEDIUM — The exact integration point for user_id validation has two valid approaches; the recommendation is opinionated.

**Research date:** 2026-06-01
**Valid until:** 2026-07-01 (stable codebase — no fast-moving dependencies)
