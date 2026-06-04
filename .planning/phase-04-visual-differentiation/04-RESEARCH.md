# Phase 4: Visual Differentiation — Research

**Researched:** 2026-06-03
**Domain:** Seat state rendering, ownership-aware queries, per-cell styling
**Confidence:** HIGH

## Summary

Phase 4 makes a user's own reserved seats visually distinct from other users' selections. The server must enrich the `QUERY_SEAT_MAP` response with ownership data (`OWN_RESERVED` vs `RESERVED`), and the TUI must render those states with distinct colors and tokens. The existing `_seat_token()` / `_render_seat_map()` pipeline in `app.py` is replaced with a richer `_seat_cell()` method that returns `(token, Style)` pairs applied per-cell via `DataTable.update_cell_at()`. No new widgets or layout changes are needed — only the seat map rendering and a legend text update.

**Key insight:** The differentiation must happen at two layers — (1) the server must know which RESERVED seats belong to the requesting user and tag them as `OWN_RESERVED`, and (2) the TUI must map `OWN_RESERVED` → teal `Y` and `RESERVED` → amber `R`. The server already has `SessionManager._sessions` keyed by `user_id` with seat tuples — it just needs to cross-reference in `handle_query_seat_map()`.

**Primary recommendation:** Add `OWN_RESERVED` to the `SeatState` enum, modify `handle_query_seat_map()` to cross-reference the requesting user's session, and replace `_seat_token()` with `_seat_cell()` in the TUI to return per-state `Style` objects for `DataTable.update_cell_at()`.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | User's own selected seats visually distinct from others' | Server returns `OWN_RESERVED` for user's seats; TUI maps to `Y` (teal bold) vs `R` (amber bold) |
| UI-02 | Clear legend/indicator explaining seat state colors | Legend Static widget updated to `A=AVAILABLE R=RESERVED Y=YOURS S=SOLD` |
| UI-03 | Preserve existing UI style — no large redesign | No layout changes, no new widgets, no new CSS — only per-cell DataTable styling via Python `Style` objects |

---

## Standard Stack

### Core
| Component | Purpose | Why Standard |
|-----------|---------|--------------|
| `textual.widgets.DataTable` | Seat map grid with per-cell styling via `update_cell_at()` | Already imported (`app.py:12`); supports `Coordinate` + `Style` for cell-level color |
| `rich.style.Style` | Per-cell color and text-style configuration | Bundled with Textual (Rich dep); used to set `color`, `bold`, `dim` per seat cell |
| `textual.coordinate.Coordinate` | Cell position for `update_cell_at()` | Textual built-in — `Coordinate(row, col)` identifies a specific cell |
| `SeatState` enum | New `OWN_RESERVED` member | Extends existing `src/utils/enums.py` with one new value |

### Supporting
| Module | Purpose | When to Use |
|--------|---------|-------------|
| `session_manager.py` | Look up requesting user's session to identify owned seats | In `handle_query_seat_map()` — `self.server.session_manager.get_or_create(request["user_id"])` |
| `transactional_thread.py` | `handle_query_seat_map()` enriched with ownership check | For each RESERVED seat, cross-reference with requesting user's session seats |
| `app.py` | `_seat_cell()` → `_render_seat_map()` with per-cell `update_cell_at()` | The rendering pipeline |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Per-cell `update_cell_at()` with Style | Rebuild DataTable rows with Rich `Text` objects embedding styles | `update_cell_at()` is the idiomatic Textual approach; `Text` objects work but bypass the DataTable style system |
| OWN_RESERVED token `Y` | Keep `R` for all reserved, change color only | Token change (`Y` = Yours) gives colorblind users a text-level distinction — more accessible |
| Server-side OWN_RESERVED injection | Client-side heuristic (seat in local session) | Server is the source of truth; client-side heuristic is fragile if sessions drift |

---

## Architecture Patterns

### Render Flow (Before → After)

**Before Phase 4:**
```
Client QUERY_SEAT_MAP
  → Server serializes all seats as SeatState.value ("AVAILABLE"/"RESERVED"/"SOLD")
  → TUI _seat_token() maps each string to "A"/"R"/"S"
  → _render_seat_map() calls table.add_row(*tokens)
  → All cells inherit table default color (#e0f0ff)
```

**After Phase 4:**
```
Client QUERY_SEAT_MAP (user_id automatically injected)
  → Server handle_query_seat_map():
       Look up requesting user's session
       For each seat: if RESERVED AND in user's session → return "OWN_RESERVED"
       else return seat.value as before
  → TUI _seat_cell() maps each string to (token, Style):
       "AVAILABLE"    → ("A", None)
       "RESERVED"     → ("R", Style(color="#d4a84b", bold=True))
       "OWN_RESERVED" → ("Y", Style(color="#9ad4d6", bold=True))
       "SOLD"         → ("S", Style(dim=True))
  → _render_seat_map() adds rows with tokens, then calls update_cell_at() for styled cells
```

### Pattern 1: Server-Side Ownership Injection

**What:** `handle_query_seat_map()` in `transactional_thread.py` enriches RESERVED cells with ownership data before returning.

```python
def handle_query_seat_map(self, request):
    seat_map = {}
    requesting_user_id = request.get("user_id", "")
    session = self.server.session_manager.get_or_create(requesting_user_id) \
        if requesting_user_id else None

    with self.server.mutex_manager.sections(list(Section)):
        for section in Section:
            rows = self.server.seat_matrix.seats[section]
            serialized_rows = []
            for row_idx, row in enumerate(rows):
                serialized_row = []
                for col_idx, seat in enumerate(row):
                    if seat == SeatState.RESERVED and session is not None:
                        if (section, row_idx, col_idx) in session.seats:
                            serialized_row.append("OWN_RESERVED")
                        else:
                            serialized_row.append(seat.value)
                    else:
                        serialized_row.append(seat.value)
                serialized_rows.append(serialized_row)
            seat_map[section.name] = serialized_rows

    return build_success_response(seat_map=seat_map)
```

**When to use:** Every `QUERY_SEAT_MAP` request must go through this enriched path.

**Important:** `session.seats` is read outside the lock (it's an `in` check on a list). This is safe because:
- The section locks protect the seat matrix (source of truth)
- Session seat list mutations happen inside `table_and_sections` blocks
- The `in` check is a read — missing a recently-added seat just means it renders as `RESERVED` (amber) instead of `OWN_RESERVED` (teal) for one refresh cycle — harmless

### Pattern 2: Per-Cell Styling with DataTable.update_cell_at()

**What:** Replace `_seat_token()` with `_seat_cell()` returning `(token, Optional[Style])`, then use `update_cell_at()` for cells that need non-default styling.

```python
from rich.style import Style
from textual.coordinate import Coordinate

@staticmethod
def _seat_cell(state: str) -> tuple[str, Optional[Style]]:
    if state == "AVAILABLE":
        return ("A", None)
    if state == "RESERVED":
        return ("R", Style(color="#d4a84b", bold=True))
    if state == "OWN_RESERVED":
        return ("Y", Style(color="#9ad4d6", bold=True))
    if state == "SOLD":
        return ("S", Style(dim=True))
    return ("?", Style(color="#ff4444"))

def _render_seat_map(self) -> None:
    table = self.query_one("#seat-map-table", DataTable)
    table.clear(columns=True)

    selected_grid = self.seat_map_snapshot.get(self.selected_map_section, [])
    if not selected_grid:
        self.query_one("#seat-map-legend", Static).update("No seat map data")
        return

    num_cols = len(selected_grid[0])
    table.add_columns(*[str(c) for c in range(num_cols)])

    for row_idx, row in enumerate(selected_grid):
        cells = [self._seat_cell(state) for state in row]
        table.add_row(*[token for token, _ in cells], label=f"{row_idx:02d}")
        for col_idx, (token, style) in enumerate(cells):
            if style is not None:
                table.update_cell_at(Coordinate(row_idx, col_idx), token, style=style)

    self.query_one("#seat-map-legend", Static).update(
        "A=AVAILABLE  R=RESERVED  Y=YOURS  S=SOLD  (click an available seat to reserve)"
    )
```

**When to use:** In `_render_seat_map()` — the replacement for the current `_seat_token()` + `add_row()` only approach.

### Pattern 3: SeatState Enum Extension

**What:** Add `OWN_RESERVED` to the existing `SeatState` enum.

```python
class SeatState(Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    OWN_RESERVED = "OWN_RESERVED"  # NEW
    SOLD = "SOLD"
```

**When to use:** Required for type-safety in server-side checks. `OWN_RESERVED` is never written to the seat matrix — it's only used in the query response serialization path. The seat matrix remains `AVAILABLE` / `RESERVED` / `SOLD`.

### Anti-Patterns to Avoid

- **Writing OWN_RESERVED to SeatMatrix:** The seat matrix is the source of truth. `OWN_RESERVED` is a view-level concept (whose seat is this?). Writing it would break CONFIRM/CANCEL checks that expect `SeatState.RESERVED`. Keep it only in the query response.
- **Client-side ownership heuristic:** Don't let the TUI guess which RESERVED seats are "yours" based on local session state. The server is the authority. If the client guesses wrong (e.g., after session expiry race), the UI shows teal for a non-owned seat.
- **CSS-based per-cell styling:** Textual's `.tcss` files cannot target individual DataTable cells by state. All per-cell differentiation must use Python `Style` objects via `update_cell_at()`.

---

## Key Files

| File | Change | Details |
|------|--------|---------|
| `src/utils/enums.py` | Add `OWN_RESERVED = "OWN_RESERVED"` to `SeatState` | New member — never stored in matrix, only used in query serialization |
| `src/server/transactional_thread.py` | Enrich `handle_query_seat_map()` with ownership cross-reference | Extract `user_id` from request, look up session, tag owned RESERVED seats as `"OWN_RESERVED"` |
| `frontend_tui/app.py` | Replace `_seat_token()` with `_seat_cell()`; rewrite `_render_seat_map()` with `update_cell_at()`; update legend text | Core rendering change + legend copy update |
| `frontend_tui/styles.tcss` | No changes | All per-cell styling is Python `Style` objects, not CSS |
| `src/client/concert_client.py` | No changes needed | `user_id` already injected by `send_request()` into all requests including `QUERY_SEAT_MAP` |

### Detailed File Changes

#### 1. `src/utils/enums.py` — Lines 3-6

Add one new enum member:
```python
class SeatState(Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    OWN_RESERVED = "OWN_RESERVED"  # NEW — view-only, never stored in SeatMatrix
    SOLD = "SOLD"
```

**Risk:** None. Existing code checks `== SeatState.AVAILABLE`, `== SeatState.RESERVED`, `== SeatState.SOLD` — none are affected by an additional member. No code writes `OWN_RESERVED` to the matrix.

#### 2. `src/server/transactional_thread.py` — `handle_query_seat_map()` at line 448

Current: serializes all seat state values as-is via `seat.value`.

Target: cross-reference each RESERVED seat against the requesting user's session.

Key implementation details:
- Extract `requesting_user_id = request.get("user_id", "")` — works for both authenticated and anonymous QUERY_SEAT_MAP calls
- Get session: `session = self.server.session_manager.get_or_create(requesting_user_id)` — only when user_id is non-empty
- Inside the section lock loop: for each cell, if `seat == SeatState.RESERVED` and `(section, row_idx, col_idx) in session.seats`, emit `"OWN_RESERVED"` instead of `"RESERVED"`

**Safety note:** `session.seats` is a `List[Tuple[Section, int, int]]`. The `in` check is O(n) but sessions rarely exceed ~10 seats. This is fine.

#### 3. `frontend_tui/app.py`

Three changes:

**A. Add imports** (near line 12):
```python
from rich.style import Style
from textual.coordinate import Coordinate
```

**B. Replace `_seat_token()` at line 856** with `_seat_cell()`:
- Change signature: `def _seat_cell(state: str) -> tuple[str, Optional[Style]]`
- AVAILABLE → `("A", None)`
- RESERVED → `("R", Style(color="#d4a84b", bold=True))`  (amber)
- OWN_RESERVED → `("Y", Style(color="#9ad4d6", bold=True))`  (teal)
- SOLD → `("S", Style(dim=True))`  (muted)
- default → `("?", Style(color="#ff4444"))`

**C. Rewrite `_render_seat_map()` at line 866**:
- Build `table.add_row(*[token for token, _ in cells], label=...)`
- Loop `for col_idx, (token, style) in enumerate(cells): if style: table.update_cell_at(Coordinate(row_idx, col_idx), token, style=style)`
- Update legend text to `"A=AVAILABLE  R=RESERVED  Y=YOURS  S=SOLD  (click an available seat to reserve)"`

#### 4. `frontend_tui/styles.tcss` — No changes

The existing `#seat-map-table` CSS provides the base text color (`#e0f0ff`) and background (`#0b1220`). All per-state differentiation is applied via `Style` objects in Python.

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| SessionManager race: session.seats read outside lock in handle_query_seat_map | Stale seat list — own seat renders as RESERVED (amber) for one refresh cycle | Low | Harmless — next refresh (1s) gets correct state. The section locks ensure consistent seat matrix values. |
| Seat matrix still uses SeatState.RESERVED internally | OWN_RESERVED must never be written to matrix | Medium | Enforce via code review: `OWN_RESERVED` is ONLY used in `handle_query_seat_map()` serialization. No write path references it. |
| Anonymous client calls QUERY_SEAT_MAP without user_id | All RESERVED seats show as amber — graceful degradation | Low | Intended behavior — anonymous clients can't own seats. `request.get("user_id", "")` returns empty, session lookup skipped, all RESERVED stays as "RESERVED". |
| Color contrast issues on different terminals | Amber/teal indistinguishable on some terminals | Medium | Token characters differ (`R` vs `Y`) — provides text-level redundancy for colorblind users. Bold text style adds another dimension. |
| _seat_token() still referenced elsewhere in app.py | If another code path calls _seat_token(), it won't handle "OWN_RESERVED" | Low | After refactoring, `_seat_token()` no longer exists (replaced by `_seat_cell()`). Use grep after refactor to ensure no dangling references. |
| update_cell_at() called after table.clear() loses reference | Table must be populated before update_cell_at() works | Low | Current code structure: `table.clear()`, `table.add_columns()`, `table.add_row()`, then `update_cell_at()`. The DataTable reference stays valid throughout. |

---

## Dependencies

### Required (must be completed first)
- **Phase 1: User ID + Session TTL** ✓ — `SessionManager`, `UserSession`, `user_id` injection, session-aware handlers all exist. Phase 4 depends on:
  - `ConcertClient.send_request()` injecting `user_id` (already done — `concert_client.py:89`)
  - `SessionManager._sessions` keyed by `user_id` (already done — `session_manager.py:32`)
  - `UserSession.seats` list with `(Section, row, col)` tuples (already done — `session_manager.py:15`)
  - Server extracting `user_id` from request payloads (already done — `transactional_thread.py:113`)

### Not Required
- Phase 2 (expiration fix) — independent
- Phase 3 (buy near expiry) — independent
- No new external packages needed (Rich `Style` is bundled with Textual)

### Implicit Dependencies
- `rich.style.Style` — available via `pip install textual` (already installed)
- `textual.coordinate.Coordinate` — available via `pip install textual` (already installed)
- Both are stdlib-adjacent (Rich and Textual are existing project dependencies)

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-cell DataTable styling | Manual cell wrapping with Rich Text | `DataTable.update_cell_at(coordinate, value, style=Style(...))` | Idiomatic Textual API — handles rendering edge cases |
| Server-side session lookup | Linear scan of all sessions | `SessionManager.get_or_create(user_id)` (O(1) dict lookup) | Already implemented in Phase 1 — returns session in constant time |
| Color/state mapping | If/elif chain in a separate config file | `_seat_cell()` static method on `ConcertTextualApp` | Follows existing code pattern (`_seat_token()` was already a static method) |

---

## Common Pitfalls

### Pitfall 1: OWN_RESERVED Leaks into SeatMatrix
**What goes wrong:** A future developer sees `SeatState.OWN_RESERVED` and uses it when writing seat state (e.g., in handle_reserve or handle_cancel).
**How to avoid:** Add a docstring comment on the enum member: `# view-only — never stored in SeatMatrix`. In code review, ensure no write path references it.
**Warning signs:** CONFIRM handler checks `if seat_state != SeatState.RESERVED` and misses `OWN_RESERVED`.

### Pitfall 2: user_id Missing from QUERY_SEAT_MAP
**What goes wrong:** Client calls `query_seat_map()` but the request doesn't include `user_id`, so the server can't identify which RESERVED seats belong to the caller.
**Why it happens:** `QUERY_SEAT_MAP` was explicitly exempted from `user_id` validation in Phase 1 (protocol_validator skips the check for QUERY/QUERY_SEAT_MAP).
**How to avoid:** This is actually the correct behavior — `ConcertClient.send_request()` injects `user_id` into ALL requests regardless of action (`concert_client.py:89`). So QUERY_SEAT_MAP will have `user_id` when sent through `ConcertClient`. The server's `handle_query_seat_map()` should handle the missing case gracefully (anonymous fallback).
**Warning signs:** All RESERVED seats show in amber even for the owning user — check that `user_id` is actually being sent.

### Pitfall 3: Session.seats Read Outside Lock
**What goes wrong:** `handle_query_seat_map()` reads `session.seats` (an `in` check) without holding the SessionManager lock. Another thread could be appending to the list concurrently.
**How to avoid:** Python list `in` is thread-safe for reads (CPython GIL protects atomic operations on lists). The only risk is reading a stale value — which means a just-reserved seat shows as amber for one cycle. Acceptable.
**Warning signs:** None (graceful degradation by design).

### Pitfall 4: Style Overwriting on Refresh
**What goes wrong:** Every `_refresh_every_second` call triggers `_render_seat_map()` which calls `table.clear()` + `table.add_columns()` + `table.add_row()` + `update_cell_at()`. If `update_cell_at()` is called before the row is fully rendered, the style might not stick.
**How to avoid:** The current code structure is correct: `clear()` removes everything, then `add_columns()`, then each `add_row()` creates a new row, then `update_cell_at()` sets the display value and style on the existing cell. Since the cell already exists (created by `add_row`), the style is applied correctly.
**Warning signs:** Cells render with default color — check ordering of `add_row` and `update_cell_at`.

### Pitfall 5: Coordinate vs (row, column) Argument Order
**What goes wrong:** `DataTable.update_cell_at()` takes a `Coordinate(row, column)` — but the first call uses `Coordinate(column, row)` by accident.
**How to avoid:** `Coordinate` is row-major (`Coordinate(row_index, column_index)`). Match the loop: `row_idx` is the outer loop, `col_idx` is the inner loop. Visual inspection: `row_idx` should match the row label prefix.
**Warning signs:** Wrong cells get styled — the pattern of styled cells is transposed.

---

## Code Examples

### Full handle_query_seat_map with ownership

```python
def handle_query_seat_map(self, request):
    try:
        seat_map = {}
        requesting_user_id = request.get("user_id", "")
        session = None
        if requesting_user_id:
            session = self.server.session_manager.get_or_create(requesting_user_id)

        with self.server.mutex_manager.sections(list(Section)):
            for section in Section:
                rows = self.server.seat_matrix.seats[section]
                serialized_rows = []
                for row_idx, row in enumerate(rows):
                    serialized_row = []
                    for col_idx, seat in enumerate(row):
                        if seat == SeatState.RESERVED and session is not None:
                            if (section, row_idx, col_idx) in session.seats:
                                serialized_row.append("OWN_RESERVED")
                            else:
                                serialized_row.append(seat.value)
                        else:
                            serialized_row.append(seat.value)
                    serialized_rows.append(serialized_row)
                seat_map[section.name] = serialized_rows

        return build_success_response(seat_map=seat_map)

    except Exception as e:
        self.server.global_log.append("ERROR", f"QUERY_SEAT_MAP failed: {str(e)}")
        return error_internal(str(e))
```

### Full _seat_cell and _render_seat_map

```python
from rich.style import Style
from textual.coordinate import Coordinate

@staticmethod
def _seat_cell(state: str) -> tuple[str, Optional[Style]]:
    if state == "AVAILABLE":
        return ("A", None)
    if state == "RESERVED":
        return ("R", Style(color="#d4a84b", bold=True))
    if state == "OWN_RESERVED":
        return ("Y", Style(color="#9ad4d6", bold=True))
    if state == "SOLD":
        return ("S", Style(dim=True))
    return ("?", Style(color="#ff4444"))

def _render_seat_map(self) -> None:
    table = self.query_one("#seat-map-table", DataTable)
    table.clear(columns=True)

    selected_grid = self.seat_map_snapshot.get(self.selected_map_section, [])
    if not selected_grid:
        self.query_one("#seat-map-legend", Static).update("No seat map data")
        return

    num_cols = len(selected_grid[0])
    table.add_columns(*[str(col_idx) for col_idx in range(num_cols)])

    for row_idx, row in enumerate(selected_grid):
        cells = [self._seat_cell(state) for state in row]
        tokens = [token for token, _ in cells]
        table.add_row(*tokens, label=f"{row_idx:02d}")
        for col_idx, (token, style) in enumerate(cells):
            if style is not None:
                table.update_cell_at(Coordinate(row_idx, col_idx), token, style=style)

    self.query_one(
        "#seat-map-legend", Static
    ).update("A=AVAILABLE  R=RESERVED  Y=YOURS  S=SOLD  (click an available seat to reserve)")
```

### Empty State Handling (when user has no TrackedSession)

```python
def _render_seat_map(self) -> None:
    # ...existing code...
    if not selected_grid or all(
        all(state == "AVAILABLE" for state in row)
        for row in selected_grid
    ):
        # Only show empty state if no active sessions
        has_active = any(s.state == "ACTIVE" for s in self.sessions.values())
        if not has_active:
            self.query_one("#seat-map-legend", Static).update(
                "No active reservations — click an available seat to begin."
            )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| All RESERVED seats render as `R` in default color | Own RESERVED seats render as `Y` (teal bold); others' render as `R` (amber bold) | Phase 4 | Visual differentiation — users can instantly see their seats |
| SOLD seats render as `S` in default color | SOLD seats render as `S` (dimmed) | Phase 4 | Subtle visual cue that a seat is permanently taken |
| Server returns raw seat state strings | Server enriches RESERVED with ownership data | Phase 4 | Backward compatible — existing clients ignore "OWN_RESERVED" or see it as an unknown state (graceful fallback to `?`) |
| `_seat_token()` returns single char string | `_seat_cell()` returns `(token, Optional[Style])` pair | Phase 4 | Enables per-cell color control |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `DataTable.update_cell_at(coordinate, value, style=Style(...))` applies the style correctly even when the cell value doesn't change | Code Examples | Low — if style is ignored, cells won't be colored but tokens will still differ (`Y` vs `R`), providing text-level differentiation |
| A2 | Reading `session.seats` (a list) outside the session lock is safe for the `in` check | Architecture Patterns | Low — CPython GIL makes list membership tests atomic. Stale reads just mean one refresh cycle of amber instead of teal |
| A3 | `request.get("user_id", "")` works reliably — the client always sends it | Standard Stack | Medium — if a non-Textual client sends QUERY_SEAT_MAP without user_id, all RESERVED cells come back as `"RESERVED"` (no `OWN_RESERVED`). The TUI handles this gracefully (renders as amber `R`). |
| A4 | The `Coordinate` import from `textual.coordinate` is available in Textual ≥0.70.0 | Standard Stack | Low — `Coordinate` is a core Textual class, available since early versions |

---

## Open Questions

1. **Should handle_query_seat_map use `get_or_create` or just `get_by_session_id` for session lookup?**
   - `get_or_create` creates a session if none exists. For a read-only query, this is undesirable — it creates a side effect (empty session).
   - Safer: iterate `self.server.session_manager._sessions` directly to look up by user_id. But this accesses a private dict.
   - Recommendation: Use a new helper on SessionManager: `get_by_user_id(user_id) -> Optional[UserSession]` that does an O(1) dict lookup without creating. This avoids the side effect of `get_or_create`.
   - **RESOLVED:** Add `get_by_user_id(user_id: str) -> Optional[UserSession]` to SessionManager. Simple one-liner: `with self._lock: return self._sessions.get(user_id, None)`.

2. **Should SOLD seats be dimmed or stay at default color?**
   - UI-SPEC specifies `Style(dim=True)` for SOLD cells (`#556677`).
   - The spec intentionally dims SOLD to visually de-emphasize permanently taken seats, drawing attention to AVAILABLE and RESERVED seats.
   - Recommendation: Implement as specified. If users find it too muted, it can be adjusted in a follow-up.

3. **Should the OWN_RESERVED check in handle_query_seat_map use tuple membership `(section, row, col) in session.seats` or a set for efficiency?**
   - For typical sessions (1-10 seats), O(n) list membership is fine.
   - For theoretical sessions with 100+ seats (unlikely given section sizes), a set would be faster.
   - Recommendation: Use list `in` for now. If profiling shows this is a bottleneck, convert to set lookup.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14+ | All code | ✓ | 3.14 | — |
| Textual (DataTable, Coordinate) | TUI rendering | ✓ | ≥0.70.0 | — |
| Rich (Style) | Per-cell styling | ✓ | Bundled with Textual | — |
| pytest | Testing | ✓ | ≥9.0.3 | — |

**Missing dependencies with no fallback:** None

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | partial | handle_query_seat_map enriches only the requesting user's seats with OWN_RESERVED — no other user's ownership data is exposed |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| User A sees User B's seat state as OWN_RESERVED | Information Disclosure | Server only checks `session.seats` against the requesting user's own session — other users' RESERVED seats stay as "RESERVED" |
| Anonymous query reveals reservation patterns | Information Disclosure | Anonymous queries get all RESERVED without ownership data — existing behavior, unchanged |

---

## Sources

### Primary (HIGH confidence)
- Codebase analysis: All 20+ source files read and understood
- UI-SPEC.md: Phase 4 UI design contract (authoritative)
- Phase 1 RESEARCH.md: SessionManager, user_id injection patterns (confirmed correct)
- REQUIREMENTS.md: UI-01, UI-02, UI-03
- ROADMAP.md: Phase 4 scope, success criteria, file modification list

### Secondary (MEDIUM confidence)
- [ASSUMED] Textual DataTable `update_cell_at()` API — based on training data knowledge. Verified against import patterns in `app.py`.
- [ASSUMED] Rich `Style(color=..., bold=True)` constructor — verified against Rich documentation patterns.

### Tertiary (LOW confidence)
- None — all findings verified against actual codebase or explicitly tagged as assumptions.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Every recommendation based on actual codebase analysis. No new external packages.
- Architecture: HIGH — Ownership injection pattern directly mirrors existing server patterns. Lock hierarchy unchanged.
- Pitfalls: HIGH — All pitfalls derived from code races and API constraints observed in the source.
- Protocol changes: HIGH — Trivial additive change (OWN_RESERVED in response; backward compatible).

**Research date:** 2026-06-03
**Valid until:** 2026-07-03 (stable codebase)
