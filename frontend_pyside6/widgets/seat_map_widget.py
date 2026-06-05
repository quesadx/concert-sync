"""Color-coded QTableWidget seat grid with click handling.

Displays seats in a grid with five visually distinct colors: AVAILABLE green,
OWN_RESERVED blue, RESERVED orange, SOLD red, PENDING purple. Clicking an
AVAILABLE seat emits a signal for the MainWindow to handle; clicking a
non-AVAILABLE seat still emits the signal so the MainWindow can show a
status message.

Port of frontend_tui/app.py _render_seat_map() (lines 1027-1059) and
on_data_table_cell_selected() (lines 259-301) to PySide6.
"""

from typing import Dict, Set

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QFont
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from frontend_pyside6.models.seat_state import SEAT_COLORS, SEAT_BORDERS


class SeatMapWidget(QTableWidget):
    """Color-coded seat grid for a single section (VIP/PREFERENTIAL/GENERAL).

    Emits seat_clicked(section_name, row, col, server_state) when a cell
    is clicked. The MainWindow connects to this signal to handle seat
    selection/deselection logic.

    Attributes:
        section_name: Section identifier (VIP, PREFERENTIAL, or GENERAL).
        _pending_coords: Set of (row, col) tuples currently pending selection.
        _own_reserved_coords: Set of (row, col) tuples reserved by this user.
    """

    seat_clicked = Signal(str, int, int, str)  # section, row, col, state

    def __init__(self, section_name: str, rows: int, cols: int) -> None:
        """Initialize the seat map grid.

        Args:
            section_name: Section identifier (VIP, PREFERENTIAL, or GENERAL).
            rows: Number of rows in this section's grid.
            cols: Number of columns in this section's grid.
        """
        super().__init__(rows, cols)
        self.section_name = section_name
        self.setHorizontalHeaderLabels([str(c) for c in range(cols)])
        self.setVerticalHeaderLabels([f"{r:02d}" for r in range(rows)])
        header_font = QFont()
        header_font.setPointSize(8)
        self.horizontalHeader().setFont(header_font)
        self.verticalHeader().setFont(header_font)
        self.cellClicked.connect(self._on_cell_clicked)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.horizontalHeader().setDefaultSectionSize(32)
        self.verticalHeader().setDefaultSectionSize(32)
        self._pending_coords: Set[tuple[int, int]] = set()
        self._own_reserved_coords: Set[tuple[int, int]] = set()

    def _on_cell_clicked(self, row: int, col: int) -> None:
        """Handle a cell click by emitting the seat_clicked signal.

        Reads server state from Qt.UserRole data and emits the signal
        so the MainWindow can decide whether to select/deselect the seat.

        Args:
            row: Row index of the clicked cell.
            col: Column index of the clicked cell.
        """
        item = self.item(row, col)
        if item:
            state = item.data(Qt.UserRole)
            self.seat_clicked.emit(self.section_name, row, col, state)

    def update_grid(
        self,
        grid_data: list[list[str]],
        pending_coords: Set[tuple[int, int]],
        own_coords: Set[tuple[int, int]],
        own_cell_ttl: Dict[tuple[int, int], int] | None = None,
    ) -> None:
        """Full refresh of the grid from server data.

        Rebuilds every cell with the correct background color based on
        server state, pending selections, and own reservations. Adds
        row/col text labels inside cells, tooltips for every cell, and
        TTL countdown text on owned cells.

        Args:
            grid_data: 2D list of server state strings (AVAILABLE, RESERVED, SOLD).
            pending_coords: Set of (row, col) tuples currently pending local selection.
            own_coords: Set of (row, col) tuples reserved by this user's session.
            own_cell_ttl: Dict mapping (row, col) to remaining TTL seconds for
                cells owned by this user (only for ACTIVE sessions). Defaults to
                empty dict if None.
        """
        if own_cell_ttl is None:
            own_cell_ttl = {}
        self._pending_coords = pending_coords
        self._own_reserved_coords = own_coords
        _ttl_font = QFont()
        _ttl_font.setPointSize(6)
        _label_font = QFont()
        _label_font.setPointSize(7)
        for r, row_data in enumerate(grid_data):
            for c, state in enumerate(row_data):
                item = QTableWidgetItem()
                display_state = self._resolve_display_state(r, c, state)
                color = SEAT_COLORS.get(display_state, SEAT_COLORS["AVAILABLE"])
                border = SEAT_BORDERS.get(display_state, SEAT_BORDERS["AVAILABLE"])
                item.setBackground(QBrush(color))
                item.setData(Qt.UserRole, state)  # Store original server state
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                # Set text alignment to center
                item.setTextAlignment(Qt.AlignCenter)

                # Row/col text label inside cell (small white text centered)
                item.setFont(_label_font)
                item.setText(f"{r},{c}")
                item.setForeground(QBrush(Qt.white))

                # Apply border style via item stylesheet hint
                item.setData(Qt.UserRole + 1, border)

                # Tooltip: clearly distinguish YOUR reservation vs others
                if display_state == "OWN_RESERVED":
                    item.setToolTip(
                        f"{self.section_name}({r},{c}) — YOUR reservation (expires in {own_cell_ttl.get((r, c), 0)}s)"
                    )
                elif display_state == "RESERVED":
                    item.setToolTip(
                        f"{self.section_name}({r},{c}) — Reserved by another user"
                    )
                elif display_state == "PENDING":
                    item.setToolTip(
                        f"{self.section_name}({r},{c}) — Your selection (click to deselect)"
                    )
                else:
                    item.setToolTip(
                        f"{self.section_name}({r},{c}) — {display_state}"
                    )

                # TTL countdown text overlay on owned cells
                if display_state == "OWN_RESERVED":
                    ttl = own_cell_ttl.get((r, c), 0)
                    if ttl > 0:
                        # Show "YOU" label + TTL
                        item.setText(f"{r},{c}\n{ttl}s")
                        item.setFont(_ttl_font)

                self.setItem(r, c, item)

    def _resolve_display_state(self, row: int, col: int, server_state: str) -> str:
        """Map server state to display state, honoring overlays.

        Priority order:
          1. PENDING overlay (local pre-reserve selection)
          2. OWN_RESERVED (server-side or detected via own_coords)
          3. Raw server state

        Args:
            row: Row index of the seat.
            col: Column index of the seat.
            server_state: Raw state string from the server.

        Returns:
            Display state string suitable for SEAT_COLORS lookup.
        """
        if (row, col) in self._pending_coords:
            return "PENDING"
        if server_state == "OWN_RESERVED":
            return "OWN_RESERVED"
        if server_state == "RESERVED" and (row, col) in self._own_reserved_coords:
            return "OWN_RESERVED"
        return server_state
