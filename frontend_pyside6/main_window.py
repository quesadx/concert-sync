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
from uuid import uuid4

from PySide6.QtCore import QSettings, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
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
        selected_map_section: Currently visible section name.
        own_reserved_coords: Set of (section, row, col) tuples owned by this user.
        server_disconnected: Whether the server notified a disconnect.
    """

    _refresh_complete = Signal(dict, dict)  # sections, seat_map_payload
    _refresh_failed = Signal(str)  # error message

    def __init__(self) -> None:
        """Initialize the main window, state, layout, and polling timer."""
        super().__init__()
        self.setWindowTitle("ConcertSync — Seat Reservation")
        self.setMinimumSize(1024, 768)

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
        self.selected_map_section = "GENERAL"
        self.own_reserved_coords: Set[tuple[str, int, int]] = set()
        self.server_disconnected: bool = False

        # ── Log tailer (mirrors TUI LogTailer init) ───────────────────────
        self.log_tailer = LogTailer(Path("logs/system.log"))

        self._setup_ui()
        self._setup_polling()

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

        # ── QSettings: restore stored session_id on startup ───────────────
        settings = QSettings("ConcertSync", "PySide6GUI")
        stored_session_id = settings.value("session_id", "")
        if stored_session_id:
            self.connection_panel.session_id_input.setText(stored_session_id)

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
        main_layout.addLayout(left_panel, stretch=40)

        # ═══ RIGHT PANEL (~60%) ═══════════════════════════════════════════
        right_panel = QVBoxLayout()

        # ── Section selector ──────────────────────────────────────────────
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Section:"))
        self.section_combo = QComboBox()
        self.section_combo.addItems(["VIP", "PREFERENTIAL", "GENERAL"])
        self.section_combo.currentTextChanged.connect(self._on_section_changed)
        selector_layout.addWidget(self.section_combo)
        selector_layout.addStretch()
        right_panel.addLayout(selector_layout)

        # ── Seat maps (one per section, created upfront) ──────────────────
        self.seat_maps: Dict[str, SeatMapWidget] = {}
        for section_name in ["VIP", "PREFERENTIAL", "GENERAL"]:
            section = Section[section_name]
            cfg = SECTION_CONFIG[section]
            sm = SeatMapWidget(section_name, cfg["rows"], cfg["cols"])
            sm.seat_clicked.connect(self._on_seat_clicked)
            self.seat_maps[section_name] = sm
            right_panel.addWidget(sm)

        right_panel.addSpacing(8)

        self.event_log = EventLogWidget()
        right_panel.addWidget(self.event_log, stretch=1)

        main_layout.addLayout(right_panel, stretch=60)

        # ── Initially show only the default section ───────────────────────
        self._show_section("GENERAL")

        # ── Status bar ────────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Not connected")
        self.setStatusBar(self.status_bar)

        # ── Signal-slot wiring ────────────────────────────────────────────
        self.connection_panel.connect_requested.connect(self._connect_client)
        self.connection_panel.reclaim_requested.connect(self._on_reclaim_session)
        self.transaction_panel.confirm_requested.connect(self._on_confirm)
        self.transaction_panel.cancel_requested.connect(self._on_cancel)
        self.reserve_btn.clicked.connect(self._on_reserve_selected)

    def _show_section(self, section_name: str) -> None:
        """Hide all seat maps and show only the selected section.

        Args:
            section_name: One of 'VIP', 'PREFERENTIAL', or 'GENERAL'.
        """
        for name, widget in self.seat_maps.items():
            widget.setVisible(name == section_name)

    @Slot(str)
    def _on_section_changed(self, section_name: str) -> None:
        """Handle section combo box selection change.

        Args:
            section_name: The newly selected section name.
        """
        self.selected_map_section = section_name
        self._show_section(section_name)

    # ════════════════════════════════════════════════════════════════════════
    # Connection
    # ════════════════════════════════════════════════════════════════════════

    @Slot(str, int)
    def _connect_client(self, host: str = "localhost", port: int = 9999) -> None:
        """Connect to the ConcertSync server and perform initial query.

        Mirrors ConcertTextualApp._connect_client (app.py lines 352-380).

        BLOCKER #1 fix: Reads user_id from the ConnectionPanel input field.
        Auto-generates a UUID-based user_id if the input is empty. The server
        requires a non-empty user_id for OWN_RESERVED seat detection.

        Args:
            host: Server hostname or IP address.
            port: Server TCP port.
        """
        # ── BLOCKER #1 fix: read user_id, auto-generate if empty ──────────
        user_id = self.connection_panel.user_id_input.text().strip()
        if not user_id:
            user_id = f"user_{uuid4().hex[:8]}"
        self.user_id = user_id

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
    # Session Reclaim (BLOCKER #2 — SESS-01/SESS-02)
    # ════════════════════════════════════════════════════════════════════════

    @Slot(str)
    def _on_reclaim_session(self, session_id: str) -> None:
        """Reclaim a previous session by sending QUERY with a stored session_id.

        BLOCKER #2 fix: Reconnects the user to a previous session so reserved
        seats survive client disconnect/reconnect. Sends QUERY with the stored
        session_id, then refreshes the full UI state.

        Args:
            session_id: The session identifier to reclaim.
        """
        if self.client is None:
            self._log_event("ERROR", "Cannot reclaim session: not connected")
            return

        try:
            _ = self.client.send_request(
                {
                    "action": "QUERY",
                    "user_id": self.user_id,
                    "session_id": session_id,
                }
            )
            self._log_event("LOCAL", f"Reclaimed session {session_id}")
            self._refresh_all()
        except ConcertClientError as exc:
            self._log_event("ERROR", f"Session reclaim failed: {exc}")

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

    @Slot(dict, dict)
    def _on_poll_success(self, sections: dict, seat_map_payload: dict) -> None:
        """Handle successful poll: update snapshots and render all widgets.

        Args:
            sections: Section count dict e.g. {'VIP': {'available': 50, ...}, ...}
            seat_map_payload: Full seat map dict from QUERY_SEAT_MAP response.
        """
        self.section_snapshot = sections
        self.seat_map_snapshot = seat_map_payload
        self._render_all()

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

        self._track_session(tx_id, "RESERVE_BATCH", seat_summary, ttl)

        for s in seat_objects:
            self.own_reserved_coords.add((s["section"], s["row"], s["col"]))

        count = len(seat_objects)
        self.pending_selections = []

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
        on the next poll refresh. The server re-reclaims coordinates on
        reconnect via session_id replay.

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
        self.section_stats.update_counts(self.section_snapshot)
        self._render_seat_map()
        self.transaction_panel.update_sessions(self.sessions)

        # Tail server log file for new lines
        try:
            for line in self.log_tailer.read_new_lines(max_lines=50):
                self.event_log.append_line(line)
        except Exception:
            pass  # Log file may not exist yet

    def _render_seat_map(self) -> None:
        """Refresh only the currently visible seat map widget.

        Builds per-section pending and own coordinate sets from the global
        pending_selections list and own_reserved_coords set, then delegates
        to SeatMapWidget.update_grid() for cell-by-cell color refresh.
        """
        section = self.selected_map_section
        widget = self.seat_maps.get(section)
        if widget is None:
            return
        grid = self.seat_map_snapshot.get(section, [])
        if not grid:
            return

        # Pending coords for this section
        pending_coords: Set[tuple[int, int]] = set()
        for s in self.pending_selections:
            if s["section"] == section:
                pending_coords.add((s["row"], s["col"]))

        # Own reserved coords for this section
        own_coords: Set[tuple[int, int]] = set()
        for s_name, r, c in self.own_reserved_coords:
            if s_name == section:
                own_coords.add((r, c))

        widget.update_grid(grid, pending_coords, own_coords)

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
        """Perform an immediate refresh (used on connect and session reclaim).

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
