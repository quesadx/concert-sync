"""Color-coded, timestamped event log widget with local/remote distinction.

EventLogWidget: Read-only QTextEdit that appends timestamped entries with
color-coded category prefixes (LOCAL green, REMOTE orange, ERROR red,
SERVER grey, EXPIRE brown).

LogTailer: Tails a server log file, returning only new lines since the
last read. Ported verbatim from frontend_tui/app.py lines 48-79.
"""

from datetime import datetime
from pathlib import Path
from typing import List

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit

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

    def append_line(self, line: str) -> None:
        """Append a raw server log line (called during log tailing).

        Args:
            line: A raw log line from the server log file.
        """
        self.moveCursor(QTextCursor.End)
        self.insertPlainText(line + "\n")
        self.ensureCursorVisible()


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
