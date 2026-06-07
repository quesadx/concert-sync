# Quick Task 260604-rml: UI Overhaul — Real System Feel

**Created:** 2026-06-05
**Status:** Ready for execution

## Goal

Transform the PySide6 frontend from a terminal-console-like tool into a polished, user-friendly reservation system. Three core changes: (1) simple numeric login, (2) unified global TTL that resets whenever the user reserves any additional seats, (3) a clearer, more professional seat matrix visualization.

## Tasks

### Task 1: Numeric Login Flow

- **Files:** `frontend_pyside6/widgets/connection_panel.py`, `frontend_pyside6/main_window.py`
- **Action:** Replace the arbitrary User ID text field with a clean numeric-only login. Add a `QDialog`-based login screen that appears on startup, accepts only digits (1+ digits), and uses that as the `user_id`. The ConnectionPanel UI should show the logged-in user ID as a read-only label with a "Change User" button to re-login. Remove the auto-generated UUID-fallback — login is now mandatory.
- **Verify:** Launch the app → login dialog appears, accepts only numbers, rejects empty/non-numeric input. After login, user ID displayed in ConnectionPanel. "Change User" reopens the dialog. Server recognizes the numeric ID in all requests.

### Task 2: Add "Reserve Seats" server action to unify TTL on every reserve

- **Files:** `src/server/transactional_thread.py`, `src/server/session_manager.py`, `src/client/concert_client.py`, `frontend_pyside6/main_window.py`, `frontend_pyside6/workers/network_worker.py`
- **Action:** When a user makes ANY new reservation (single or batch), the server must also reset the `last_activity` timestamp on ALL seats in the user's session to the current time. This gives all seats a fresh TTL every time the user reserves something new. Currently each seat has an independent `reserved_at` timestamp. Modify `SessionManager` so that any reservation for an existing user refreshes the `last_activity` of every seat in that session (not just the new ones). Also ensure the `ttl_secs` field in the response reflects the globally refreshed value. Update the frontend to correctly display the refreshed per-seat TTLs on all owned seats after any reservation.
- **Verify:** Reserve 2 seats → wait 30 seconds → reserve 1 more seat → check that TTL on all 3 seats is now ~300s (not ~270s for the old ones). Old TTL numbers don't appear — only the freshly reset ones.

### Task 3: Professional Seat Matrix Visualization

- **Files:** `frontend_pyside6/widgets/seat_map_widget.py`, `frontend_pyside6/models/seat_state.py`
- **Action:** Overhaul the seat matrix rendering to feel polished and intuitive:
  - Add a stage/screen indicator at the top (a labeled bar: "STAGE").
  - Use rounded seat cells with softer, more professional colors.
  - Add row/col labels that are clearer and more legible.
  - Show a hover tooltip that clearly explains the seat state (e.g., "VIP Row 3, Seat 7 — Available" or "VIP Row 3, Seat 7 — Reserved by YOU (234s remaining)").
  - Add a subtle alternating row/col background pattern to make seats easier to scan.
  - Add section label headers for VIP (labeled "FRONT STAGE"), PREFERENTIAL (labeled "MIDDLE"), and GENERAL (labeled "UPPER") that are visually distinct.
  - Ensure TTL countdown text on owned seats is readable (bigger font, better contrast).
- **Verify:** Visual inspection — seat map has a stage indicator, sections are clearly labeled, hover tooltips are informative, colors are professional and easy to distinguish, TTL text is clearly readable on owned seats.
