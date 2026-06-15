"""Section availability count table widget.

Displays a 3-row × 5-column table showing the number of available, reserved,
sold, and pending seats for each section (VIP, PREFERENTIAL, GENERAL).
Updated via update_counts() from a snapshot dict returned by the server
QUERY action, plus a separate pending counts dict for local selections.

Port of frontend_tui/app.py _render_section_table() lines 967-978.
"""

from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem


class SectionStatsWidget(QTableWidget):
    """Displays section availability counts (VIP/PREFERENTIAL/GENERAL)."""

    def __init__(self) -> None:
        """Initialize a 3-row × 5-column table with section labels."""
        super().__init__(3, 5)  # 3 sections × 5 columns
        self.setHorizontalHeaderLabels(
            ["Section", "Available", "Reserved", "Sold", "Pending"]
        )
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        # Static section labels
        for row_idx, section_name in enumerate(["VIP", "PREFERENTIAL", "GENERAL"]):
            self.setItem(row_idx, 0, QTableWidgetItem(section_name))

    def update_counts(self, snapshot: dict, pending: dict | None = None) -> None:
        """Update availability counts from a snapshot dict.

        Args:
            snapshot: Dict with section names as keys, each mapping to
                a dict with 'available', 'reserved', and 'sold' integer counts.
                Example: {'VIP': {'available': 10, 'reserved': 5, 'sold': 3}, ...}
            pending: Dict mapping section name to pending selection count.
                Example: {'VIP': 3, 'PREFERENTIAL': 0, 'GENERAL': 0}.
                Defaults to all zeros if None.
        """
        if pending is None:
            pending = {}
        for row_idx, section_name in enumerate(["VIP", "PREFERENTIAL", "GENERAL"]):
            counts = snapshot.get(section_name, {})
            self.setItem(row_idx, 1, QTableWidgetItem(str(counts.get("available", 0))))
            self.setItem(row_idx, 2, QTableWidgetItem(str(counts.get("reserved", 0))))
            self.setItem(row_idx, 3, QTableWidgetItem(str(counts.get("sold", 0))))
            self.setItem(row_idx, 4, QTableWidgetItem(str(pending.get(section_name, 0))))
