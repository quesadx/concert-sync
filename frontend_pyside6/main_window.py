"""PySide6 main window for the ConcertSync seat reservation GUI.

Click-to-reserve: clicking an AVAILABLE seat immediately reserves it via
the server (RESERVE action). Own seats show as blue (OWN_RESERVED), other
users' reservations show as orange (RESERVED). Live polling at 1s updates
the seat map across all connected clients.
"""

from __future__ import annotations

import socket
import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from frontend_pyside6.models.tracked_session import TrackedSession
from frontend_pyside6.workers.network_worker import (
    CancelWorker,
    ConfirmWorker,
    PollWorker,
    ReadNotificationWorker,
    ReserveSelectedWorker,
    ReserveWorker,
    SubscribeNotificationsWorker,
    run_worker,
)
from frontend_pyside6.widgets.connection_panel import ConnectionPanel
from frontend_pyside6.widgets.event_log import ActivityDialog, LogTailer
from frontend_pyside6.widgets.seat_map_widget import SeatMapWidget
from src.client.concert_client import ConcertClient, ConcertClientError
from src.utils.config import SECTION_CONFIG
from src.utils.enums import Section


class ConcertMainWindow(QMainWindow):
    """Main window for the ConcertSync PySide6 client.

    Mirrors ConcertTextualApp (frontend_tui/app.py) state and behavior:
    client connection, 1-second QTimer polling, seat click toggling,
    unified batch reservation, confirm/cancel, and session tracking.

    Signals:
        _refresh_complete: Emitted internally for thread-safe poll dispatch.
        _refresh_failed: Emitted internally for poll error dispatch.

    Attributes:
        client: Connected ConcertClient instance (None if disconnected).
        user_id: The user's identifier (auto-generated UUID if empty).
        connected_host: Hostname of the connected server.
        connected_port: Port of the connected server.
        sessions: Dict mapping transaction_id to TrackedSession.
        _click_inflight: Set of (section, row, col) being reserved (pending server response).
        section_snapshot: Last known section availability counts.
        seat_map_snapshot: Last known full seat map grid.
        own_reserved_coords: Set of (section, row, col) tuples owned by this user.
        server_disconnected: Whether the server notified a disconnect.
    """

    _refresh_complete = Signal(dict, dict, object)  # sections, seat_map_payload, user_session
    _refresh_failed = Signal(str)  # error message

    def __init__(self) -> None:
        """Initialize the main window, state, layout, and polling timer."""
        super().__init__()
        self.setWindowTitle("ConcertSync — Seat Reservation Dashboard")
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)

        # ── Stylesheet (WARNING #1 fix) ──────────────────────────────────
        stylesheet_path = Path(__file__).parent / "resources" / "styles.qss"
        stylesheet = stylesheet_path.read_text(encoding="utf-8")
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet)

        # ── Client state (mirrors ConcertTextualApp.__init__) ─────────────
        self.client: Optional[ConcertClient] = None
        self.user_id: Optional[str] = None
        self.connected_host: str = "localhost"
        self.connected_port: int = 9999
        self.sessions: Dict[str, TrackedSession] = {}
        self._click_inflight: Set[tuple[str, int, int]] = set()
        self.section_snapshot = {
            "VIP": {"available": 0, "reserved": 0, "sold": 0},
            "PREFERENTIAL": {"available": 0, "reserved": 0, "sold": 0},
            "GENERAL": {"available": 0, "reserved": 0, "sold": 0},
        }
        self.seat_map_snapshot = self._build_empty_seat_map()
        self.own_reserved_coords: Set[tuple[str, int, int]] = set()
        self.own_sold_coords: Set[tuple[str, int, int]] = set()
        self.server_disconnected: bool = False
        self._closing: bool = False

        # ── Log buffer for replaying events into the log dialog ────────────
        self._log_buffer: list[tuple[str, str]] = []
        self._log_buffer_max = 200
        self._notif_sock: socket.socket | None = None

        # ── Log tailer (mirrors TUI LogTailer init) ───────────────────────
        self.log_tailer = LogTailer(Path("logs/system.log"))

        # ── Pop-up activity dialog (separate window, not embedded) ──────────
        self.log_dialog: ActivityDialog | None = None

        self._setup_ui()
        self._setup_polling()

    # ════════════════════════════════════════════════════════════════════════
    # Layout
    # ════════════════════════════════════════════════════════════════════════

    def _setup_ui(self) -> None:
        """Build the full dashboard layout and wire all signal-slot connections."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ═══ TOP TOOLBAR ═══════════════════════════════════════════════════
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setSpacing(16)
        toolbar_layout.setContentsMargins(20, 10, 20, 10)

        # Title area: vertical stack for title + subtitle
        title_area = QVBoxLayout()
        title_area.setSpacing(0)
        title_area.setContentsMargins(0, 0, 0, 0)

        self.header_title = QLabel("ConcertSync")
        self.header_title.setObjectName("header-title")
        title_area.addWidget(self.header_title)

        self.header_subtitle = QLabel("Seat Reservation System")
        self.header_subtitle.setObjectName("header-subtitle")
        title_area.addWidget(self.header_subtitle)

        toolbar_layout.addLayout(title_area)

        toolbar_layout.addStretch()

        self._toolbar_status = QLabel("Not connected")
        self._toolbar_status.setObjectName("status-disconnected")
        toolbar_layout.addWidget(self._toolbar_status)

        self._toolbar_user = QLabel("")
        self._toolbar_user.setObjectName("section-label")
        toolbar_layout.addWidget(self._toolbar_user)

        main_layout.addWidget(toolbar)

        # ═══ MAIN SPLITTER (left control panel | seat map viewer) ═══════════
        main_splitter = QSplitter(Qt.Horizontal)

        # ═══ LEFT CONTROL PANEL ══════════════════════════════════════════════
        left_panel_widget = QWidget()
        left_panel = QVBoxLayout(left_panel_widget)
        left_panel.setSpacing(16)
        left_panel.setContentsMargins(20, 20, 20, 20)
        left_panel_widget.setMinimumWidth(340)

        # ── Section Switcher ──────────────────────────────────────────────
        switcher_label = QLabel("Section")
        switcher_label.setObjectName("section-label")
        left_panel.addWidget(switcher_label)

        switcher_layout = QHBoxLayout()
        switcher_layout.setSpacing(6)
        self._section_buttons: Dict[str, QPushButton] = {}
        section_meta = {
            "VIP": ("VIP", "#3584e4"),
            "PREFERENTIAL": ("Preferential", "#62a0ea"),
            "GENERAL": ("General", "#9141ac"),
        }
        for sec_name, (label, accent) in section_meta.items():
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(
                f"QPushButton:checked {{ background-color: {accent}; "
                f"border-color: {accent}; }}"
            )
            btn.clicked.connect(lambda checked, s=sec_name: self._switch_section(s))
            switcher_layout.addWidget(btn)
            self._section_buttons[sec_name] = btn
        left_panel.addLayout(switcher_layout)

        left_panel.addSpacing(8)

        # ── Connection ────────────────────────────────────────────────────
        conn_label = QLabel("Connection")
        conn_label.setObjectName("section-label")
        left_panel.addWidget(conn_label)
        self.connection_panel = ConnectionPanel()
        left_panel.addWidget(self.connection_panel)

        left_panel.addSpacing(8)

        # ── Reservation Actions ────────────────────────────────────────────
        action_label = QLabel("Manage Reservation")
        action_label.setObjectName("section-label")
        left_panel.addWidget(action_label)

        tx_layout = QHBoxLayout()
        self.tx_input = QLineEdit()
        self.tx_input.setPlaceholderText("Transaction ID")
        tx_layout.addWidget(self.tx_input)
        left_panel.addLayout(tx_layout)

        btn_row = QHBoxLayout()
        self.confirm_btn = QPushButton("Confirm")
        self.confirm_btn.clicked.connect(lambda: self._on_confirm(self.tx_input.text().strip()))
        btn_row.addWidget(self.confirm_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(lambda: self._on_cancel(self.tx_input.text().strip()))
        btn_row.addWidget(self.cancel_btn)
        left_panel.addLayout(btn_row)

        left_panel.addSpacing(8)

        # ── TTL Countdown ──────────────────────────────────────────────────
        ttl_label = QLabel("Reservation Timer")
        ttl_label.setObjectName("section-label")
        left_panel.addWidget(ttl_label)
        self._ttl_display = QLabel("No active reservation")
        self._ttl_display.setObjectName("ttl-display")
        self._ttl_display.setAlignment(Qt.AlignCenter)
        left_panel.addWidget(self._ttl_display)

        left_panel.addSpacing(8)

        # ── Activity Center button ──────────────────────────────────────────
        self.view_logs_btn = QPushButton("Activity Center")
        self.view_logs_btn.clicked.connect(self._show_log_window)
        left_panel.addWidget(self.view_logs_btn)

        left_panel.addStretch()
        main_splitter.addWidget(left_panel_widget)

        # ═══ RIGHT PANEL: single section viewer via QStackedWidget ══════════
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(10)
        right_layout.setContentsMargins(12, 12, 12, 12)

        # Color legend
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(8)
        for color, text in [
            ("#66bb6a", "Available"),
            ("#29b6f6", "Yours"),
            ("#ffa726", "Reserved"),
            ("#ef5350", "Sold"),
            ("#ab47bc", "Pending"),
        ]:
            swatch = QLabel("   ")
            swatch.setStyleSheet(f"background-color: {color};")
            swatch.setObjectName("seat-legend-swatch")
            legend_layout.addWidget(swatch)
            lbl = QLabel(text)
            lbl.setObjectName("legend-text")
            legend_layout.addWidget(lbl)
        legend_layout.addStretch()
        right_layout.addLayout(legend_layout)

        # Stacked widget holds one scrollable seat map per section
        self._section_stack = QStackedWidget()
        self.seat_maps: Dict[str, SeatMapWidget] = {}
        cell_sizes = {"VIP": 52, "PREFERENTIAL": 40, "GENERAL": 28}
        for section_name in ["VIP", "PREFERENTIAL", "GENERAL"]:
            section = Section[section_name]
            cfg = SECTION_CONFIG[section]
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("border: none; background-color: transparent;")
            sm = SeatMapWidget(
                section_name, cfg["rows"], cfg["cols"],
                cell_size=cell_sizes[section_name],
            )
            sm.seat_clicked.connect(self._on_seat_clicked)
            self.seat_maps[section_name] = sm
            scroll.setWidget(sm)
            self._section_stack.addWidget(scroll)
        right_layout.addWidget(self._section_stack, stretch=1)
        main_splitter.addWidget(right_widget)

        main_splitter.setSizes([400, 1040])
        main_splitter.setHandleWidth(2)
        main_layout.addWidget(main_splitter, stretch=1)

        # ── Status bar ────────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Not connected")
        self.setStatusBar(self.status_bar)

        # ── Signal-slot wiring ────────────────────────────────────────────
        self.connection_panel.connect_requested.connect(self._connect_client)
        self.connection_panel.disconnect_requested.connect(self._disconnect_client)

        # Default to VIP section
        self._switch_section("VIP")

    def _switch_section(self, section_name: str) -> None:
        """Switch the main viewer to the selected section."""
        for sn, btn in self._section_buttons.items():
            btn.setChecked(sn == section_name)
        idx = {"VIP": 0, "PREFERENTIAL": 1, "GENERAL": 2}.get(section_name, 0)
        self._section_stack.setCurrentIndex(idx)
        self._active_section = section_name

    def _show_log_window(self) -> None:
        """Open the Activity Center dialog."""
        if self.log_dialog is None or not self.log_dialog.isVisible():
            self.log_dialog = ActivityDialog(self)
            for cat, msg in self._log_buffer:
                self.log_dialog.append_event(cat, msg)
            self.log_dialog.update_sessions(self.sessions)
            self.log_dialog.update_sold_seats(self.own_sold_coords)
            self.log_dialog.update_section_stats(self.section_snapshot)
            self.log_dialog.show()
        else:
            self.log_dialog.raise_()
            self.log_dialog.activateWindow()

    # ════════════════════════════════════════════════════════════════════════
    # Connection
    # ════════════════════════════════════════════════════════════════════════

    @Slot(str, int)
    def _connect_client(self, host: str = "localhost", port: int = 9999) -> None:
        """Connect to the ConcertSync server and perform initial query.

        Reads user_id from the ConnectionPanel input field.
        Auto-generates a UUID-based user_id if the input is empty. The server
        requires a non-empty user_id for OWN_RESERVED seat detection.

        Args:
            host: Server hostname or IP address.
            port: Server TCP port.
        """
        # ── Read user_id, auto-generate if empty ─────────────────────────
        user_id = self.connection_panel.user_id_input.text().strip()
        if not user_id:
            user_id = f"user_{uuid4().hex[:8]}"

        # Clear state from any previous user session to prevent stale OWN_RESERVED highlights
        self.own_reserved_coords.clear()
        self.sessions.clear()
        self._click_inflight.clear()

        self.user_id = user_id

        self.client = ConcertClient(user_id=self.user_id, host=host, port=port)
        self.connected_host = host
        self.connected_port = port

        try:
            self.client.query()  # Test connection
            self._toolbar_status.setText(f"Connected to {host}:{port}")
            self._toolbar_status.setObjectName("status-connected")
            self._toolbar_user.setText(f"User: {self.user_id}")
            self.status_bar.showMessage(f"Connected to {host}:{port} as {self.user_id}")
            self.connection_panel.set_connected(True, host, port)
            self._log_event("LOCAL", f"Connected to {host}:{port}")

            # Subscribe to push notifications in background
            self._subscribe_notifications()

            self._refresh_all()
        except ConcertClientError as exc:
            self.client = None
            self._toolbar_status.setText("Not connected")
            self._toolbar_status.setObjectName("status-disconnected")
            self._toolbar_user.setText("")
            self.connection_panel.set_connected(False)
            self.status_bar.showMessage(f"Connection failed: {exc}")
            self._log_event("ERROR", f"Connection failed: {exc}")

    @Slot()
    def _disconnect_client(self) -> None:
        """Disconnect from the server and reset all client-side state.

        Clears the client reference, tracked sessions, pending selections,
        own reserved coordinates, and all rendered widgets. Mirrors the
        TUI disconnect behavior.
        """
        if self._notif_sock is not None:
            try:
                self._notif_sock.close()
            except OSError:
                pass
            self._notif_sock = None
        self.client = None
        self.sessions.clear()
        self._click_inflight.clear()
        self.own_reserved_coords.clear()
        self.section_snapshot = {
            "VIP": {"available": 0, "reserved": 0, "sold": 0},
            "PREFERENTIAL": {"available": 0, "reserved": 0, "sold": 0},
            "GENERAL": {"available": 0, "reserved": 0, "sold": 0},
        }
        self.seat_map_snapshot = self._build_empty_seat_map()

        self._toolbar_status.setText("Not connected")
        self._toolbar_status.setObjectName("status-disconnected")
        self._toolbar_user.setText("")
        self.connection_panel.set_connected(False)
        self.status_bar.showMessage("Disconnected")
        self._log_event("LOCAL", "Disconnected from server")
        self._render_all()

    # ════════════════════════════════════════════════════════════════════════
    # Polling
    # ════════════════════════════════════════════════════════════════════════

    def _setup_polling(self) -> None:
        """Start the 1-second QTimer for seat map, section polling, and TTL countdown."""
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_tick)
        self.poll_timer.start(1000)  # 1 second

        # Live TTL countdown timer (updates every second independently of polls)
        self.ttl_timer = QTimer(self)
        self.ttl_timer.timeout.connect(self._update_live_ttl)
        self.ttl_timer.start(1000)  # 1 second

    def _poll_tick(self) -> None:
        """Timer callback — dispatches network poll to a background thread.

        Never runs network calls on the main thread. Creates a PollWorker
        and dispatches via run_worker() which uses a daemon threading.Thread.
        """
        if self.client is None:
            return
        worker = PollWorker(self.client)
        worker.finished.connect(self._on_poll_success)
        worker.error.connect(self._on_poll_error)
        run_worker(worker)

        # Also check for pending push notifications (non-blocking)
        if self._notif_sock is not None:
            self._read_pending_notifications()

    def _read_pending_notifications(self) -> None:
        """Read any pending push notifications from the subscription socket."""
        worker = ReadNotificationWorker(self._notif_sock)
        worker.finished.connect(self._on_notification)
        run_worker(worker)

    def _subscribe_notifications(self) -> None:
        """Subscribe to push notifications in background."""
        if self.client is None:
            return
        worker = SubscribeNotificationsWorker(self.client)
        worker.finished.connect(self._on_subscribe_success)
        worker.error.connect(self._on_subscribe_error)
        run_worker(worker)

    @Slot(object)
    def _on_subscribe_success(self, sub_sock: socket.socket) -> None:
        """Store the subscription socket for notification reading."""
        if self._closing:
            return
        self._notif_sock = sub_sock
        self._log_event("LOCAL", "Subscribed to push notifications")

    @Slot(str)
    def _on_subscribe_error(self, error_msg: str) -> None:
        """Log subscription failure (non-fatal)."""
        if self._closing:
            return
        self._log_event("ERROR", f"Notification subscribe failed: {error_msg}")

    @Slot(dict)
    def _on_notification(self, notif: dict) -> None:
        """Display a push notification in the event log and notification feed."""
        if self._closing:
            return
        ntype = notif.get("notification_type", "UNKNOWN")
        msg = notif.get("message", "")
        self._log_event("NOTIFICATION", f"[{ntype}] {msg}")

    @Slot(dict, dict, object)
    def _on_poll_success(self, sections: dict, seat_map_payload: dict, user_session: object) -> None:
        if self._closing:
            return
        self.section_snapshot = sections
        self.seat_map_snapshot = seat_map_payload
        self._sync_user_session(user_session)
        self._render_all()

    def _sync_user_session(self, user_session: object) -> None:
        if user_session is None:
            self.own_reserved_coords.clear()
            return

        session_id = user_session.get("session_id", "")
        seat_list = user_session.get("seats", [])
        ttl_secs = user_session.get("ttl_secs", 300)
        last_activity = user_session.get("last_activity", 0)

        if not session_id or not seat_list:
            self.own_reserved_coords.clear()
            return

        session_coords: Set[tuple[str, int, int]] = set()
        seat_summary_parts: list[str] = []
        for s in seat_list:
            coord = (s["section"], s["row"], s["col"])
            session_coords.add(coord)
            seat_summary_parts.append(f"{s['section']}({s['row']},{s['col']})")
        self.own_reserved_coords = session_coords
        seat_summary = ", ".join(seat_summary_parts)

        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.created_at = last_activity
            session.seats = seat_list
        else:
            session = TrackedSession(
                transaction_id=session_id,
                operation_type="AUTO_LOADED",
                seat_summary=seat_summary,
                ttl_seconds=ttl_secs,
                created_at=last_activity,
            )
            session.seats = seat_list
            self.sessions[session_id] = session
            self.connection_panel.set_session_id(session_id)
            self._log_event("LOCAL", f"Auto-loaded session {session_id} with {len(seat_list)} seat(s)")

        self.tx_input.setText(session_id)

    @Slot(str)
    def _on_poll_error(self, error_msg: str) -> None:
        if self._closing:
            return
        self.status_bar.showMessage(f"Poll error: {error_msg}")
        self._toolbar_status.setText("Disconnected")
        self._toolbar_status.setObjectName("status-disconnected")
        self.connection_panel.set_connected(False)
        self._log_event("ERROR", f"Poll failed: {error_msg}")

    def _update_live_ttl(self) -> None:
        """Update the TTL countdown display every second.

        Re-renders the TTL label and dialog session table so that ACTIVE session
        countdowns decrease smoothly between server polls. Lightweight:
        does NOT trigger network calls or re-render the seat map.
        """
        if self.log_dialog is not None and self.log_dialog.isVisible():
            self.log_dialog.update_sessions(self.sessions)

        if not self.sessions:
            self._set_ttl_display(None)
            return

        active_sessions = [
            s for s in self.sessions.values() if s.state == "ACTIVE"
        ]
        if active_sessions:
            active_sessions.sort(key=lambda s: s.ttl_remaining())
            self._set_ttl_display(active_sessions[0])
        else:
            self._set_ttl_display(None)

    # ════════════════════════════════════════════════════════════════════════
    # Seat Click (mirrors TUI on_data_table_cell_selected, app.py 259-301)
    # ════════════════════════════════════════════════════════════════════════

    @Slot(str, int, int, str)
    def _on_seat_clicked(self, section: str, row: int, col: int, state: str) -> None:
        if self._closing:
            return
        if (section, row, col) in self._click_inflight:
            return

        if state == "OWN_RESERVED":
            self.status_bar.showMessage(
                f"Your seat {section}({row},{col}) - use Confirm/Cancel in the panel"
            )
            return

        if state != "AVAILABLE":
            self.status_bar.showMessage(
                f"Seat {section}({row},{col}) - state: {state} (not available)"
            )
            return

        self._click_inflight.add((section, row, col))
        self._render_seat_map()
        self.status_bar.showMessage(f"Reserving {section}({row},{col})...")

        worker = ReserveWorker(self.client, section, row, col)
        worker.finished.connect(
            lambda resp, s=section, r=row, c=col: self._on_click_reserve_success(s, r, c, resp)
        )
        worker.error.connect(
            lambda msg, s=section, r=row, c=col: self._on_click_reserve_error(s, r, c, msg)
        )
        run_worker(worker)

    # ════════════════════════════════════════════════════════════════════════
    # Click-to-Reserve (inmediato al hacer clic)
    # ════════════════════════════════════════════════════════════════════════

    def _on_click_reserve_success(self, section: str, row: int, col: int, response: dict) -> None:
        if self._closing:
            return
        self._click_inflight.discard((section, row, col))
        tx_id = response["transaction_id"]
        ttl = response["ttl"]
        seat_summary = f"{section}({row},{col})"

        self._track_session(tx_id, "RESERVE", seat_summary, ttl)
        session = self.sessions.get(tx_id)
        if session is not None:
            coord = {"section": section, "row": row, "col": col}
            if coord not in session.seats:
                session.seats.append(coord)
        self.own_reserved_coords.add((section, row, col))
        self.tx_input.setText(tx_id)

        self._log_event("LOCAL", f"Reserved {seat_summary} — TX:{tx_id}")
        self.status_bar.showMessage(f"Reserved {seat_summary}")
        self._render_all()

    def _on_click_reserve_error(self, section: str, row: int, col: int, error_msg: str) -> None:
        if self._closing:
            return
        self._click_inflight.discard((section, row, col))
        self._render_seat_map()
        self.status_bar.showMessage(
            f"Could not reserve {section}({row},{col}) : {error_msg}"
        )
        self._log_event("ERROR", f"Click reserve failed: {error_msg}")

    # ════════════════════════════════════════════════════════════════════════
    # Session Tracking (mirrors TUI _track_session, app.py 549-565)
    # ════════════════════════════════════════════════════════════════════════

    def _track_session(
        self,
        transaction_id: str,
        operation_type: str,
        seat_summary: str,
        ttl: int,
    ) -> TrackedSession:
        """Track a reservation session, merging if same transaction_id exists.

        Mirrors ConcertTextualApp._track_session (app.py 549-565).

        Args:
            transaction_id: Unique transaction identifier.
            operation_type: Protocol action string (e.g., 'RESERVE_BATCH').
            seat_summary: Human-readable seat description.
            ttl: Reservation time-to-live in seconds.

        Returns:
            The TrackedSession instance (new or merged).
        """
        if transaction_id in self.sessions:
            existing = self.sessions[transaction_id]
            existing.seat_summary = (
                existing.seat_summary + ", " + seat_summary
                if existing.seat_summary
                else seat_summary
            )
            existing.created_at = time.time()
            existing.state = "ACTIVE"
            existing.ttl_seconds = ttl
            return existing

        session = TrackedSession(
            transaction_id=transaction_id,
            operation_type=operation_type,
            seat_summary=seat_summary,
            ttl_seconds=ttl,
            created_at=time.time(),
        )
        self.sessions[transaction_id] = session
        return session

    # ════════════════════════════════════════════════════════════════════════
    # Confirm
    # ════════════════════════════════════════════════════════════════════════

    @Slot(str)
    def _on_confirm(self, tx_id: str) -> None:
        if self._closing:
            return
        if not tx_id:
            self.status_bar.showMessage("No transaction ID to confirm")
            return
        worker = ConfirmWorker(self.client, tx_id)
        worker.finished.connect(self._on_confirm_success)
        worker.error.connect(self._on_confirm_error)
        run_worker(worker)

    @Slot(dict)
    def _on_confirm_success(self, response: dict) -> None:
        if self._closing:
            return
        tx_id = response.get("transaction_id", "")
        if tx_id in self.sessions:
            session = self.sessions[tx_id]
            session.state = "CONFIRMED"
            # Move confirmed seats from reserved to sold tracking
            for seat in session.seats:
                coord = (seat.get("section", ""), seat.get("row", 0), seat.get("col", 0))
                if coord[0]:  # valid section
                    self.own_reserved_coords.discard(coord)
                    self.own_sold_coords.add(coord)

        self._log_event("LOCAL", f"Confirmed TX:{tx_id}")
        self.status_bar.showMessage(f"Confirmed TX:{tx_id}")
        self._render_all()

    @Slot(str)
    def _on_confirm_error(self, error_msg: str) -> None:
        if self._closing:
            return
        self.status_bar.showMessage(f"Confirm failed: {error_msg}")
        self._log_event("ERROR", f"Confirm failed: {error_msg}")

    # ════════════════════════════════════════════════════════════════════════
    # Cancel
    # ════════════════════════════════════════════════════════════════════════

    @Slot(str)
    def _on_cancel(self, tx_id: str) -> None:
        if self._closing:
            return
        if not tx_id:
            self.status_bar.showMessage("No transaction ID to cancel")
            return
        worker = CancelWorker(self.client, tx_id)
        worker.finished.connect(self._on_cancel_success)
        worker.error.connect(self._on_cancel_error)
        run_worker(worker)

    @Slot(dict)
    def _on_cancel_success(self, response: dict) -> None:
        if self._closing:
            return
        tx_id = response.get("transaction_id", "")
        if tx_id in self.sessions:
            self.sessions[tx_id].state = "CANCELLED"

        self._log_event("LOCAL", f"Cancelled TX:{tx_id}")
        self.status_bar.showMessage(f"Cancelled TX:{tx_id}")
        self._render_all()

    @Slot(str)
    def _on_cancel_error(self, error_msg: str) -> None:
        if self._closing:
            return
        self.status_bar.showMessage(f"Cancel failed: {error_msg}")
        self._log_event("ERROR", f"Cancel failed: {error_msg}")

    # ════════════════════════════════════════════════════════════════════════
    # Rendering
    # ════════════════════════════════════════════════════════════════════════

    def _render_all(self) -> None:
        """Refresh all widgets: seat map, sessions, and log tail.

        Called on every poll success and after reservation/confirm/cancel.
        """
        self._render_seat_map()

        # Sync dialog contents if open
        if self.log_dialog is not None and self.log_dialog.isVisible():
            self.log_dialog.update_sessions(self.sessions)
            self.log_dialog.update_sold_seats(self.own_sold_coords)
            self.log_dialog.update_section_stats(self.section_snapshot)

        # Tail server log file for new lines — forward to dialog if open
        try:
            for line in self.log_tailer.read_new_lines(max_lines=50):
                self._log_buffer.append(("SERVER", line))
                if len(self._log_buffer) > self._log_buffer_max:
                    self._log_buffer.pop(0)
                if self.log_dialog is not None and self.log_dialog.isVisible():
                    self.log_dialog.append_line(line)
        except Exception:
            pass  # Log file may not exist yet

    def _render_seat_map(self) -> None:
        """Refresh all visible seat map widgets with current snapshot data."""
        pending_by_section: Dict[str, Set[tuple[int, int]]] = {
            "VIP": set(),
            "PREFERENTIAL": set(),
            "GENERAL": set(),
        }
        for s_name, r, c in self._click_inflight:
            pending_by_section[s_name].add((r, c))

        own_by_section: Dict[str, Set[tuple[int, int]]] = {
            "VIP": set(),
            "PREFERENTIAL": set(),
            "GENERAL": set(),
        }
        for s_name, r, c in self.own_reserved_coords:
            own_by_section[s_name].add((r, c))

        # Build TTL overlay dict per section from active sessions
        ttl_by_section: Dict[str, Dict[tuple[int, int], int]] = {
            "VIP": {},
            "PREFERENTIAL": {},
            "GENERAL": {},
        }
        for session in self.sessions.values():
            if session.state != "ACTIVE":
                continue
            ttl_remaining = session.ttl_remaining()
            for seat in session.seats:
                sec = seat.get("section", "")
                if sec in ttl_by_section:
                    ttl_by_section[sec][(seat["row"], seat["col"])] = ttl_remaining

        for section_name, widget in self.seat_maps.items():
            grid = self.seat_map_snapshot.get(section_name, [])
            if not grid:
                continue
            widget.update_grid(
                grid,
                pending_by_section.get(section_name, set()),
                own_by_section.get(section_name, set()),
                own_cell_ttl=ttl_by_section.get(section_name, {}),
            )

    def _set_ttl_display(self, session: object | None) -> None:
        """Update the prominent TTL countdown label."""
        if session is None or session.state != "ACTIVE":
            self._ttl_display.setText("No active reservation")
            self._ttl_display.setStyleSheet("color: #77767b;")
            return
        remaining = session.ttl_remaining()
        if remaining <= 0:
            self._ttl_display.setText("Reservation expired")
            self._ttl_display.setStyleSheet("color: #e01b24;")
            return
        mins, secs = divmod(remaining, 60)
        if remaining <= 30:
            color = "#e01b24"
        elif remaining <= 120:
            color = "#e66100"
        else:
            color = "#2ec27e"
        self._ttl_display.setText(f"{mins:02d}:{secs:02d}")
        self._ttl_display.setStyleSheet(f"color: {color};")

    # ════════════════════════════════════════════════════════════════════════
    # Utilities
    # ════════════════════════════════════════════════════════════════════════

    def _refresh_all(self) -> None:
        """Perform an immediate refresh (used on connect).

        Mirrors the TUI pattern: triggers a poll cycle to populate the UI
        synchronously through the normal poll path.
        """
        if self.client is None:
            return
        self._poll_tick()

    def _log_event(self, category: str, message: str) -> None:
        """Append a color-coded event to the event log buffer and dialog.

        Events are buffered so the log dialog can replay them when opened.
        If the log dialog is already open, the event is forwarded immediately.

        Args:
            category: Event category (LOCAL, REMOTE, ERROR, SERVER, EXPIRE).
            message: The event description text.
        """
        self._log_buffer.append((category, message))
        if len(self._log_buffer) > self._log_buffer_max:
            self._log_buffer.pop(0)
        if self.log_dialog is not None and self.log_dialog.isVisible():
            self.log_dialog.append_event(category, message)

    # ════════════════════════════════════════════════════════════════════════
    # Window Events (close guard, keyboard shortcuts)
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _build_empty_seat_map() -> Dict[str, List[List[str]]]:
        """Build an empty seat map snapshot for all sections.

        Uses SECTION_CONFIG for per-section dimensions.

        Returns:
            Dict mapping section names to 2D lists filled with 'AVAILABLE'.
        """
        snapshot: Dict[str, List[List[str]]] = {}
        for section in Section:
            cfg = SECTION_CONFIG[section]
            rows = cfg["rows"]
            cols = cfg["cols"]
            snapshot[section.name] = [
                ["AVAILABLE" for _ in range(cols)] for _ in range(rows)
            ]
        return snapshot

    def closeEvent(self, event) -> None:
        self.poll_timer.stop()
        self.ttl_timer.stop()
        self._closing = True

        active_sessions = [
            tx_id for tx_id, s in self.sessions.items() if s.state == "ACTIVE"
        ]
        if active_sessions:
            count = len(active_sessions)
            tx_list = "\n".join(active_sessions[:5])
            if count > 5:
                tx_list += f"\n... and {count - 5} more"
            msg = f"You have {count} active reservation(s):\n{tx_list}"
            reply = QMessageBox.warning(
                self,
                "Active Reservations",
                msg,
                QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if reply == QMessageBox.Discard:
                event.accept()
            else:
                self._closing = False
                self._setup_polling()
                event.ignore()
                return
        else:
            event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Q and event.modifiers() & Qt.ControlModifier:
            self.close()
        else:
            super().keyPressEvent(event)
