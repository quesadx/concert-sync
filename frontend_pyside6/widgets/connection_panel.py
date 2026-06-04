"""Connection panel widget for host/port input and session management.

Provides UI controls for connecting to the ConcertSync server, displaying
the active session ID, and reclaiming a previous session after disconnect.

Port of frontend_tui/app.py _connect_client() lines 352-380 and
compose connection widgets lines 128-139, extended with session
persistence (BLOCKER #1, #2: SESS-01, SESS-02).
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
    """Connection controls with host/port input and session management.

    Emits:
        connect_requested(host, port): When user clicks Connect.
        reclaim_requested(session_id): When user clicks Reclaim Session.
    """

    connect_requested = Signal(str, int)  # host, port
    reclaim_requested = Signal(str)  # session_id

    def __init__(self) -> None:
        """Initialize connection panel with all input fields and buttons."""
        super().__init__()
        layout = QVBoxLayout(self)

        # ── User ID row (BLOCKER #1 — enables OWN_RESERVED detection) ────────
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

        # ── Session ID display ───────────────────────────────────────────────
        self.session_label = QLabel("Session ID: --")
        self.session_label.setWordWrap(True)
        layout.addWidget(self.session_label)

        # ── Reclaim Session row (BLOCKER #2 — SESS-01/SESS-02) ───────────────
        reclaim_layout = QHBoxLayout()
        self.session_id_input = QLineEdit()
        self.session_id_input.setPlaceholderText("Session ID")
        reclaim_layout.addWidget(QLabel("Session ID:"))
        reclaim_layout.addWidget(self.session_id_input)
        self.reclaim_button = QPushButton("Reclaim Session")
        self.reclaim_button.clicked.connect(self._on_reclaim)
        reclaim_layout.addWidget(self.reclaim_button)
        layout.addLayout(reclaim_layout)

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

    def _on_reclaim(self) -> None:
        """Handle Reclaim Session button click.

        Reads session ID from input field and emits reclaim_requested
        if the field is non-empty.
        """
        session_id = self.session_id_input.text().strip()
        if session_id:
            self.reclaim_requested.emit(session_id)

    def set_session_id(self, session_id: str) -> None:
        """Update the session ID display label and persist to QSettings.

        Args:
            session_id: The session identifier string from the server.
        """
        self.session_label.setText(f"Session ID: {session_id}")
        QSettings("ConcertSync", "PySide6GUI").setValue("session_id", session_id)

    def set_stored_session_id(self) -> None:
        """Restore a previously stored session ID from QSettings.

        Reads the 'session_id' value from QSettings and pre-fills the
        session_id_input field if a value exists. Called at startup to
        enable one-click session reclamation.
        """
        stored = QSettings("ConcertSync", "PySide6GUI").value("session_id")
        if stored:
            self.session_id_input.setText(stored)
