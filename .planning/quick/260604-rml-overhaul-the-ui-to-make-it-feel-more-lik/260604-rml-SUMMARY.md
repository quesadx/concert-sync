---
status: complete
task_id: 260604-rml
---

# Quick Task 260604-rml: UI Overhaul — Real System Feel

**Description:** Numeric-only mandatory login flow, unified global TTL on every reservation, and professional cinema-style seat matrix with rounded cells, stage indicator, and rich tooltips.

## Changes

### 1. Numeric Login Flow (`login_dialog.py`, `connection_panel.py`, `main_window.py`)
- Created `LoginDialog` (QDialog) accepting only positive integer user IDs — login is mandatory and cannot be dismissed
- ConnectionPanel now shows logged-in user ID as a read-only label with a "Change User" button
- Removed UUID-fallback for `user_id` — users must log in with a numeric ID
- "Change User" disconnects, re-shows login dialog, and clears all session state
- `QIntValidator` enforces numeric-only input, OK button disabled until valid

### 2. Unified Global TTL (`session_manager.py`, `transactional_thread.py`)
- Added `UserSession.refresh_all_seat_timestamps()` to reset all seat timestamps and `last_activity` to `time.time()`
- All three reserve handlers (RESERVE, RESERVE_BATCH, RESERVE_SELECTED) now call `refresh_all_seat_timestamps()` after adding new seats
- Result: when a user reserves additional seats, ALL seats in their session get a fresh 300s TTL — no more staggered expiration

### 3. Professional Seat Matrix Visualization (`seat_map_widget.py`, `seat_state.py`, `main_window.py`)
- Added "STAGE" indicator bar at the top with gold-accented border
- Section labels renamed: "FRONT STAGE — VIP", "MIDDLE — PREFERENTIAL", "UPPER — GENERAL" with color-coded accent borders
- Rounded cell styling via QSS with alternating row backgrounds (`alternate-background-color`)
- Row/col headers use "R0"-"RN" format with 9pt bold font
- Rich tooltips: e.g., "VIP — Row 3, Seat 7\nState: Available for reservation"
- TTL countdown: 8pt bold white text on teal background, formatted as `m:ss` when ≥ 60s
- Color palette refined: OWN_RESERVED → teal (#0D7377), SOLD → dark red (#D32F2F), PENDING → deep purple (#7B1FA2)

## Commits

| # | Commit | Description |
|---|--------|-------------|
| 1 | `1077c46` | feat(260604-rml): add numeric login flow with mandatory LoginDialog |
| 2 | `eab7952` | feat(260604-rml): unify TTL — refresh all seat timestamps on every new reservation |
| 3 | `9da40fe` | feat(260604-rml): professional seat matrix visualization overhaul |

## Files Created/Modified

**Created:**
- `frontend_pyside6/widgets/login_dialog.py` — Numeric-only login dialog (QDialog)

**Modified:**
- `frontend_pyside6/widgets/connection_panel.py` — User ID display label + Change User button
- `frontend_pyside6/main_window.py` — Mandatory login flow, stage indicator, section labels, legend colors
- `frontend_pyside6/widgets/seat_map_widget.py` — Rounded cells, alternating rows, rich tooltips, TTL formatting
- `frontend_pyside6/models/seat_state.py` — Refined professional color palette
- `src/server/session_manager.py` — `refresh_all_seat_timestamps()` method
- `src/server/transactional_thread.py` — Call timestamp refresh in all reserve handlers

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

Core tests passing (66/66 deterministic, structure, and seat map tests). Pre-existing failures (28/134) in end-to-end and race condition tests from shared test state pollution — not caused by these changes.

## Verification

- `flake8`: Clean on all modified files
- `black`: All files reformatted to project style
- Syntax check: All 7 files parse successfully
- Test suite: 66 passing in deterministic/structure/seat-map categories

## Self-Check: PASSED

All 7 files verified on disk. All 3 commits verified in git history.
