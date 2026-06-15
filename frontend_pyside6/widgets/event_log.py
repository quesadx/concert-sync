"""Color-coded, timestamped event log widget with local/remote distinction.

EventLogWidget: Read-only QTextEdit that appends timestamped entries with
color-coded category prefixes (LOCAL green, REMOTE orange, ERROR red,
SERVER grey, EXPIRE brown).

LogTailer: Tails a server log file, returning only new lines since the
last read. Ported verbatim from frontend_tui/app.py lines 48-79.

ActivityDialog: Pop-up window that combines event log, active sessions,
and sold-seats history into one polished dialog.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from frontend_pyside6.models.seat_state import CATEGORY_COLORS


class EventLogWidget(QTextEdit):
    """Read-only log widget with color-coded entries.

    Appends events with a timestamp and category prefix in the category's
    designated color. Mirrors the TUI's _append_event() pattern.
    """

    def __init__(self) -> None:
        """Initialize a read-only text edit for event display."""
        super().__init__()
        self.setReadOnly(True)

    def append_event(self, category: str, message: str) -> None:
        """Append an event with category-specific color.

        Args:
            category: Event category (LOCAL, REMOTE, ERROR, SERVER, EXPIRE).
            message: The event description text.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = CATEGORY_COLORS.get(category, "#000000")

        self.moveCursor(QTextCursor.End)
        self.insertHtml(
            f'<span style="color:{color}">[{timestamp}] [{category}]</span> '
            f"{message}<br>"
        )
        self.ensureCursorVisible()

    def clear_log(self) -> None:
        """Clear all event log content."""
        self.clear()

    def append_line(self, line: str) -> None:
        """Append a raw server log line (called during log tailing).

        Args:
            line: A raw log line from the server log file.
        """
        self.moveCursor(QTextCursor.End)
        self.insertPlainText(line + "\n")
        self.ensureCursorVisible()


class ActivityDialog(QDialog):
    """Pop-up dialog with four tabs: Event Log, Active Sessions, Sold Seats, Section Stats.

    Can be opened and closed independently without affecting the main
    window layout. Reuses EventLogWidget internally.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the activity dialog with tabs."""
        super().__init__(parent)
        self.setWindowTitle("Activity Center")
        self.setMinimumSize(800, 550)
        self.resize(900, 650)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        self._tabs = QTabWidget()
        # Tab styling lives in styles.qss now for a consistent look

        # ── Tab 1: Event Log ──────────────────────────────────────────────
        self.event_log = EventLogWidget()
        self._tabs.addTab(self.event_log, "Event Log")

        # ── Tab 2: Active Sessions ────────────────────────────────────────
        self._sessions_widget = QWidget()
        sessions_layout = QVBoxLayout(self._sessions_widget)
        sessions_layout.setContentsMargins(6, 6, 6, 6)

        self._sessions_table = QTableWidget(0, 5)
        self._sessions_table.setHorizontalHeaderLabels(
            ["Transaction", "Type", "State", "TTL", "Seats"]
        )
        self._sessions_table.setColumnWidth(0, 200)
        self._sessions_table.setColumnWidth(1, 90)
        self._sessions_table.setColumnWidth(2, 80)
        self._sessions_table.setColumnWidth(3, 70)
        self._sessions_table.horizontalHeader().setStretchLastSection(True)
        # QTableWidget styling handled by styles.qss
        sessions_layout.addWidget(self._sessions_table)
        self._tabs.addTab(self._sessions_widget, "Active Sessions")

        # ── Tab 3: Sold Seats ─────────────────────────────────────────────
        self._sold_widget = QWidget()
        sold_layout = QVBoxLayout(self._sold_widget)
        sold_layout.setContentsMargins(6, 6, 6, 6)

        sold_header = QLabel("Your confirmed / sold seats")
        sold_header.setObjectName("sold-header")
        sold_layout.addWidget(sold_header)

        self._sold_list = QLabel("No confirmed seats yet.")
        self._sold_list.setObjectName("sold-list-bg")
        self._sold_list.setWordWrap(True)
        sold_layout.addWidget(self._sold_list)
        sold_layout.addStretch()
        self._tabs.addTab(self._sold_widget, "Sold Seats")

        # ── Tab 4: Section Stats ──────────────────────────────────────────
        self._stats_widget = QWidget()
        stats_layout = QVBoxLayout(self._stats_widget)
        stats_layout.setContentsMargins(6, 6, 6, 6)

        stats_header = QLabel("Section Overview")
        stats_header.setObjectName("sold-header")
        stats_layout.addWidget(stats_header)

        self._stats_table = QTableWidget(3, 4)
        self._stats_table.setHorizontalHeaderLabels(["Section", "Available", "Reserved", "Sold"])
        self._stats_table.setColumnWidth(0, 140)
        self._stats_table.setColumnWidth(1, 90)
        self._stats_table.setColumnWidth(2, 90)
        self._stats_table.horizontalHeader().setStretchLastSection(True)
        # QTableWidget styling handled by styles.qss
        stats_layout.addWidget(self._stats_table)
        stats_layout.addStretch()
        self._tabs.addTab(self._stats_widget, "Section Stats")

        layout.addWidget(self._tabs, stretch=1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def append_event(self, category: str, message: str) -> None:
        """Forward event to the internal EventLogWidget."""
        self.event_log.append_event(category, message)

    def append_line(self, line: str) -> None:
        """Forward raw line to the internal EventLogWidget."""
        self.event_log.append_line(line)

    def clear_log(self) -> None:
        """Clear the internal event log."""
        self.event_log.clear_log()

    def update_sessions(self, sessions: dict) -> None:
        """Refresh the Active Sessions tab."""
        sorted_sessions = sorted(
            sessions.values(), key=lambda s: s.created_at, reverse=True
        )
        self._sessions_table.setRowCount(len(sorted_sessions))
        for row_idx, session in enumerate(sorted_sessions):
            ttl_text = (
                f"{session.ttl_remaining():>3}s"
                if session.state == "ACTIVE"
                else "-"
            )
            self._sessions_table.setItem(
                row_idx, 0, QTableWidgetItem(session.transaction_id)
            )
            self._sessions_table.setItem(
                row_idx, 1, QTableWidgetItem(session.operation_type)
            )
            self._sessions_table.setItem(row_idx, 2, QTableWidgetItem(session.state))
            self._sessions_table.setItem(row_idx, 3, QTableWidgetItem(ttl_text))
            self._sessions_table.setItem(
                row_idx, 4, QTableWidgetItem(session.seat_summary[:80])
            )

    def update_sold_seats(self, sold_coords: set) -> None:
        """Refresh the Sold Seats tab with confirmed seat coordinates."""
        if not sold_coords:
            self._sold_list.setText("No confirmed seats yet.")
            return

        by_section: Dict[str, List[str]] = {}
        for sec, r, c in sold_coords:
            by_section.setdefault(sec, []).append(f"({r},{c})")

        lines = []
        for sec in ["VIP", "PREFERENTIAL", "GENERAL"]:
            if sec in by_section:
                coords = ", ".join(by_section[sec])
                lines.append(f"<b>{sec}</b>: {coords}")
        self._sold_list.setText("<br>".join(lines))

    def update_section_stats(self, snapshot: dict) -> None:
        """Refresh the Section Stats tab with all-section counts."""
        for row_idx, sec in enumerate(["VIP", "PREFERENTIAL", "GENERAL"]):
            counts = snapshot.get(sec, {})
            self._stats_table.setItem(row_idx, 0, QTableWidgetItem(sec))
            self._stats_table.setItem(
                row_idx, 1, QTableWidgetItem(str(counts.get("available", 0)))
            )
            self._stats_table.setItem(
                row_idx, 2, QTableWidgetItem(str(counts.get("reserved", 0)))
            )
            self._stats_table.setItem(
                row_idx, 3, QTableWidgetItem(str(counts.get("sold", 0)))
            )


class LogTailer:
    """Tails a server log file, returning only new lines since last read.

    Ported verbatim from frontend_tui/app.py lines 48-79. Maintains an
    internal file position to avoid re-reading old content.

    Attributes:
        file_path: Path to the log file being tailed.
        position: Current byte offset in the file.
    """

    def __init__(self, file_path: Path) -> None:
        """Initialize the tailer and seek to end of file.

        Args:
            file_path: Path to the log file to tail.
        """
        self.file_path = file_path
        self.position = 0
        self.reset_position_to_eof()

    def set_file_path(self, file_path: Path) -> None:
        """Change the log file being tailed.

        Args:
            file_path: New log file path.
        """
        self.file_path = file_path
        self.position = 0
        self.reset_position_to_eof()

    def reset_position_to_eof(self) -> None:
        """Seek internal position to the current end of file."""
        try:
            with self.file_path.open("r", encoding="utf-8") as handle:
                handle.seek(0, 2)
                self.position = handle.tell()
        except FileNotFoundError:
            self.position = 0

    def read_new_lines(self, max_lines: int = 100) -> List[str]:
        """Read new lines since the last read, up to max_lines.

        Args:
            max_lines: Maximum number of lines to return (most recent).

        Returns:
            List of new non-empty log lines, stripped of trailing newlines.
        """
        try:
            with self.file_path.open("r", encoding="utf-8") as handle:
                handle.seek(self.position)
                lines = handle.readlines()
                self.position = handle.tell()
        except FileNotFoundError:
            return []
        cleaned = [line.rstrip("\n") for line in lines if line.strip()]
        if len(cleaned) > max_lines:
            return cleaned[-max_lines:]
        return cleaned
