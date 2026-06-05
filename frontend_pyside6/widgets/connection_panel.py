"""Connection panel widget for host/port input and session management.

Provides UI controls for connecting to the ConcertSync server with
user identity. Active sessions are auto-loaded on connect via the
QUERY_SEAT_MAP response — no manual session claiming needed.

Includes a visual connection status indicator and modern input styling.
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

    Attributes:
        user_id_input: QLineEdit for the user's identifier.
        host_input: QLineEdit for the server hostname.
        port_input: QLineEdit for the server port.
        connect_btn: QPushButton that triggers connection.
        status_label: QLabel showing connection status (connected/disconnected).
    """

    connect_requested = Signal(str, int)  # host, port

    def __init__(self) -> None:
        """Initialize connection panel with user ID, host/port, and connect button."""
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Title ────────────────────────────────────────────────────────────
        title = QLabel("ConcertSync Connection")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #f5a623;")
        layout.addWidget(title)

        # ── User ID row ──────────────────────────────────────────────────────
        user_layout = QHBoxLayout()
        user_label = QLabel("User ID:")
        user_label.setStyleSheet("font-weight: 600; color: #d8d8e8;")
        self.user_id_input = QLineEdit()
        self.user_id_input.setPlaceholderText("Enter your name or number (auto-generated if empty)")
        self.user_id_input.setStyleSheet("QLineEdit { font-weight: 500; }")
        user_layout.addWidget(user_label)
        user_layout.addWidget(self.user_id_input)
        layout.addLayout(user_layout)

        # ── Host/Port row ────────────────────────────────────────────────────
        conn_layout = QHBoxLayout()
        host_label = QLabel("Host:")
        host_label.setStyleSheet("font-weight: 600; color: #d8d8e8;")
        self.host_input = QLineEdit("localhost")
        self.host_input.setPlaceholderText("Host")
        conn_layout.addWidget(host_label)
        conn_layout.addWidget(self.host_input)
        port_label = QLabel("Port:")
        port_label.setStyleSheet("font-weight: 600; color: #d8d8e8;")
        self.port_input = QLineEdit("9999")
        self.port_input.setPlaceholderText("Port")
        self.port_input.setMaximumWidth(80)
        conn_layout.addWidget(port_label)
        conn_layout.addWidget(self.port_input)
        layout.addLayout(conn_layout)

        # ── Status + Connect button row ─────────────────────────────────────
        action_layout = QHBoxLayout()
        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("status-disconnected")
        self.status_label.setStyleSheet(
            "font-weight: bold; color: #ef5350; font-size: 11px;"
        )
        action_layout.addWidget(self.status_label)
        action_layout.addStretch()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("accent-btn")
        self.connect_btn.setStyleSheet(
            "QPushButton { background-color: #f5a623; color: #1a1a2e; "
            "border: 1px solid #d4a84b; border-radius: 6px; padding: 6px 16px; "
            "font-weight: bold; }"
            "QPushButton:hover { background-color: #ffc44d; }"
        )
        self.connect_btn.clicked.connect(self._on_connect)
        action_layout.addWidget(self.connect_btn)
        layout.addLayout(action_layout)

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

    def set_connected(self, connected: bool, host: str = "", port: int = 0) -> None:
        """Update the visual connection status indicator.

        Args:
            connected: True if connected, False if disconnected.
            host: The connected host (for display).
            port: The connected port (for display).
        """
        if connected:
            self.status_label.setText(f"Connected to {host}:{port}")
            self.status_label.setStyleSheet(
                "font-weight: bold; color: #66bb6a; font-size: 11px;"
            )
            self.status_label.setObjectName("status-connected")
            self.connect_btn.setText("Disconnect")
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet(
                "font-weight: bold; color: #ef5350; font-size: 11px;"
            )
            self.status_label.setObjectName("status-disconnected")
            self.connect_btn.setText("Connect")

    def set_session_id(self, session_id: str) -> None:
        """Persist the session ID to QSettings for cross-session continuity.

        Args:
            session_id: The session identifier string from the server.
        """
        QSettings("ConcertSync", "PySide6GUI").setValue("session_id", session_id)
