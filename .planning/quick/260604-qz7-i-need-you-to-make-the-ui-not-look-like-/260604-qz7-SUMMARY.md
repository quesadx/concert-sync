---
phase: quick-260604-qz7
plan: "01"
subsystem: ui
tags: [pyside6, cinema-ui, styling, layout]

# Dependency graph
requires: []
provides:
  - Cinema-style dark theme with gold accents replacing teal
  - Cinema screen graphic at top of seat map area
  - Cinema-style header showing user and selection count
  - Rounded seat cells with theater-like appearance
  - Gold-accented buttons, labels, and status bar
  - Cinema-themed widget labels (✦ ENTER, ★ RESERVE, ✓ CONFIRM, ✕ CANCEL)
  - Section headers without dimension numbers (more cinematic)
  - Themed scrollbars and event log
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - ObjectName-based QSS targeting for component-specific styling
    - Cinema-screen QWidget with gradient background and gold border
    - Seat state colors tuned to match gold-based cinema palette

key-files:
  created: []
  modified:
    - frontend_pyside6/main_window.py
    - frontend_pyside6/resources/styles.qss
    - frontend_pyside6/widgets/seat_map_widget.py
    - frontend_pyside6/widgets/connection_panel.py
    - frontend_pyside6/widgets/section_stats.py
    - frontend_pyside6/widgets/transaction_panel.py
    - frontend_pyside6/widgets/event_log.py
    - frontend_pyside6/models/seat_state.py

key-decisions:
  - "Used gold (#d4a84b) as primary accent color for cinematic feel"
  - "Set seat cell size to 28px (from 30px) for tighter theater-seat grouping"
  - "Kept seat map QTableWidget approach but added objectName for QSS styling"
  - "Screen graphic rendered as styled QWidget with ▬ SCREEN ▬ centered label"
  - "Own_RESERVED color changed from blue to gold to match cinema palette"

patterns-established:
  - "Cinema header text updates reactively on connect/select/reserve/confirm/cancel"
  - "ObjectName-based QSS selectors for component-level styling without class bloat"

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-06-05
---

# Quick Task 260604-qz7: Cinema-Style UI Overhaul — Gold Accents, Screen Graphic, Theater Theme

**Transforms the PySide6 frontend from a functional dev-dark-theme UI into a polished cinema-style seat reservation app with gold accent colors, a visible screen graphic, theater-like seat cells, and an overall feel that does not resemble a terminal/console interface.**

## Accomplishments

- **Gold accent color scheme** (#d4a84b) replaces teal (#9ad4d6) throughout — buttons, headers, scrollbars, status bar, and borders
- **Cinema screen graphic** added at the top of the seat map area — a styled QWidget with gradient background, gold border, and "▬▬▬ SCREEN ▬▬▬" centered label
- **Cinema-style header** shows the current user name and seat selection count dynamically:
  - Not connected: "✦ SELECT YOUR SEATS ✦"
  - Connected: "✦ username — SELECT YOUR SEATS ✦"
  - Selecting: "✦ username — 3 SELECTED ✦"
  - Reserved: "✦ username — 5 SEATS RESERVED ✦"
  - Confirmed: "✦ username — TX CONFIRMED ✦"
  - Cancelled: "✦ username — TX CANCELLED ✦"
- **Seat state colors** tuned to cinema palette:
  - OWN_RESERVED: gold (#d4a84b) instead of blue
  - AVAILABLE: warm green (#5a9e6f)
  - RESERVED: amber (#e8913a)
  - SOLD: cinema red (#d43a3a)
- **Button labels** updated for cinema feel:
  - Connect → ✦ ENTER ✦
  - Reserve Selected → ★ RESERVE SELECTED ★ / ★ RESERVE N SEAT(S) ★
  - Confirm → ✓ CONFIRM
  - Cancel → ✕ CANCEL
- **Widget panel labels** updated: "Patron:" instead of "User ID:", "Server:" instead of "Host:"
- **Section headers** without dimension numbers: "VIP — Orchestra Front", "PREFERENTIAL — Middle Tier", "GENERAL — Upper Level"
- **Seat cells** compacted to 28px (from 30px) for tighter grouping, with rounded appearance via QSS border-radius
- **Custom scrollbars** with gold hover accent
- **ObjectName-based QSS targeting** for precise component-level styling
- **Deep cinematic dark background** (#0a0e17) replaces the previous dark teal theme

## Task Commits

1. **Task 1-3: All cinema-style UI changes** — `779bb15` (feat)

## Files Modified

- `frontend_pyside6/resources/styles.qss` — Complete rewrite: gold accent theme, rounded seat cells, cinema screen style, themed scrollbars, reserve button styling, objectName selectors
- `frontend_pyside6/main_window.py` — Added cinema screen graphic widget, cinema header label, updated window title, section labels without dimensions, dynamic header updates on connect/select/reserve/confirm/cancel, reserve button with ★ styling, objectNames for QSS
- `frontend_pyside6/models/seat_state.py` — Updated seat colors: OWN_RESERVED gold, AVAILABLE warm green, RESERVED amber, SOLD cinema red
- `frontend_pyside6/widgets/seat_map_widget.py` — Added objectName "seat-map", reduced cell size to 28px, header font to 7pt
- `frontend_pyside6/widgets/connection_panel.py` — Added objectName, updated labels ("Patron:", "Server:"), connect button → "✦ ENTER ✦"
- `frontend_pyside6/widgets/transaction_panel.py` — Added objectName, confirm → "✓ CONFIRM", cancel → "✕ CANCEL"
- `frontend_pyside6/widgets/section_stats.py` — Added objectName for QSS targeting
- `frontend_pyside6/widgets/event_log.py` — Added objectName for QSS targeting

## Deviations from Plan

None — all tasks completed as planned.

---

*Quick task: 260604-qz7*
*Completed: 2026-06-05*
