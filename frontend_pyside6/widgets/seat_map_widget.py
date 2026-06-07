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

    def __init__(self, section_name: str, rows: int, cols: int, cell_size: int = 26) -> None:
        """Initialize the seat map grid.

        Args:
            section_name: Section identifier (VIP, PREFERENTIAL, or GENERAL).
            rows: Number of rows in this section's grid.
            cols: Number of columns in this section's grid.
            cell_size: Pixel size for each seat cell (default 26).
        """
        super().__init__(rows, cols)
        self.section_name = section_name
        self.setObjectName(f"seat-map-{section_name.lower()}")
        self.setHorizontalHeaderLabels([str(c) for c in range(cols)])
        self.setVerticalHeaderLabels([f"{r:02d}" for r in range(rows)])
        header_font = QFont()
        header_font.setPointSize(7)
        self.horizontalHeader().setFont(header_font)
        self.verticalHeader().setFont(header_font)
        self.cellClicked.connect(self._on_cell_clicked)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionMode(QTableWidget.NoSelection)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFrameShape(QTableWidget.Shape.NoFrame)
        self.setShowGrid(False)
        self.horizontalHeader().setDefaultSectionSize(cell_size)
        self.verticalHeader().setDefaultSectionSize(cell_size)
        self.horizontalHeader().setMinimumSectionSize(cell_size)
        self.verticalHeader().setMinimumSectionSize(cell_size)
        self._cell_size = cell_size
        vheader_w = self.verticalHeader().sizeHint().width()
        hheader_h = self.horizontalHeader().sizeHint().height()
        natural_w = vheader_w + cols * cell_size + 8
        natural_h = hheader_h + rows * cell_size + 8
        self.setMinimumSize(natural_w, natural_h)
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
        # Scale font sizes proportionally to cell size for readability
        label_pt = max(7, self._cell_size // 4)
        ttl_pt = max(6, self._cell_size // 5)
        _ttl_font = QFont()
        _ttl_font.setPointSize(ttl_pt)
        _label_font = QFont()
        _label_font.setPointSize(label_pt)
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

                # Subtle row/col label so cells are never truly empty
                # (empty cells can confuse Qt's backing-store repaint)
                item.setFont(_label_font)
                if display_state == "OWN_RESERVED":
                    ttl = own_cell_ttl.get((r, c), 0)
                    if ttl > 0:
                        item.setText(str(ttl))
                        item.setFont(_ttl_font)
                    else:
                        item.setText("Y")
                    item.setForeground(QBrush(Qt.white))
                elif display_state == "PENDING":
                    # Small dot to show selection without clutter
                    item.setText("\u2022")
                    item.setForeground(QBrush(Qt.white))
                else:
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

                self.setItem(r, c, item)

        # Force the viewport to repaint so background colors are immediately visible
        self.viewport().update()

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
