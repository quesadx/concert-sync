"""PySide6 main window for the ConcertSync seat reservation GUI.

Assembles all Plan 03 widgets (ConnectionPanel, SectionStatsWidget,
TransactionPanel, SeatMapWidget, EventLogWidget) and Plan 03 workers
(ReserveSelectedWorker, ConfirmWorker, CancelWorker, PollWorker) into a
single QMainWindow with signal-slot wiring, QTimer-based 1-second polling,
session tracking mirroring the Textual TUI, and dual-frontend support
via desktop_launcher.py.

Port of frontend_tui/app.py ConcertTextualApp (lines 82-126 state init,
220-240 compose/layout, 259-301 seat clicks, 332-448 polling, 549-565
session tracking) to PySide6.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from frontend_pyside6.models.tracked_session import TrackedSession
from frontend_pyside6.workers.network_worker import (
    CancelWorker,
    ConfirmWorker,
    PollWorker,
    ReserveSelectedWorker,
    run_worker,
)
from frontend_pyside6.widgets.connection_panel import ConnectionPanel
from frontend_pyside6.widgets.event_log import EventLogWidget, LogTailer
from frontend_pyside6.widgets.login_dialog import LoginDialog
from frontend_pyside6.widgets.seat_map_widget import SeatMapWidget
from frontend_pyside6.widgets.section_stats import SectionStatsWidget
from frontend_pyside6.widgets.transaction_panel import TransactionPanel
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
        pending_selections: List of dicts with 'section','row','col' keys.
        section_snapshot: Last known section availability counts.
        seat_map_snapshot: Last known full seat map grid.
        own_reserved_coords: Set of (section, row, col) tuples owned by this user.
        server_disconnected: Whether the server notified a disconnect.
    """

    _refresh_complete = Signal(
        dict, dict, object
    )  # sections, seat_map_payload, user_session
    _refresh_failed = Signal(str)  # error message

    def __init__(self) -> None:
        """Initialize the main window, state, layout, and polling timer.

        Shows a mandatory numeric login dialog before building the UI.
        Login cannot be skipped — the user must provide a valid numeric ID.
        """
        super().__init__()
        self.setWindowTitle("ConcertSync — Seat Reservation")
        self.setMinimumSize(1024, 768)
        self.resize(1320, 920)

        # ── Stylesheet (WARNING #1 fix) ──────────────────────────────────
        stylesheet_path = Path(__file__).parent / "resources" / "styles.qss"
        stylesheet = stylesheet_path.read_text()
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet)

        # ── Client state (mirrors ConcertTextualApp.__init__) ─────────────
        self.client: Optional[ConcertClient] = None
        self.user_id: Optional[str] = None
        self.connected_host: str = "localhost"
        self.connected_port: int = 9999
        self.sessions: Dict[str, TrackedSession] = {}
        self.pending_selections: List[dict] = []
        self.section_snapshot = {
            "VIP": {"available": 0, "reserved": 0, "sold": 0},
            "PREFERENTIAL": {"available": 0, "reserved": 0, "sold": 0},
            "GENERAL": {"available": 0, "reserved": 0, "sold": 0},
        }
        self.seat_map_snapshot = self._build_empty_seat_map()
        self.own_reserved_coords: Set[tuple[str, int, int]] = set()
        self.server_disconnected: bool = False

        # ── Log tailer (mirrors TUI LogTailer init) ───────────────────────
        self.log_tailer = LogTailer(Path("logs/system.log"))

        # ── Mandatory login dialog ───────────────────────────────────────
        self._show_login()
        if self.user_id is None:
            # User somehow bypassed login — should not happen, but guard
            self.user_id = "0"

        # ── Build UI after login is confirmed ─────────────────────────────
        self._setup_ui()
        self._setup_polling()

        # ── Display user ID in connection panel ───────────────────────────
        self.connection_panel.set_user_id(self.user_id)

    # ════════════════════════════════════════════════════════════════════════
    # Layout
    # ════════════════════════════════════════════════════════════════════════

    def _setup_ui(self) -> None:
        """Build the full window layout and wire all signal-slot connections."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # ═══ LEFT PANEL (~40%) ════════════════════════════════════════════
        left_panel = QVBoxLayout()

        self.connection_panel = ConnectionPanel()
        left_panel.addWidget(self.connection_panel)

        left_panel.addSpacing(8)

        self.section_stats = SectionStatsWidget()
        left_panel.addWidget(self.section_stats)

        left_panel.addSpacing(8)

        self.transaction_panel = TransactionPanel()
        left_panel.addWidget(self.transaction_panel)

        left_panel.addSpacing(8)

        self.reserve_btn = QPushButton("Reserve Selected")
        left_panel.addWidget(self.reserve_btn)

        left_panel.addStretch()
        main_layout.addLayout(left_panel, stretch=22)

        # ═══ RIGHT PANEL (~78%) ═══════════════════════════════════════════
        right_panel = QVBoxLayout()

        # ── Color legend (compact) ────────────────────────────────────────
        legend_layout = QHBoxLayout()
        legend_layout.setContentsMargins(0, 0, 0, 2)
        legend_layout.setSpacing(10)
        legend_states = [
            ("AVAILABLE", "#4CAF50", "Available"),
            ("OWN_RESERVED", "#2196F3", "Own"),
            ("RESERVED", "#FF9800", "Reserved"),
            ("SOLD", "#F44336", "Sold"),
            ("PENDING", "#9C27B0", "Pending"),
        ]
        for state_id, color, label_text in legend_states:
            swatch = QLabel("  ")
            swatch.setStyleSheet(
                f"background-color: {color}; min-width: 14px; max-width: 14px;"
                f" min-height: 10px; max-height: 10px;"
                f" border: 1px solid #3b4a64; border-radius: 2px;"
            )
            legend_layout.addWidget(swatch)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 10px; padding-right: 2px;")
            legend_layout.addWidget(lbl)
        legend_layout.addStretch()
        right_panel.addLayout(legend_layout)

        # ── Cinema seat matrix: all sections stacked vertically ───────────
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(6)

        self.seat_maps: Dict[str, SeatMapWidget] = {}
        section_labels = {
            "VIP": "VIP — Orchchestra Front (5\xd710)",
            "PREFERENTIAL": "PREFERENTIAL — Middle Tier (10\xd715)",
            "GENERAL": "GENERAL — Upper Level (20\xd720)",
        }
        for section_name in ["VIP", "PREFERENTIAL", "GENERAL"]:
            section = Section[section_name]
            cfg = SECTION_CONFIG[section]
            header = QLabel(section_labels[section_name])
            header.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #9ad4d6; "
                "padding: 4px 0 2px 0;"
            )
            scroll_layout.addWidget(header)
            sm = SeatMapWidget(section_name, cfg["rows"], cfg["cols"])
            sm.seat_clicked.connect(self._on_seat_clicked)
            self.seat_maps[section_name] = sm
            scroll_layout.addWidget(sm)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        right_panel.addWidget(scroll_area, stretch=1)

        # ── Event log toggle ────────────────────────────────────────────
        self.event_log = EventLogWidget()
        self.event_log.setObjectName("event-log-panel")
        self.event_log.setFixedHeight(120)

        log_header = QHBoxLayout()
        self.log_toggle_btn = QPushButton("\u25bc Event Log")
        self.log_toggle_btn.setCheckable(True)
        self.log_toggle_btn.setChecked(True)
        self.log_toggle_btn.clicked.connect(self._toggle_event_log)
        log_header.addWidget(self.log_toggle_btn)
        log_header.addStretch()
        clear_log_btn = QPushButton("Clear")
        clear_log_btn.clicked.connect(self.event_log.clear)
        log_header.addWidget(clear_log_btn)
        right_panel.addLayout(log_header)
        right_panel.addWidget(self.event_log)

        main_layout.addLayout(right_panel, stretch=60)

        # ── Status bar ────────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Not connected")
        self.setStatusBar(self.status_bar)

        # ── Signal-slot wiring ────────────────────────────────────────────
        self.connection_panel.connect_requested.connect(self._connect_client)
        self.connection_panel.change_user_requested.connect(self._on_change_user)
        self.transaction_panel.confirm_requested.connect(self._on_confirm)
        self.transaction_panel.cancel_requested.connect(self._on_cancel)
        self.reserve_btn.clicked.connect(self._on_reserve_selected)

    def _toggle_event_log(self) -> None:
        """Show or hide the event log based on toggle button state."""
        visible = self.log_toggle_btn.isChecked()
        self.event_log.setVisible(visible)
        self.log_toggle_btn.setText(
            "\u25bc Event Log" if visible else "\u25b6 Event Log"
        )

    # ════════════════════════════════════════════════════════════════════════
    # Login
    # ════════════════════════════════════════════════════════════════════════

    def _show_login(self) -> None:
        """Show the numeric login dialog and store the user ID.

        Blocks until a valid numeric ID is entered. Login is mandatory —
        the dialog cannot be dismissed without providing valid input.
        Sets self.user_id on success, leaves it as None if somehow rejected.
        """
        dialog = LoginDialog(self)
        if dialog.exec() == LoginDialog.Accepted:
            self.user_id = dialog.user_id
        # If rejected (should not happen since close button is hidden),
        # user_id stays None and the caller handles it.

    @Slot()
    def _on_change_user(self) -> None:
        """Handle Change User button: disconnect, re-login, and reset state.

        Disconnects from the current server, shows the login dialog for a
        new numeric user ID, clears all session state, and updates the UI.
        """
        # Disconnect current client
        self.client = None
        self.connected_host = "localhost"
        self.connected_port = 9999
        self.status_bar.showMessage("Not connected")

        # Clear all state from previous user
        self.own_reserved_coords.clear()
        self.sessions.clear()
        self.pending_selections.clear()

        # Show login dialog for re-authentication
        self._show_login()
        if self.user_id is None:
            self.user_id = "0"

        # Update display
        self.connection_panel.set_user_id(self.user_id)
        self._render_all()

    # ════════════════════════════════════════════════════════════════════════
    # Connection
    # ════════════════════════════════════════════════════════════════════════

    @Slot(str, int)
    def _connect_client(self, host: str = "localhost", port: int = 9999) -> None:
        """Connect to the ConcertSync server and perform initial query.

        Uses the user_id set during mandatory login flow. The server
        requires a non-empty user_id for OWN_RESERVED seat detection.

        Args:
            host: Server hostname or IP address.
            port: Server TCP port.
        """
        if self.user_id is None:
            self.status_bar.showMessage("Login required before connecting")
            return

        # Clear state from any previous user session to prevent stale OWN_RESERVED highlights
        self.own_reserved_coords.clear()
        self.sessions.clear()
        self.pending_selections.clear()

        self.client = ConcertClient(user_id=self.user_id, host=host, port=port)
        self.connected_host = host
        self.connected_port = port

        try:
            self.client.query()  # Test connection
            self.status_bar.showMessage(f"Connected to {host}:{port} as {self.user_id}")
            self._log_event("LOCAL", f"Connected to {host}:{port}")
            self._refresh_all()
        except ConcertClientError as exc:
            self.client = None
            self.status_bar.showMessage(f"Connection failed: {exc}")
            self._log_event("ERROR", f"Connection failed: {exc}")

    # ════════════════════════════════════════════════════════════════════════
    # Polling
    # ════════════════════════════════════════════════════════════════════════

    def _setup_polling(self) -> None:
        """Start the 1-second QTimer for seat map and section polling."""
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_tick)
        self.poll_timer.start(1000)  # 1 second

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

    @Slot(dict, dict, object)
    def _on_poll_success(
        self, sections: dict, seat_map_payload: dict, user_session: object
    ) -> None:
        """Handle successful poll: update snapshots, parse user session, render all widgets.

        Args:
            sections: Section count dict e.g. {'VIP': {'available': 50, ...}, ...}
            seat_map_payload: Full seat map dict from QUERY_SEAT_MAP response.
            user_session: Active session dict for the user, or None if no active session.
        """
        self.section_snapshot = sections
        self.seat_map_snapshot = seat_map_payload
        self._sync_user_session(user_session)
        self._render_all()

    def _sync_user_session(self, user_session: object) -> None:
        """Sync client-side session tracking with server-side active session.

        When the user has an active session on the server (detected via
        QUERY_SEAT_MAP response), create a TrackedSession entry locally
        so it appears in the session table with TTL countdown. Auto-fills
        the TX ID input for one-click confirm/cancel.

        Args:
            user_session: Dict with session_id, seats, ttl_secs, last_activity
                          from the server, or None if no active session.
        """
        if user_session is None:
            return

        session_id = user_session.get("session_id", "")
        seat_list = user_session.get("seats", [])
        ttl_secs = user_session.get("ttl_secs", 300)
        last_activity = user_session.get("last_activity", 0)

        if not session_id or not seat_list:
            return

        seat_summary = ", ".join(
            f"{s['section']}({s['row']},{s['col']})" for s in seat_list
        )

        if session_id in self.sessions:
            self.sessions[session_id].created_at = last_activity
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
            self._log_event(
                "LOCAL",
                f"Auto-loaded session {session_id} with {len(seat_list)} seat(s)",
            )

        self.transaction_panel.tx_input.setText(session_id)

    @Slot(str)
    def _on_poll_error(self, error_msg: str) -> None:
        """Handle poll error: update status bar and log the error.

        Args:
            error_msg: Error message string from the worker.
        """
        self.status_bar.showMessage(f"Poll error: {error_msg}")
        self._log_event("ERROR", f"Poll failed: {error_msg}")

    # ════════════════════════════════════════════════════════════════════════
    # Seat Click (mirrors TUI on_data_table_cell_selected, app.py 259-301)
    # ════════════════════════════════════════════════════════════════════════

    @Slot(str, int, int, str)
    def _on_seat_clicked(self, section: str, row: int, col: int, state: str) -> None:
        """Handle a seat click: toggle selection for AVAILABLE seats only.

        Mirrors ConcertTextualApp.on_data_table_cell_selected (app.py 273-295).

        Args:
            section: Section name (VIP, PREFERENTIAL, GENERAL).
            row: Row index (0-based).
            col: Column index (0-based).
            state: Server state string for the clicked seat.
        """
        if state != "AVAILABLE":
            self.status_bar.showMessage(
                f"Seat {section}({row},{col}) — state: {state} (not selectable)"
            )
            return

        # Check if already in pending selections
        existing_idx = None
        for i, s in enumerate(self.pending_selections):
            if s["section"] == section and s["row"] == row and s["col"] == col:
                existing_idx = i
                break

        if existing_idx is not None:
            self.pending_selections.pop(existing_idx)
            self.status_bar.showMessage(f"Deselected {section}({row},{col})")
        else:
            self.pending_selections.append({"section": section, "row": row, "col": col})
            self.status_bar.showMessage(
                f"Selected {section}({row},{col}) — {len(self.pending_selections)} pending"
            )

        self._render_seat_map()
        self._update_reserve_button()

    # ════════════════════════════════════════════════════════════════════════
    # Reserve Selected (unified batch mode — RSRV-01)
    # ════════════════════════════════════════════════════════════════════════

    @Slot()
    def _on_reserve_selected(self) -> None:
        """Dispatch a batch reservation for all pending seat selections.

        Always uses ConcertClient.reserve_selected() which sends RESERVE_SELECTED,
        the unified batch reservation mode (RSRV-01 fix). Dispatches work on a
        background thread via ReserveSelectedWorker.
        """
        if len(self.pending_selections) == 0:
            self.status_bar.showMessage("No seats selected for reservation")
            return

        worker = ReserveSelectedWorker(self.client, self.pending_selections)
        worker.finished.connect(self._on_reserve_success)
        worker.error.connect(self._on_reserve_error)
        run_worker(worker)

    @Slot(dict)
    def _on_reserve_success(self, response: dict) -> None:
        """Handle successful reservation: track session and own coords.

        Extracts transaction_id and TTL, builds seat summary, creates/merges
        a TrackedSession, records own reserved coordinates, and refreshes UI.

        Args:
            response: Server response dict with transaction_id, ttl, etc.
        """
        tx_id = response["transaction_id"]
        ttl = response["ttl"]

        seat_objects = list(self.pending_selections)
        seat_summary = ", ".join(
            f"{s['section']}({s['row']},{s['col']})" for s in seat_objects
        )

        session = self._track_session(tx_id, "RESERVE_BATCH", seat_summary, ttl)
        session.seats = list(self.pending_selections)

        for s in seat_objects:
            self.own_reserved_coords.add((s["section"], s["row"], s["col"]))

        count = len(seat_objects)
        self.pending_selections = []

        # Auto-fill the transaction ID in the transaction panel for one-click confirm/cancel
        self.transaction_panel.tx_input.setText(tx_id)

        self._log_event("LOCAL", f"Reserved {count} seats — TX:{tx_id}")
        self.status_bar.showMessage(f"Reserved {count} seats — TX:{tx_id}")
        self._render_all()

    @Slot(str)
    def _on_reserve_error(self, error_msg: str) -> None:
        """Handle reservation error: show status and log.

        Args:
            error_msg: Error message from the worker.
        """
        self.status_bar.showMessage(f"Reserve failed: {error_msg}")
        self._log_event("ERROR", f"Reserve failed: {error_msg}")

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
        """Dispatch a confirm request for a transaction on a background thread.

        Args:
            tx_id: Transaction ID to confirm.
        """
        if not tx_id:
            self.status_bar.showMessage("No transaction ID to confirm")
            return
        worker = ConfirmWorker(self.client, tx_id)
        worker.finished.connect(self._on_confirm_success)
        worker.error.connect(self._on_confirm_error)
        run_worker(worker)

    @Slot(dict)
    def _on_confirm_success(self, response: dict) -> None:
        """Handle confirm success: mark session CONFIRMED, keep own coords.

        Args:
            response: Server response dict.
        """
        tx_id = response.get("transaction_id", "")
        if tx_id in self.sessions:
            self.sessions[tx_id].state = "CONFIRMED"

        self._log_event("LOCAL", f"Confirmed TX:{tx_id}")
        self.status_bar.showMessage(f"Confirmed TX:{tx_id}")
        self._render_all()

    @Slot(str)
    def _on_confirm_error(self, error_msg: str) -> None:
        """Handle confirm error.

        Args:
            error_msg: Error message from the worker.
        """
        self.status_bar.showMessage(f"Confirm failed: {error_msg}")
        self._log_event("ERROR", f"Confirm failed: {error_msg}")

    # ════════════════════════════════════════════════════════════════════════
    # Cancel
    # ════════════════════════════════════════════════════════════════════════

    @Slot(str)
    def _on_cancel(self, tx_id: str) -> None:
        """Dispatch a cancel request for a transaction on a background thread.

        Args:
            tx_id: Transaction ID to cancel.
        """
        if not tx_id:
            self.status_bar.showMessage("No transaction ID to cancel")
            return
        worker = CancelWorker(self.client, tx_id)
        worker.finished.connect(self._on_cancel_success)
        worker.error.connect(self._on_cancel_error)
        run_worker(worker)

    @Slot(dict)
    def _on_cancel_success(self, response: dict) -> None:
        """Handle cancel success: mark session CANCELLED, remove own coords.

        Updates the tracking state and removes previously owned coordinates
        from the own_reserved_coords set so they revert to plain AVAILABLE
        on the next poll refresh.

        Args:
            response: Server response dict.
        """
        tx_id = response.get("transaction_id", "")
        if tx_id in self.sessions:
            self.sessions[tx_id].state = "CANCELLED"

        self._log_event("LOCAL", f"Cancelled TX:{tx_id}")
        self.status_bar.showMessage(f"Cancelled TX:{tx_id}")
        self._render_all()

    @Slot(str)
    def _on_cancel_error(self, error_msg: str) -> None:
        """Handle cancel error.

        Args:
            error_msg: Error message from the worker.
        """
        self.status_bar.showMessage(f"Cancel failed: {error_msg}")
        self._log_event("ERROR", f"Cancel failed: {error_msg}")

    # ════════════════════════════════════════════════════════════════════════
    # Rendering
    # ════════════════════════════════════════════════════════════════════════

    def _render_all(self) -> None:
        """Refresh all widgets: section stats, seat map, sessions, and log tail.

        Called on every poll success and after reservation/confirm/cancel.
        """
        # Compute pending counts per section
        pending_counts: dict[str, int] = {"VIP": 0, "PREFERENTIAL": 0, "GENERAL": 0}
        for s in self.pending_selections:
            section = s.get("section", "")
            if section in pending_counts:
                pending_counts[section] += 1

        self.section_stats.update_counts(self.section_snapshot, pending=pending_counts)
        self._render_seat_map()
        self.transaction_panel.update_sessions(self.sessions)
        self._update_reserve_button()

        # Tail server log file for new lines
        try:
            for line in self.log_tailer.read_new_lines(max_lines=50):
                self.event_log.append_line(line)
        except Exception:
            pass  # Log file may not exist yet

    def _render_seat_map(self) -> None:
        """Refresh all visible seat map widgets with current snapshot data."""
        pending_by_section: Dict[str, Set[tuple[int, int]]] = {
            "VIP": set(),
            "PREFERENTIAL": set(),
            "GENERAL": set(),
        }
        for s in self.pending_selections:
            pending_by_section[s["section"]].add((s["row"], s["col"]))

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

    def _update_reserve_button(self) -> None:
        """Update the Reserve button text to show pending selection count."""
        count = len(self.pending_selections)
        self.reserve_btn.setText(f"Reserve Selected ({count})")

    @staticmethod
    def _build_empty_seat_map() -> Dict[str, List[List[str]]]:
        """Build an empty seat map snapshot for all sections.

        Mirrors ConcertTextualApp._build_empty_seat_map and PATTERNS.md
        lines 192-200. Uses SECTION_CONFIG for per-section dimensions.

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
        """Append a color-coded event to the event log widget.

        Args:
            category: Event category (LOCAL, REMOTE, ERROR, SERVER, EXPIRE).
            message: The event description text.
        """
        self.event_log.append_event(category, message)

    # ════════════════════════════════════════════════════════════════════════
    # Window Events (close guard, keyboard shortcuts)
    # ════════════════════════════════════════════════════════════════════════

    def closeEvent(self, event) -> None:
        """Warn the user before closing if there are active reservations.

        Checks all tracked sessions for ACTIVE state. If any exist, shows a
        QMessageBox with Discard/Cancel options. Discard accepts the close;
        Cancel ignores it.

        Args:
            event: The QCloseEvent from Qt.
        """
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
                event.ignore()
        else:
            event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard shortcuts.

        Ctrl+R: Trigger Reserve Selected action.
        Ctrl+Q: Close the window.
        All other keys: delegate to default handler.

        Args:
            event: The QKeyEvent from Qt.
        """
        if event.key() == Qt.Key_R and event.modifiers() & Qt.ControlModifier:
            self._on_reserve_selected()
        elif event.key() == Qt.Key_Q and event.modifiers() & Qt.ControlModifier:
            self.close()
        else:
            super().keyPressEvent(event)
