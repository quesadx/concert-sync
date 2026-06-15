"""Server monitoring dashboard for ConcertSync.

Displays real-time section occupancy, active sessions, and a live event log
by polling the server via existing QUERY and QUERY_SEAT_MAP endpoints.

Connects as a generic admin user (user_id="admin_dashboard") and updates
UI components every second via a QTimer-driven PollWorker.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from frontend_pyside6.widgets.event_log import EventLogWidget, LogTailer
from frontend_pyside6.workers.network_worker import PollWorker, run_worker
from src.client.concert_client import ConcertClient, ConcertClientError
from src.utils.config import SECTION_CONFIG
from src.utils.enums import Section


class ServerDashboardWindow(QMainWindow):
    """Real-time server monitoring dashboard for ConcertSync.

    Polls the server every second via existing QUERY and QUERY_SEAT_MAP
    endpoints, displaying section occupancy bars, summary counts, and a
    live event log tail.

    Attributes:
        client: Connected ConcertClient instance (None if disconnected).
        poll_timer: QTimer that triggers polling every 1 second.
        log_tailer: LogTailer for reading new server log lines.
    """

    _poll_complete = Signal(dict, dict, object)
    _poll_error = Signal(str)

    def __init__(self) -> None:
        """Initialize the dashboard window, layout, and polling timer."""
        super().__init__()
        self.setWindowTitle("ConcertSync Server Dashboard")
        self.setMinimumSize(1024, 768)
        self.resize(1280, 900)

        # ── Stylesheet ───────────────────────────────────────────────────
        stylesheet_path = Path(__file__).parent / "resources" / "styles.qss"
        if stylesheet_path.exists():
            stylesheet = stylesheet_path.read_text(encoding="utf-8")
            app = QApplication.instance()
            if app:
                app.setStyleSheet(stylesheet)

        # ── Client state ────────────────────────────────────────────────
        self.client: Optional[ConcertClient] = None
        self.user_id: str = "admin_dashboard"
        self.connected_host: str = "localhost"
        self.connected_port: int = 9999

        # ── Log tailer ────────────────────────────────────────────────────
        self.log_tailer = LogTailer(Path("logs/system.log"))

        self._setup_ui()
        self._setup_polling()

    # ════════════════════════════════════════════════════════════════════════
    # Layout
    # ════════════════════════════════════════════════════════════════════════

    def _setup_ui(self) -> None:
        """Build the dashboard layout and wire all signal-slot connections."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ── Top bar ───────────────────────────────────────────────────────
        top_bar = QHBoxLayout()
        self.title_label = QLabel("ConcertSync Server Dashboard")
        self.title_label.setObjectName("header-title")
        top_bar.addWidget(self.title_label)
        top_bar.addStretch()

        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("status-disconnected")
        top_bar.addWidget(self.status_label)

        self.timestamp_label = QLabel("--:--:--")
        self.timestamp_label.setObjectName("section-label")
        top_bar.addWidget(self.timestamp_label)
        main_layout.addLayout(top_bar)

        # ── Main splitter (left | center | right) ────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # ═══ LEFT PANEL: Connection + Summary ═════════════════════════════
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)

        # Connection controls
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout(conn_group)
        host_row = QHBoxLayout()
        self.host_input = QLineEdit("localhost")
        self.host_input.setPlaceholderText("Host")
        host_row.addWidget(QLabel("Host:"))
        host_row.addWidget(self.host_input)
        conn_layout.addLayout(host_row)
        port_row = QHBoxLayout()
        self.port_input = QLineEdit("9999")
        self.port_input.setPlaceholderText("Port")
        self.port_input.setMaximumWidth(80)
        port_row.addWidget(QLabel("Port:"))
        port_row.addWidget(self.port_input)
        conn_layout.addLayout(port_row)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("accent-btn")
        self.connect_btn.clicked.connect(self._on_connect)
        conn_layout.addWidget(self.connect_btn)
        left_layout.addWidget(conn_group)

        # Summary cards
        summary_group = QGroupBox("Server Summary")
        summary_layout = QVBoxLayout(summary_group)
        self.total_seats_label = QLabel("Total: 0 / 0 occupied")
        self.active_sessions_label = QLabel("Active sessions: 0")
        self.reserved_count_label = QLabel("Reserved: 0")
        self.sold_count_label = QLabel("Sold: 0")
        self.available_count_label = QLabel("Available: 0")
        for lbl in [
            self.total_seats_label,
            self.active_sessions_label,
            self.reserved_count_label,
            self.sold_count_label,
            self.available_count_label,
        ]:
            lbl.setObjectName("summary-text")
            summary_layout.addWidget(lbl)
        left_layout.addWidget(summary_group)
        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # ═══ CENTER PANEL: Section Occupancy ══════════════════════════════
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(4, 4, 4, 4)

        occupancy_group = QGroupBox("Section Occupancy")
        occupancy_layout = QVBoxLayout(occupancy_group)

        self.progress_bars: Dict[str, QProgressBar] = {}
        self.progress_labels: Dict[str, QLabel] = {}
        section_colors = {
            "VIP": "vip-progress",
            "PREFERENTIAL": "preferential-progress",
            "GENERAL": "general-progress",
        }
        for section_name in ["VIP", "PREFERENTIAL", "GENERAL"]:
            section = Section[section_name]
            cfg = SECTION_CONFIG[section]
            total = cfg["rows"] * cfg["cols"]

            bar_label = QLabel(f"{section_name} — {total} seats")
            bar_label.setObjectName("summary-text")
            occupancy_layout.addWidget(bar_label)

            bar = QProgressBar()
            bar.setObjectName(section_colors[section_name])
            bar.setRange(0, total)
            bar.setValue(0)
            bar.setTextVisible(True)
            bar.setFormat("%v / %m occupied (%p%)")
            # text-align: center is handled by QSS QProgressBar rule
            self.progress_bars[section_name] = bar
            occupancy_layout.addWidget(bar)

            counts_label = QLabel("Available: 0 | Reserved: 0 | Sold: 0")
            counts_label.setObjectName("legend-text")
            self.progress_labels[section_name] = counts_label
            occupancy_layout.addWidget(counts_label)

            occupancy_layout.addSpacing(8)

        center_layout.addWidget(occupancy_group)
        center_layout.addStretch()
        splitter.addWidget(center_widget)

        # ═══ RIGHT PANEL: Live Event Log ════════════════════════════════
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 4, 4, 4)

        log_group = QGroupBox("Live Event Log")
        log_layout = QVBoxLayout(log_group)
        self.event_log = EventLogWidget()
        log_layout.addWidget(self.event_log)
        right_layout.addWidget(log_group)
        splitter.addWidget(right_widget)

        # Set splitter proportions
        splitter.setSizes([300, 520, 300])
        main_layout.addWidget(splitter, stretch=1)

        # ── Signal-slot wiring ──────────────────────────────────────────
        self._poll_complete.connect(self._on_poll_success)
        self._poll_error.connect(self._on_poll_error)

    # ════════════════════════════════════════════════════════════════════════
    # Polling
    # ════════════════════════════════════════════════════════════════════════

    def _setup_polling(self) -> None:
        """Start the 1-second QTimer for dashboard data polling."""
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_tick)
        self.poll_timer.start(1000)

        # Also update timestamp every second
        self._update_timestamp()

    def _poll_tick(self) -> None:
        """Timer callback — dispatches network poll to a background thread."""
        if self.client is None:
            return
        worker = PollWorker(self.client)
        worker.finished.connect(self._poll_complete)
        worker.error.connect(self._poll_error)
        run_worker(worker)

    def _update_timestamp(self) -> None:
        """Update the timestamp label with the current time."""
        self.timestamp_label.setText(datetime.now().strftime("%H:%M:%S"))

    @Slot(dict, dict, object)
    def _on_poll_success(self, sections: dict, seat_map_payload: dict, user_session: object) -> None:
        """Handle successful poll: update occupancy bars, summary counts, and log.

        Args:
            sections: Section count dict e.g. {'VIP': {'available': 50, ...}, ...}
            seat_map_payload: Full seat map dict from QUERY_SEAT_MAP response.
            user_session: Active session dict for the user (ignored for dashboard).
        """
        self._update_timestamp()
        self._update_summary(sections)
        self._update_occupancy(sections)
        self._tail_log()

    @Slot(str)
    def _on_poll_error(self, error_msg: str) -> None:
        """Handle poll error: update status and log.

        Args:
            error_msg: Error message from the worker.
        """
        self.status_label.setText("Disconnected")
        self.status_label.setObjectName("status-disconnected")
        self._update_timestamp()
        self.event_log.append_event("ERROR", f"Poll failed: {error_msg}")

    # ════════════════════════════════════════════════════════════════════════
    # Connection
    # ════════════════════════════════════════════════════════════════════════

    def _on_connect(self) -> None:
        """Handle Connect button click: connect to the server."""
        host = self.host_input.text().strip() or "localhost"
        try:
            port = int(self.port_input.text().strip())
        except ValueError:
            self.event_log.append_event("ERROR", "Invalid port number")
            return

        self.connected_host = host
        self.connected_port = port
        self.client = ConcertClient(user_id=self.user_id, host=host, port=port)

        try:
            self.client.query()
            self.status_label.setText(f"Connected to {host}:{port}")
            self.status_label.setObjectName("status-connected")
            self.connect_btn.setText("Disconnect")
            self.connect_btn.clicked.disconnect(self._on_connect)
            self.connect_btn.clicked.connect(self._on_disconnect)
            self.event_log.append_event("SERVER", f"Connected to {host}:{port}")
            self._poll_tick()
        except ConcertClientError as exc:
            self.client = None
            self.status_label.setText("Connection failed")
            self.status_label.setObjectName("status-disconnected")
            self.event_log.append_event("ERROR", f"Connection failed: {exc}")

    def _on_disconnect(self) -> None:
        """Handle Disconnect button click: disconnect from the server."""
        self.client = None
        self.status_label.setText("Disconnected")
        self.status_label.setObjectName("status-disconnected")
        self.connect_btn.setText("Connect")
        try:
            self.connect_btn.clicked.disconnect(self._on_disconnect)
        except RuntimeError:
            pass
        self.connect_btn.clicked.connect(self._on_connect)
        self.event_log.append_event("SERVER", "Disconnected")

    # ════════════════════════════════════════════════════════════════════════
    # Data Updates
    # ════════════════════════════════════════════════════════════════════════

    def _update_summary(self, sections: dict) -> None:
        """Update server summary counts from section data.

        Args:
            sections: Section count dict with 'available', 'reserved', 'sold'.
        """
        total = 0
        occupied = 0
        reserved = 0
        sold = 0
        available = 0

        for section_name in ["VIP", "PREFERENTIAL", "GENERAL"]:
            counts = sections.get(section_name, {})
            section = Section[section_name]
            cfg = SECTION_CONFIG[section]
            section_total = cfg["rows"] * cfg["cols"]
            total += section_total
            occupied += counts.get("reserved", 0) + counts.get("sold", 0)
            reserved += counts.get("reserved", 0)
            sold += counts.get("sold", 0)
            available += counts.get("available", 0)

        self.total_seats_label.setText(f"Total: {occupied} / {total} occupied")
        self.reserved_count_label.setText(f"Reserved: {reserved}")
        self.sold_count_label.setText(f"Sold: {sold}")
        self.available_count_label.setText(f"Available: {available}")

        # Active sessions count is not directly in sections; we approximate
        # by counting how many sections have reserved seats. In a real implementation
        # we'd add a dedicated endpoint. For now, we just show total reserved.
        self.active_sessions_label.setText(f"Active reservations: {reserved}")

    def _update_occupancy(self, sections: dict) -> None:
        """Update section occupancy progress bars.

        Args:
            sections: Section count dict with 'available', 'reserved', 'sold'.
        """
        for section_name in ["VIP", "PREFERENTIAL", "GENERAL"]:
            counts = sections.get(section_name, {})
            section = Section[section_name]
            cfg = SECTION_CONFIG[section]
            total = cfg["rows"] * cfg["cols"]
            occupied = counts.get("reserved", 0) + counts.get("sold", 0)
            available = counts.get("available", 0)
            reserved = counts.get("reserved", 0)
            sold = counts.get("sold", 0)

            bar = self.progress_bars.get(section_name)
            if bar:
                bar.setRange(0, total)
                bar.setValue(occupied)

            lbl = self.progress_labels.get(section_name)
            if lbl:
                lbl.setText(f"Available: {available} | Reserved: {reserved} | Sold: {sold}")

    def _tail_log(self) -> None:
        """Tail the server log file for new lines and append to event log."""
        try:
            for line in self.log_tailer.read_new_lines(max_lines=20):
                self.event_log.append_line(line)
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        """Accept the close event and disconnect from the server."""
        self.client = None
        event.accept()
