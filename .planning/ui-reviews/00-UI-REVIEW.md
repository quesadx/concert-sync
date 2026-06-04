# Phase 00 — UI Review

**Audited:** 2026-06-04
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md found)
**Screenshots:** Not captured (TUI application — no HTTP dev server)
**UI Type:** Textual Terminal UI (Python)
**Files Examined:** 4 Python files, 1 TCSS file (140 lines)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Clear labels and helpful placeholders, but inconsistent empty-state patterns and ambiguous button labels |
| 2. Visuals | 3/4 | Well-organized two-panel layout with clear sections, but no visual grouping and information-dense dashboard |
| 3. Color | 2/4 | 15+ hardcoded hex colors, no theme variables, inconsistent border accents across panels |
| 4. Typography | 2/4 | Only `bold` and `dim` text-styles used; no italic, reverse, or typography scale |
| 5. Spacing | 2/4 | Uniform `padding: 1` everywhere with no spacing scale; hardcoded heights not responsive |
| 6. Experience Design | 3/4 | Covers loading/error/empty states but lacks spinners, confirmation dialogs, and keyboard shortcuts |

**Overall: 15/24**

---

## Top 3 Priority Fixes

1. **Hardcoded color system — BLOCKER** — Every visual element uses raw hex codes with no variables or theme. 15 unique hex values in TCSS + 5 in Python `Style()` calls. No dark-theme guarantee, no accent color consistency. User impact: inconsistent visual identity; difficult to maintain or theme. Concrete fix: Define TCSS variables (`$bg-dark`, `$bg-panel`, `$accent-teal`, `$accent-amber`, `$border-default`, `$text-primary`) and reference them everywhere. Replace `'#0f1722'` → `$bg-panel`, `'#9ad4d6'` → `$accent-teal`, etc.

2. **No keyboard shortcuts for primary actions — WARNING** — Only 2 bindings (`q`=quit, `F5`=refresh). Users must tab through 10+ widgets or use mouse for every reservation/confirmation action. User impact: slow workflows for power users who prefer keyboard. Concrete fix: Add `Binding("r", "reserve_single", "Reserve")`, `Binding("b", "reserve_batch", "Batch")`, `Binding("c", "confirm", "Confirm")`, `Binding("x", "cancel", "Cancel")` in the BINDINGS list and wire to corresponding actions.

3. **Uniform spacing with no visual breathing room — WARNING** — All padding is `1` (single terminal cell), all margins are `1`. No differentiation between section groups, no whitespace hierarchy. User impact: dense UI feels cramped; hard to visually parse section boundaries. Concrete fix: Establish a spacing scale: `$spacing-sm: 1`, `$spacing-md: 2`, `$spacing-lg: 3`. Apply `padding: 1` to panels, `margin-top: 2` between section groups, `margin-bottom: 1` within sections.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**What works well:**
- Section titles are descriptive: "Connection", "Reserve single seat", "Reserve batch seats", "Transaction actions"
- Placeholder text is helpful: `placeholder="e.g., Alice"` (login), `placeholder="VIP:0:0,VIP:0:1,GENERAL:2:3"` (batch format example)
- Batch format help text explains the `SECTION:ROW:COL` format clearly (lines 146-149)
- Status messages are specific and actionable: `"Port must be a number."`, `"Log path cannot be empty."`
- LoginScreen validation message `"Name cannot be empty!"` is direct

**FLAG — Generic/ambiguous labels:**
- `"Reserve Pending"` button label (line 152) — could read as "pending reservations" vs "reserve my pending selections". Better: `"Confirm Selected Seats"`
- `"Reserve Batch"` label (line 151) — slightly ambiguous whether it's batch reading or batch reserving. Acceptable but could be `"Reserve Batch Seats"`
- `"Apply"` button for log path (line 132) — too generic. Better: `"Set Log Path"`

**FLAG — Inconsistent empty-state messages:**
- `"Batch input is empty."` (line 604) — technically accurate but user-unfriendly
- `"No transactions tracked yet."` (line 1048) — clear
- `"No pending selections to reserve"` (line 700) — good
- `"Not connected. Press Connect to start querying the server."` (line 170-171) — excellent initial state

**WARNING — No error-state copy guidance:**
- Error messages use raw exception text: `f"Connection error: {exc}"` (line 351), `f"Seat select error: {e}"` (line 273)
- Exception `__str__` may produce technical output not suitable for end users

**Fix:**
1. Rename "Reserve Pending" → "Confirm Selected Seats"
2. Add user-friendly error message mapping for common exceptions
3. Standardize empty-state messages to a consistent tone

---

### Pillar 2: Visuals (3/4)

**What works well:**
- Two-panel layout with `Horizontal(id="main-layout")` and `Vertical` containers for left (controls) and right (dashboard) panels
- `.panel-title` class with `text-style: bold` provides clear section demarcation
- Consistent section ordering: connection first, then reservation workflows, then transaction actions
- Side-by-side horizontal rows for related inputs (host+port, row+col, confirm+cancel) — good use of `Horizontal` containers
- Seat map uses DataTable with cell-select cursor — innovative for a TUI

**FLAG — No visual grouping between sections within panels:**
- Sections stacked with only a `Static` title separating them — no section borders, no background color change, no divider lines
- Controls panel (42 chars wide) packs 7 sections into a single column with only `margin-top: 1` between them
- Checklist of sections: Connection, Server log path, Reserve single seat, Reserve batch seats, Transaction actions, Quick actions, Status line — all visually similar
- Fix: Add `border: none` horizontal separators or use `Vertical` groups with distinct backgrounds

**FLAG — Left panel width constraint:**
- `#controls-panel` set to `width: 42` (line 11) — this is narrow for containing labels like "Reserve batch seats" and buttons like "Reserve Pending"
- The `'#2d6a7e'` border for dashboard vs `'#3b4a64'` for controls — colors are inconsistent but not visually meaningful
- Fix: Increase to `width: 48` or use `width: 30%` for proportional sizing

**FLAG — Information density on dashboard:**
- Dashboard contains 7 data elements stacked vertically: status line, section table, seat map selector, seat map, session table, sparklines (×2), and event log
- No collapsible sections or tabs — everything visible at once
- Seat map fixed at `height: 28` — GENERAL section has 20 rows which barely fits
- Fix: Make seat map scrollable with `overflow-y: auto` and consider reducing section table height when not needed

**FLAG — No visual feedback on button press:**
- No hover styles for buttons (only seat-map-table has `:hover` at line 118)
- No disabled visual state — buttons remain same color when `batch_pending` is True or when not connected
- Fix: Add TCSS rules for `Button:disabled` and `Button:hover`

---

### Pillar 3: Color (2/4)

**Hardcoded color inventory — TCSS (`styles.tcss`):**

| Hex | Usage | Element |
|-----|-------|---------|
| `#3b4a64` | border | #controls-panel |
| `#0f1722` | background | #controls-panel |
| `#2d6a7e` | border | #dashboard-panel |
| `#10171f` | background | #dashboard-panel |
| `#9ad4d6` | color | .panel-title, "Y" state |
| `#9fb3c8` | color | #batch-help |
| `#b9cbe0` | color | #seat-map-legend |
| `#5a8f9f` | border | #seat-map-table |
| `#0b1220` | background | #seat-map-table, #request-chart, #thread-chart |
| `#e0f0ff` | color | #seat-map-table |
| `#7aafbf` | border | #seat-map-table:hover |
| `#0d1428` | background | #seat-map-table:hover |
| `#4f6f8f` | border | #request-chart, #thread-chart, #event-log |
| `#d8e6f5` | color | #status-line, #connection-status |

**Hardcoded colors — Python `Style()` calls (`app.py`):**

| Hex | Usage |
|-----|-------|
| `#d4a84b` | "R" (RESERVED by others) |
| `#9ad4d6` | "Y" (OWN_RESERVED — duplicate of panel-title) |
| `#6a9fb5` | "P" (PENDING) |
| `#ff4444` | "?" (unknown state fallback) |

**FLAG — No 60/30/10 distribution:**
- Background: 5 distinct dark values — `#0f1722`, `#10171f`, `#0b1220`, `#0d1428` — slightly different shades with no semantic meaning
- Accent: `#9ad4d6` (teal) used for both panel titles AND own-reserved seat token — ambiguous association
- No dominant, secondary, and accent color roles defined

**FLAG — Inconsistent border accents:**
- Controls panel: `#3b4a64` (muted blue-gray)
- Dashboard panel: `#2d6a7e` (deep teal)
- Seat map: `#5a8f9f` (medium steel)
- Charts: `#4f6f8f` (blue-gray)
- Each panel has a different border color with no rationale

**FLAG — Red only for unknown/error fallback:**
- `#ff4444` used only in the `"?"` fallback —  no red semantic for actual errors
- No green for success states (only Textual's built-in `variant="success"` green on buttons)
- No consistent error/warning color applied in TCSS

**WARNING — Hover state only on one element:**
- Only `#seat-map-table:hover` has a hover style — no hover on buttons, inputs, or selects

**Fix:**
1. Define TCSS variables: `$bg-primary: #0f1722; $bg-secondary: #10171f; $accent: #9ad4d6; $border-default: #4f6f8f; $warning: #d4a84b; $error: #ff4444; $success: #4a9;`
2. Use variables everywhere instead of raw hex
3. Adopt 60/30/10: 60% background (`$bg-primary`), 30% secondary surfaces (`$bg-secondary`), 10% accent (`$accent`)
4. Add hover and disabled states to Input, Select, and Button elements

---

### Pillar 4: Typography (2/4)

**What exists:**
- `.panel-title` uses `text-style: bold` (line 28) — 1 declaration
- `_seat_cell()` uses `bold=True` on "R" and "Y" states
- `Style(dim=True)` used on "S" (SOLD) and "P" (PENDING) states

**What is missing:**
- No `text-style: italic` anywhere — could be used for secondary/help text (e.g., batch-help, seat-map-legend)
- No `text-style: reverse` or `text-style: underline` — no visual variety for interactive hints
- No typographic hierarchy — all body text, titles, labels, data, status, and log entries are the same terminal font at the same size
- `text-opacity` not used — text density is uniform

**FLAG — No distinction between data and labels:**
- DataTable values and section titles both render in default terminal weight
- Only `.panel-title` is bold — but 11 elements use the `panel-title` class so there's no sub-hierarchy
- Status line (`#status-line`) and connection status (`#connection-status`) use the same style as everything else despite being different semantic elements

**FLAG — RichLog styling disabled:**
- `markup=False` on event log (line 195) — Rich terminal markup disabled, so `[UI]`, `[CLIENT]`, `[RESERVE]` tags appear as plain text
- `highlight=True` enables auto-highlighting but without markup, visual differentiation is limited
- Fix: Enable `markup=True` so event log entries can use Rich markup for level-appropriate styling

**Fix:**
1. Add `text-style: italic` to `.help-text` class for guidance text (batch-help, seat-map-legend)
2. Use `text-style: reverse` for status line to make it visually distinct
3. Add `text-opacity: 0.7` for secondary data (TTL count, sparkline labels)
4. Enable `markup=True` on RichLog for styled log entries

---

### Pillar 5: Spacing (2/4)

**Spacing inventory:**

```
Padding:   padding: 1          on controls-panel, dashboard-panel, seat-map-table, request-chart, thread-chart
Margin:    margin-top: 1        on .panel-title, #map-section-select, #section-table, #session-table, etc.
           margin-bottom: 1     on Input, Select, Button, #batch-help, #map-section-select
           margin-left: 1       on #port-input, #col-input, #cancel-btn, #apply-log-btn, #use-last-active-tx-btn
Height:    height: 9            on #section-table
           height: 13           on #session-table
           height: 14           on #event-log
           height: 28           on #seat-map-table
           height: auto         on horizontal rows
Width:     width: 42            on #controls-panel
           width: 1fr           on #dashboard-panel
           width: 100%          on Input, Select, Button
           width: 49%           on paired buttons
           width: 64/34%        on host/port inputs
```

**FLAG — No spacing scale:**
- Every padding value is `1`. Every margin value is `1`. No `2`, `3`, or larger values.
- No differentiation between internal padding and external margins
- No hierarchical spacing — sections close to each other have the same gap as related elements

**FLAG — Hardcoded heights create overflow risk:**
- `#section-table: height: 9` — only fits 3 data rows comfortably (header + 3 sections); no room for additional sections
- `#session-table: height: 13` — capped at ~10 tracked sessions but Dashboard renders `sorted_sessions[:30]`
- `#event-log: height: 14` — fixed height independent of screen size
- These heights are in terminal rows — on a small terminal (24 rows), the layout will overflow
- Fix: Use `height: 1fr` with `max-height` or rely on `overflow-y: auto` without fixed heights

**FLAG — Left panel wasteful with space:**
- `#controls-panel` width fixed at 42 chars but content (especially `#host-input` at 64% = ~27 chars) doesn't need this constraint
- Several horizontal rows (connection-row, log-row, quick-row) wrap only 2 elements — could be more compact
- Fix: Consider `width: 35` or proportional sizing

**WARNING — No responsive behavior:**
- All dimensions are absolute — `padding: 1`, `width: 42`, `height: 28`
- No `min-width` or `max-width` on panels
- On small terminals, the 42-char controls panel + dashboard may not fit
- Fix: Add `grid-size` or `grid-columns` for responsive layout, use `fr` units

**Fix:**
1. Establish spacing variables: `$spacing-sm: 1`, `$spacing-md: 2`, `$spacing-lg: 3`
2. Apply `margin-top: 2` between section groups, retain `margin-top: 1` within groups
3. Remove fixed heights from tables; use `height: 1fr` with `max-height` constraint
4. Add responsive fallback for terminals <100 chars wide

---

### Pillar 6: Experience Design (3/4)

**Loading/Progress states — PARTIAL:**
- Status line updates with "Reserving..." or "Refreshing..." messages — good
- `batch_pending` flag prevents double-submit — good
- `refresh_pending` flag prevents concurrent queries — good
- **MISSING:** No spinner or progress indicator — long operations (batch reserve, connection) show only a static status message
- **MISSING:** Buttons not visually disabled during operations — user can click "Reserve Seat" while a reserve is in progress
- **MISSING:** `_reserve_click_worker` race — `pending_clicks` set is used but there's no guard against rapid clicks on same seat

**Error handling — GOOD:**
- All operations wrapped in try/except with specific error classes
- `ConcertClientError` hierarchy (e.g., `SeatNotAvailableError`, `TransactionNotFoundError`)
- Consecutive failure tracking: 3 failures → "DISCONNECTED — server unreachable" (line 453-456)
- Server reconnection detection (line 428-431)
- Saturated zone pre-flight: pending selections checked against seat_map_snapshot before sending (line 703-726)
- **MISSING:** No retry mechanism for transient failures
- **MISSING:** No error notification beyond status line (ephemeral — overwritten by next operation)

**Empty states — GOOD:**
- Initial state: `"Not connected. Press Connect to start querying the server."` (line 170-171)
- No seat map: `"No seat map data"` (line 1008)
- No transactions: `"No transactions tracked yet."` (line 1047 — as "No ACTIVE transactions tracked yet.")
- No pending selections: `"No pending selections to reserve"` (line 700)
- Sparkline no data: `"Requests/tick: no data"` (line 1084)

**Keyboard interaction — POOR:**
- Only 2 keyboard bindings: `q` (quit) and `F5` (refresh) (lines 87-88)
- Primary actions (Reserve Seat, Reserve Batch, Confirm, Cancel) require mouse or tab-through
- No keyboard shortcut for toggling seat selection
- No keyboard shortcut for opening section selector
- Fix: Add bindings for all primary actions (see Priority Fix #2)

**Confirmation/Destructive actions — PARTIAL:**
- `confirm-btn` and `cancel-btn` present for transactions — good
- `_reserve_pending_selections()` removes conflicted seats silently — user may not notice
- **MISSING:** No confirmation dialog for `cancel-btn` — destructive action executed on single click
- **MISSING:** No undo mechanism for accidental clicks

**Affordance — PARTIAL:**
- `#host-input` and `#port-input` have default values pre-filled — good for quick connect
- Transaction ID auto-filled after each reserve — excellent workflow optimization (lines 544, 567, 680, 774)
- `_resolve_transaction_id_from_input()` auto-fills latest ACTIVE as fallback (lines 1062-1068) — smart UX
- **MISSING:** Clickable seat map rows/columns labeled with `label=f"{row_idx:02d}"` but no visual row-number column — user sees column numbers at top but rows only in label

**Accessibility — LIMITED:**
- No tooltip on any button or widget
- No `aria-label` equivalents (Textual doesn't use HTML aria, but does support `tooltip`)
- Widget naming via `id` enables programmatic querying — good
- Buttons use descriptive text labels — good for screen readers

**Event log — PARTIAL:**
- `RichLog` captures all events with tags like `[CLIENT]`, `[RESERVE]`, `[CONFIRM]`
- `markup=False` prevents Rich markup rendering — tags appear as-is
- No log-level filtering (all events mixed together)
- No log persistence beyond what's in the widget

**Fix:**
1. Add `tooltip` attributes to all buttons: `tooltip="Connect to the concert server"`
2. Add confirmation for Cancel: `self.push_screen(ConfirmScreen(...))` or a second-click pattern
3. Add spinner/progress during long operations: use Textual's built-in `LoadingIndicator`
4. Add keyboard bindings for all primary actions

---

## Registry Safety

**Not applicable.** No `components.json` found. This is not a shadcn project. The UI is a Textual TUI (Python), not a React/HTML component library.

---

## Files Audited

| File | Lines | Type | Role |
|------|-------|------|------|
| `frontend_tui/app.py` | 1098 | Python | Main TUI application — composition, event handlers, data rendering |
| `frontend_tui/login_screen.py` | 33 | Python | Login screen with name input |
| `frontend_tui/__main__.py` | 10 | Python | Application entry point |
| `frontend_tui/__init__.py` | 1 | Python | Package marker |
| `frontend_tui/styles.tcss` | 140 | TCSS | Textual CSS — layout, colors, spacing |
| `frontend_tui/README.md` | 86 | Markdown | Usage documentation |
| `src/client/concert_client.py` | 293 | Python | Client protocol (UI-adjacent) |
| `src/utils/enums.py` | 22 | Python | Seat state enums (UI color mapping source) |
| `src/utils/config.py` | 12 | Python | Section layout config |

---

### Recommendation Summary

- **BLOCKER items:** 1 (hardcoded color system)
- **WARNING items:** 4 (no keyboard shortcuts, uniform spacing, narrow left panel, no RichLog markup)
- **FLAG items:** 11 (documented above across all 6 pillars)
- **Priority fixes:** 3 (detailed in Top 3)
- **Minor recommendations:** 8 (documented in Detailed Findings)
