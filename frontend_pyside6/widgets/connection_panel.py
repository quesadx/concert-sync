"""Connection panel widget for host/port input and session management.

Provides UI controls for connecting to the ConcertSync server with
user identity. The user ID is collected via a mandatory numeric login
dialog on startup. Active sessions are auto-loaded on connect via the
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
    """Connection controls with user display, host/port inputs, and connect.

    Emits:
        connect_requested(host, port): When user clicks Connect.
        change_user_requested(): When user clicks Change User.
    """

    connect_requested = Signal(str, int)  # host, port
    change_user_requested = Signal()  # request re-login

    def __init__(self) -> None:
        """Initialize connection panel with user label, host/port, and buttons."""
        super().__init__()
        layout = QVBoxLayout(self)

        # ── User identity row ───────────────────────────────────────────────
        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("User:"))

        self.user_label = QLabel("Not logged in")
        self.user_label.setStyleSheet(
            "font-weight: bold; color: #9ad4d6; padding: 2px 6px;"
            "background-color: #10171f; border-radius: 3px;"
        )
        user_layout.addWidget(self.user_label)
        user_layout.addStretch()

        self.change_user_btn = QPushButton("Change User")
        self.change_user_btn.clicked.connect(lambda: self.change_user_requested.emit())
        user_layout.addWidget(self.change_user_btn)
        layout.addLayout(user_layout)

        # ── Host/Port row ───────────────────────────────────────────────────
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

        # ── Connect button ──────────────────────────────────────────────────
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect)
        layout.addWidget(self.connect_btn)

    def set_user_id(self, user_id: str) -> None:
        """Update the displayed user ID label.

        Args:
            user_id: The user's numeric ID string.
        """
        self.user_label.setText(user_id)

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
