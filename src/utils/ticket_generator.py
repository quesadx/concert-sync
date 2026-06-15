"""
Ticket generator for ConcertSync TXT ticket output (v1.0).

Generates human-readable text files with Unicode box-drawing formatting
for confirmed reservations.
"""

import datetime
import threading
from pathlib import Path
from typing import Any, List, Tuple


class TicketGenerator:
    """Generates QR code PNG and TXT ticket files for confirmed reservations.

    Produces paired output files (ticket_<id>.txt and ticket_<id>.png) in a
    tickets/ directory. All I/O errors are caught and logged via global_log;
    the method returns False on failure instead of raising.

    Args:
        global_log: Logger instance with ``append(event_type, message)``
    """

    def __init__(self, global_log: Any) -> None:
        self._log = global_log
        self._mutex = threading.Lock()
        self._tickets_dir = Path("tickets")

    def _ensure_dir(self) -> bool:
        """Create tickets directory if it does not exist (thread-safe)."""
        try:
            self._tickets_dir.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as e:
            self._log.append("ERROR", f"TicketGenerator: mkdir failed: {e}")
            return False

    @staticmethod
    def _format_seat(seat: Tuple[int, int]) -> str:
        row, col = seat
        col_letter = chr(65 + col)
        return f"F{row}-{col_letter}"

    @staticmethod
    def _format_timestamp(timestamp: float) -> str:
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _line(content: str) -> str:
        inner = 34
        return f"\u2551{content:<{inner}}\u2551\n"

    def _build_txt_content(
        self,
        ticket_id: str,
        section_name: str,
        seats: List[Tuple[int, int]],
        transaction_id: str,
        timestamp_str: str,
    ) -> str:
        inner = 34
        top = "\u2554" + "\u2550" * inner + "\u2557\n"
        sep = "\u2560" + "\u2550" * inner + "\u2563\n"
        bottom = "\u255a" + "\u2550" * inner + "\u255d\n"

        lines = [
            top,
            self._line("         CONCERT SYNC             "),
            self._line("      TICKET DE COMPRA            "),
            sep,
            self._line(f" TICKET: {ticket_id}"),
            self._line(f" FECHA:  {timestamp_str}"),
            self._line(f" ZONA:   {section_name}"),
            self._line(" ASIENTOS:"),
        ]
        for seat in seats:
            lines.append(self._line(f"   {self._format_seat(seat)}"))
        lines.append(self._line(f" TRANSACCI\u00d3N: {transaction_id}"))
        lines.append(self._line(" ESTADO:  CONFIRMADO"))
        lines.append(bottom)
        return "".join(lines)

    def _write_txt(self, path: Path, content: str) -> bool:
        try:
            path.write_text(content, encoding="utf-8")
            self._log.append(
                "TICKET",
                f"TXT ticket saved: {path}",
            )
            return True
        except OSError as e:
            self._log.append("ERROR", f"TicketGenerator: TXT write failed: {e}")
            return False

    def generate_ticket(
        self,
        ticket_id: str,
        section_name: str,
        seats: List[Tuple[int, int]],
        transaction_id: str,
        timestamp: float = None,
    ) -> bool:
        """Generate a TXT ticket file for a confirmed reservation.

        Produces one file in the tickets/ directory:
          - tickets/ticket_<lower_id>.txt (Unicode box-drawing format)

        Args:
            ticket_id: Human-readable ticket identifier (e.g., 'TKT-000001')
            section_name: Section display name (e.g., 'VIP', 'PREFERENTIAL')
            seats: List of (row, col) tuples representing reserved seats
            transaction_id: Server transaction ID for cross-reference
            timestamp: Optional Unix timestamp; uses current time if None

        Returns:
            True if both files were written successfully, False on any error
        """
        if not self._ensure_dir():
            return False

        lower_id = ticket_id.lower()
        txt_path = self._tickets_dir / f"ticket_{lower_id}.txt"

        if timestamp is None:
            timestamp = datetime.datetime.now().timestamp()
        timestamp_str = self._format_timestamp(timestamp)

        txt_content = self._build_txt_content(
            ticket_id, section_name, seats, transaction_id, timestamp_str,
        )

        with self._mutex:
            txt_ok = self._write_txt(txt_path, txt_content)

        return txt_ok
