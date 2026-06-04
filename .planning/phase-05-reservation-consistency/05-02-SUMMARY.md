# Phase 5 — Plan 02 Summary: TUI pending seat selection

**Wave:** 2
**Status:** Executed ✓
**Commit:** 19e44fc

## Changes

### frontend_tui/app.py
- Added `self.pending_selections: List[dict]` in `__init__`
- Modified `on_data_table_cell_selected`: clicking available seat toggles in `pending_selections` instead of immediate `RESERVE`; clicking pending seat deselects it
- Added `PENDING` rendering in `_seat_cell()`: `("P", Style(color="#6a9fb5", dim=True))`
- Modified `_render_seat_map()` to overlay pending state: cells in `pending_selections` render as `P` instead of their actual server state
- Added `Button("Reserve Pending", id="reserve-pending-btn", variant="warning")` in `compose()`
- Added button handler dispatching to `_reserve_pending_selections()`
- Added `_reserve_pending_selections()`: validates non-empty, calls `reserve_selected()`, clears pending on success, rendering refresh
- Added worker/succeeded/failed methods following same pattern as batch reserve
- Legend updated: `"A=AVAILABLE  P=PENDING  R=RESERVED  Y=YOURS  S=SOLD  (click available seats, then Reserve Pending)"`
- Existing single-seat RESERVE and RESERVE_BATCH paths completely unchanged

## Verification
- Cell click toggles seat in pending_selections (add if AVAILABLE, remove if already pending)
- PENDING renders as "P" in muted blue
- "Reserve Pending" button is visible and functional
- Success clears pending_selections and re-renders seat map
- Legend shows P=PENDING

## Requirements Covered
- CON-01 (individual mode reserves all seats atomically via pending + Reserve Pending)
- CON-02 (block mode continues working — Reserve Batch button unchanged)
- CON-03 (both modes produce consistent results)
