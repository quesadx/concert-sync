"""Connection panel widget for host/port input and session management.

Provides UI controls for connecting to the ConcertSync server with
user identity. Active sessions are auto-loaded on connect via the
QUERY_SEAT_MAP response — no manual session claiming needed.
"""

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ConnectionPanel(QWidget):
    """Connection controls with user ID, host, and port inputs.

    Emits:
        connect_requested(host, port): When user clicks Connect.
    """

    connect_requested = Signal(str, int)  # host, port

    def __init__(self) -> None:
        """Initialize connection panel with user ID, host/port, and connect button."""
        super().__init__()
        layout = QVBoxLayout(self)

        # ── User ID row ──────────────────────────────────────────────────────
        user_layout = QHBoxLayout()
        self.user_id_input = QLineEdit()
        self.user_id_input.setPlaceholderText("User ID")
        user_layout.addWidget(QLabel("User ID:"))
        user_layout.addWidget(self.user_id_input)
        layout.addLayout(user_layout)

        # ── Host/Port row ────────────────────────────────────────────────────
        conn_layout = QHBoxLayout()
        self.host_input = QLineEdit("localhost")
        self.host_input.setPlaceholderText("Host")
        conn_layout.addWidget(QLabel("Host:"))
        conn_layout.addWidget(self.host_input)
        self.port_input = QLineEdit("9999")
        self.port_input.setPlaceholderText("Port")
        conn_layout.addWidget(QLabel("Port:"))
        conn_layout.addWidget(self.port_input)
        layout.addLayout(conn_layout)

        # ── Connect button ───────────────────────────────────────────────────
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect)
        layout.addWidget(self.connect_btn)

    def _on_connect(self) -> None:
        """Handle Connect button click.

        Reads host and port from input fields. Falls back to 'localhost'
        if host is empty. Does NOT emit if port is not a valid integer.
        """
        host = self.host_input.text().strip() or "localhost"
        try:
            port = int(self.port_input.text().strip())
        except ValueError:
            return
        self.connect_requested.emit(host, port)

    def set_session_id(self, session_id: str) -> None:
        """Persist the session ID to QSettings for cross-session continuity.

        Args:
            session_id: The session identifier string from the server.
        """
        QSettings("ConcertSync", "PySide6GUI").setValue("session_id", session_id)
