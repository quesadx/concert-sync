"""Transaction panel widget for confirm/cancel and tracked session display.

Provides TX ID input with Confirm/Cancel buttons, a session table showing
active tracked sessions, and a TTL countdown label.

Port of frontend_tui/app.py _render_session_table() lines 980-999 and
TrackedSession-based session tracking from lines 29-45.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class TransactionPanel(QWidget):
    """Transaction management with session tracking table and TTL display.

    Emits:
        confirm_requested(transaction_id): When user clicks Confirm.
        cancel_requested(transaction_id): When user clicks Cancel.
    """

    confirm_requested = Signal(str)  # tx_id
    cancel_requested = Signal(str)  # tx_id

    def __init__(self) -> None:
        """Initialize the transaction panel with all controls."""
        super().__init__()
        layout = QVBoxLayout(self)

        # ── Transaction ID input row ─────────────────────────────────────────
        tx_layout = QHBoxLayout()
        self.tx_input = QLineEdit()
        self.tx_input.setPlaceholderText("Transaction ID")
        tx_layout.addWidget(QLabel("TX ID:"))
        tx_layout.addWidget(self.tx_input)
        layout.addLayout(tx_layout)

        # ── Action buttons ───────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        self.confirm_btn = QPushButton("Confirm")
        self.confirm_btn.clicked.connect(
            lambda: self.confirm_requested.emit(self.tx_input.text().strip())
        )
        btn_layout.addWidget(self.confirm_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(
            lambda: self.cancel_requested.emit(self.tx_input.text().strip())
        )
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        # ── Session table ────────────────────────────────────────────────────
        self.session_table = QTableWidget(0, 5)
        self.session_table.setHorizontalHeaderLabels(
            ["Transaction", "Type", "State", "TTL", "Seats"]
        )
        layout.addWidget(self.session_table)

        # ── TTL countdown label ──────────────────────────────────────────────
        self.ttl_label = QLabel("TTL: --")
        layout.addWidget(self.ttl_label)

    def update_sessions(self, sessions: dict) -> None:
        """Update the tracked sessions table from a session dict.

        Sorts sessions by created_at descending and displays the 30 most
        recent. Shows TTL countdown for ACTIVE sessions, '-' for others.

        Args:
            sessions: Dict mapping transaction_id to TrackedSession objects.
        """
        sorted_sessions = sorted(
            sessions.values(), key=lambda s: s.created_at, reverse=True
        )
        self.session_table.setRowCount(len(sorted_sessions[:30]))
        for row_idx, session in enumerate(sorted_sessions[:30]):
            ttl_text = (
                f"{session.ttl_remaining():>3}s" if session.state == "ACTIVE" else "-"
            )
            self.session_table.setItem(
                row_idx, 0, QTableWidgetItem(session.transaction_id)
            )
            self.session_table.setItem(
                row_idx, 1, QTableWidgetItem(session.operation_type)
            )
            self.session_table.setItem(row_idx, 2, QTableWidgetItem(session.state))
            self.session_table.setItem(row_idx, 3, QTableWidgetItem(ttl_text))
            self.session_table.setItem(
                row_idx, 4, QTableWidgetItem(session.seat_summary)
            )
