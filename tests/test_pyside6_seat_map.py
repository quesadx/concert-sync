"""Verify seat map widget rendering and visual states (VIS-01, VIS-02).

Tests the SeatMapWidget color assignments for all five display states and
the priority ordering of PENDING / OWN_RESERVED overlays.
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from frontend_pyside6.models.seat_state import SEAT_COLORS
from frontend_pyside6.widgets.seat_map_widget import SeatMapWidget


@pytest.fixture
def vip_widget(qapp):
    """Return a SeatMapWidget pre-configured for a 5×10 VIP grid."""
    widget = SeatMapWidget("VIP", rows=5, cols=10)
    yield widget
    widget.deleteLater()


class TestSeatMapWidget:
    """Visual state coverage for the five seat map display colors."""

    def test_initial_grid_dimensions(self, vip_widget):
        """Widget dimensions match the constructor (rows=5, cols=10)."""
        assert vip_widget.rowCount() == 5
        assert vip_widget.columnCount() == 10

    def test_update_grid_applies_correct_colors(self, vip_widget):
        """AVAILABLE → green, RESERVED → orange, SOLD → red."""
        grid = [["AVAILABLE"] * 10 for _ in range(5)]
        grid[0][0] = "RESERVED"
        grid[1][1] = "SOLD"
        vip_widget.update_grid(grid, set(), set())

        # AVAILABLE cell
        avail_item = vip_widget.item(0, 1)
        assert avail_item.background().color().name() == SEAT_COLORS["AVAILABLE"].name()

        # RESERVED cell
        reserved_item = vip_widget.item(0, 0)
        assert reserved_item.background().color().name() == SEAT_COLORS["RESERVED"].name()

        # SOLD cell
        sold_item = vip_widget.item(1, 1)
        assert sold_item.background().color().name() == SEAT_COLORS["SOLD"].name()

    def test_own_reserved_displays_blue(self, vip_widget):
        """RESERVED seat in own_coords → blue (OWN_RESERVED)."""
        grid = [["AVAILABLE"] * 10 for _ in range(5)]
        grid[0][0] = "RESERVED"
        vip_widget.update_grid(grid, set(), {(0, 0)})

        item = vip_widget.item(0, 0)
        assert item.background().color().name() == SEAT_COLORS["OWN_RESERVED"].name()

    def test_pending_overlay_takes_priority(self, vip_widget):
        """PENDING coords override OWN_RESERVED coords (purple wins)."""
        grid = [["AVAILABLE"] * 10 for _ in range(5)]
        grid[0][0] = "RESERVED"
        vip_widget.update_grid(grid, {(0, 0)}, {(0, 0)})

        item = vip_widget.item(0, 0)
        assert item.background().color().name() == SEAT_COLORS["PENDING"].name()

    def test_sold_displays_red(self, vip_widget):
        """SOLD seat background is red."""
        grid = [["AVAILABLE"] * 10 for _ in range(5)]
        grid[2][2] = "SOLD"
        vip_widget.update_grid(grid, set(), set())

        item = vip_widget.item(2, 2)
        assert item.background().color().name() == SEAT_COLORS["SOLD"].name()

    def test_click_emits_signal(self, qapp, vip_widget):
        """Clicking a cell emits ``seat_clicked`` with correct section/row/col/state."""
        grid = [["AVAILABLE"] * 10 for _ in range(5)]
        grid[0][0] = "SOLD"
        vip_widget.update_grid(grid, set(), set())

        received = []

        def on_click(section, row, col, state):
            received.append((section, row, col, state))

        vip_widget.seat_clicked.connect(on_click)
        vip_widget._on_cell_clicked(0, 0)

        assert len(received) == 1
        section, row, col, state = received[0]
        assert section == "VIP"
        assert row == 0
        assert col == 0
        assert state == "SOLD"
