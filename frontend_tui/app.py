from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Dict, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, RichLog, Select, Static

from src.client.concert_client import ConcertClient, ConcertClientError
from src.utils.config import SECTION_CONFIG
from src.utils.enums import Section


SECTION_OPTIONS = [
    ("VIP", "VIP"),
    ("PREFERENTIAL", "PREFERENTIAL"),
    ("GENERAL", "GENERAL"),
]


@dataclass
class TrackedSession:
    transaction_id: str
    operation_type: str
    seat_summary: str
    ttl_seconds: int
    created_at: float
    state: str = "ACTIVE"

    @property
    def expires_at(self) -> float:
        return self.created_at + self.ttl_seconds

    def ttl_remaining(self) -> int:
        if self.state != "ACTIVE":
            return 0
        return max(0, int(self.expires_at - time.time()))


class LogTailer:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.position = 0
        self.reset_position_to_eof()

    def set_file_path(self, file_path: Path) -> None:
        self.file_path = file_path
        self.position = 0
        self.reset_position_to_eof()

    def reset_position_to_eof(self) -> None:
        try:
            with self.file_path.open("r", encoding="utf-8") as handle:
                handle.seek(0, 2)
                self.position = handle.tell()
        except FileNotFoundError:
            self.position = 0

    def read_new_lines(self, max_lines: int = 100) -> List[str]:
        try:
            with self.file_path.open("r", encoding="utf-8") as handle:
                handle.seek(self.position)
                lines = handle.readlines()
                self.position = handle.tell()
        except FileNotFoundError:
            return []

        cleaned = [line.rstrip("\n") for line in lines if line.strip()]
        if len(cleaned) > max_lines:
            return cleaned[-max_lines:]
        return cleaned


class ConcertTextualApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "ConcertSync Terminal Console"
    SUB_TITLE = "Textual client for reservations and live TTL monitoring"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f5", "manual_refresh", "Refresh"),
    ]

    def __init__(self):
        super().__init__()
        self.client: Optional[ConcertClient] = None
        self.connected_host: str = "localhost"
        self.connected_port: int = 9999
        self.sessions: Dict[str, TrackedSession] = {}
        self.section_snapshot = {
            "VIP": {"available": 0, "reserved": 0, "sold": 0},
            "PREFERENTIAL": {"available": 0, "reserved": 0, "sold": 0},
            "GENERAL": {"available": 0, "reserved": 0, "sold": 0},
        }
        self.seat_map_snapshot = self._build_empty_seat_map()
        self.requests_this_tick = 0
        self.request_history: List[int] = []
        self.thread_history: List[int] = []
        self.error_history: List[int] = []
        self.log_tailer = LogTailer(Path("logs/system.log"))

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            with Vertical(id="controls-panel"):
                yield Static("Connection", classes="panel-title")
                with Horizontal(id="connection-row"):
                    yield Input(value="localhost", placeholder="Host", id="host-input")
                    yield Input(value="9999", placeholder="Port", id="port-input")
                yield Button("Connect", id="connect-btn", variant="primary")

                yield Static("Server log path", classes="panel-title")
                with Horizontal(id="log-row"):
                    yield Input(value="logs/system.log", placeholder="Path to system.log", id="log-path-input")
                    yield Button("Apply", id="apply-log-btn")

                yield Static("Reserve single seat", classes="panel-title")
                yield Select(SECTION_OPTIONS, value="VIP", id="section-select", allow_blank=False)
                with Horizontal(id="seat-row"):
                    yield Input(placeholder="Row", id="row-input")
                    yield Input(placeholder="Column", id="col-input")
                yield Button("Reserve Seat", id="reserve-btn", variant="success")

                yield Static("Reserve batch seats", classes="panel-title")
                yield Input(
                    placeholder="Example: VIP:0:0,VIP:0:1,GENERAL:2:3",
                    id="batch-input",
                )
                yield Button("Reserve Batch", id="reserve-batch-btn", variant="success")

                yield Static("Transaction actions", classes="panel-title")
                yield Input(placeholder="Transaction ID", id="tx-input")
                with Horizontal(id="tx-row"):
                    yield Button("Confirm", id="confirm-btn", variant="primary")
                    yield Button("Cancel", id="cancel-btn", variant="warning")

                with Horizontal(id="quick-row"):
                    yield Button("Refresh Now", id="query-btn")

                yield Static("Ready", id="status-line")

            with Vertical(id="dashboard-panel"):
                yield Static(
                    "Not connected. Press Connect to start querying the server.",
                    id="connection-status",
                )
                yield Static("Seat availability by section", classes="panel-title")
                yield DataTable(id="section-table")

                yield Static("Visual seat map", classes="panel-title")
                yield Static("", id="seat-map-view")

                yield Static("Tracked transactions (TTL)", classes="panel-title")
                yield DataTable(id="session-table")

                yield Static("Requests per refresh tick", classes="panel-title")
                yield Static("", id="request-chart")
                yield Static("Thread and error events from log", classes="panel-title")
                yield Static("", id="thread-chart")

                yield Static("Live event stream", classes="panel-title")
                yield RichLog(id="event-log", wrap=False, markup=False, highlight=True)

        yield Footer()

    def on_mount(self) -> None:
        section_table = self.query_one("#section-table", DataTable)
        section_table.add_columns("Section", "Available", "Reserved", "Sold")

        session_table = self.query_one("#session-table", DataTable)
        session_table.add_columns("Transaction", "Type", "State", "TTL", "Seats")

        self.set_interval(1.0, self._refresh_every_second)
        self._render_section_table()
        self._render_seat_map()
        self._render_session_table()
        self._render_metrics_panels()

    def action_manual_refresh(self) -> None:
        self._refresh_query(silent=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "connect-btn":
            self._connect_client()
        elif button_id == "apply-log-btn":
            self._apply_log_path()
        elif button_id == "reserve-btn":
            self._reserve_single_seat()
        elif button_id == "reserve-batch-btn":
            self._reserve_batch_seats()
        elif button_id == "confirm-btn":
            self._confirm_transaction()
        elif button_id == "cancel-btn":
            self._cancel_transaction()
        elif button_id == "query-btn":
            self._refresh_query(silent=False)

    def _refresh_every_second(self) -> None:
        self._refresh_query(silent=True)
        self._refresh_tracked_ttls()
        self._refresh_log_metrics()

        self.request_history.append(self.requests_this_tick)
        if len(self.request_history) > 40:
            self.request_history = self.request_history[-40:]
        self.requests_this_tick = 0

        self._render_session_table()
        self._render_metrics_panels()

    def _set_status(self, message: str) -> None:
        self.query_one("#status-line", Static).update(message)

    def _append_event(self, message: str) -> None:
        event_log = self.query_one("#event-log", RichLog)
        event_log.write(message)

    def _connect_client(self) -> None:
        host = self.query_one("#host-input", Input).value.strip() or "localhost"
        port_text = self.query_one("#port-input", Input).value.strip() or "9999"

        try:
            port = int(port_text)
        except ValueError:
            self._set_status("Port must be a number.")
            return

        self.client = ConcertClient(host=host, port=port)
        self.connected_host = host
        self.connected_port = port

        try:
            self._request(lambda: self.client.query())
            self.query_one("#connection-status", Static).update(
                f"Connected to {host}:{port} - live polling every second"
            )
            self._set_status("Connected successfully.")
            self._append_event(f"[CLIENT] Connected to {host}:{port}")
            self._refresh_query(silent=False)
        except ConcertClientError as exc:
            self.client = None
            self.query_one("#connection-status", Static).update(
                f"Connection failed to {host}:{port}"
            )
            self._set_status(f"Connection error: {exc}")
            self._append_event(f"[CLIENT] Connection failed: {exc}")

    def _apply_log_path(self) -> None:
        path_value = self.query_one("#log-path-input", Input).value.strip()
        if not path_value:
            self._set_status("Log path cannot be empty.")
            return

        self.log_tailer.set_file_path(Path(path_value))
        self.thread_history.clear()
        self.error_history.clear()
        self._set_status(f"Log path updated to {path_value}")
        self._append_event(f"[CLIENT] Log tail switched to {path_value}")

    def _ensure_client(self) -> ConcertClient:
        if self.client is None:
            raise ConcertClientError("Not connected. Press Connect first.")
        return self.client

    def _request(self, fn):
        self.requests_this_tick += 1
        return fn()

    @staticmethod
    def _build_empty_seat_map() -> Dict[str, List[List[str]]]:
        snapshot: Dict[str, List[List[str]]] = {}
        for section in Section:
            cfg = SECTION_CONFIG[section]
            rows = cfg["rows"]
            cols = cfg["cols"]
            snapshot[section.name] = [["AVAILABLE" for _ in range(cols)] for _ in range(rows)]
        return snapshot

    def _refresh_query(self, silent: bool) -> None:
        if self.client is None:
            return

        try:
            response = self._request(lambda: self.client.query())
            sections = response.get("sections", {})
            for section_name in self.section_snapshot:
                if section_name in sections:
                    self.section_snapshot[section_name] = sections[section_name]

            seat_map_response = self._request(lambda: self.client.query_seat_map())
            seat_map_payload = seat_map_response.get("seat_map", {})
            if seat_map_payload:
                for section_name in self.seat_map_snapshot:
                    if section_name in seat_map_payload:
                        self.seat_map_snapshot[section_name] = seat_map_payload[section_name]

            self._render_section_table()
            self._render_seat_map()
            if not silent:
                self._set_status("Section data refreshed.")
        except ConcertClientError as exc:
            if not silent:
                self._set_status(f"Refresh error: {exc}")
                self._append_event(f"[CLIENT] Query failed: {exc}")

    def _reserve_single_seat(self) -> None:
        try:
            client = self._ensure_client()
            section = self.query_one("#section-select", Select).value
            row = int(self.query_one("#row-input", Input).value.strip())
            col = int(self.query_one("#col-input", Input).value.strip())

            response = self._request(lambda: client.reserve_seat(section, row, col))
            transaction_id = response["transaction_id"]
            ttl = int(response.get("ttl", 0))

            self.sessions[transaction_id] = TrackedSession(
                transaction_id=transaction_id,
                operation_type="SINGLE",
                seat_summary=f"{section}({row},{col})",
                ttl_seconds=ttl,
                created_at=time.time(),
            )

            self._set_status(f"Reserved {section}({row},{col}) -> {transaction_id}")
            self._append_event(f"[RESERVE] tx={transaction_id} seat={section}({row},{col}) ttl={ttl}s")
            self._render_session_table()
            self._refresh_query(silent=True)
        except ValueError:
            self._set_status("Row and column must be valid integers.")
        except ConcertClientError as exc:
            self._set_status(f"Reserve failed: {exc}")
            self._append_event(f"[RESERVE] Failed: {exc}")

    def _parse_batch_input(self, text: str) -> List[dict]:
        seats = []
        tokens = [chunk.strip() for chunk in text.split(",") if chunk.strip()]
        if not tokens:
            raise ValueError("Batch input is empty.")

        for token in tokens:
            parts = [part.strip().upper() for part in token.split(":")]
            if len(parts) != 3:
                raise ValueError("Use SECTION:ROW:COL format separated by commas.")

            section, row_str, col_str = parts
            if section not in {"VIP", "PREFERENTIAL", "GENERAL"}:
                raise ValueError(f"Unsupported section in batch: {section}")

            row = int(row_str)
            col = int(col_str)
            seats.append({"section": section, "row": row, "col": col})

        return seats

    def _reserve_batch_seats(self) -> None:
        try:
            client = self._ensure_client()
            batch_raw = self.query_one("#batch-input", Input).value.strip()
            seats = self._parse_batch_input(batch_raw)

            response = self._request(
                lambda: client.send_request({"action": "RESERVE_BATCH", "seats": seats})
            )

            transaction_id = response["transaction_id"]
            ttl = int(response.get("ttl", 0))
            seat_summary = ", ".join(
                f"{seat['section']}({seat['row']},{seat['col']})" for seat in seats
            )

            self.sessions[transaction_id] = TrackedSession(
                transaction_id=transaction_id,
                operation_type="BATCH",
                seat_summary=seat_summary,
                ttl_seconds=ttl,
                created_at=time.time(),
            )

            self._set_status(f"Batch reserved -> {transaction_id}")
            self._append_event(f"[RESERVE_BATCH] tx={transaction_id} seats={seat_summary} ttl={ttl}s")
            self._render_session_table()
            self._refresh_query(silent=True)
        except ValueError as exc:
            self._set_status(f"Batch parse error: {exc}")
        except ConcertClientError as exc:
            self._set_status(f"Batch reserve failed: {exc}")
            self._append_event(f"[RESERVE_BATCH] Failed: {exc}")

    def _confirm_transaction(self) -> None:
        try:
            client = self._ensure_client()
            tx_id = self.query_one("#tx-input", Input).value.strip()
            if not tx_id:
                self._set_status("Transaction ID is required.")
                return

            self._request(lambda: client.confirm(tx_id))
            self._set_status(f"Confirmed {tx_id}")
            self._append_event(f"[CONFIRM] tx={tx_id}")

            if tx_id in self.sessions:
                self.sessions[tx_id].state = "CONFIRMED"
            self._render_session_table()
            self._refresh_query(silent=True)
        except ConcertClientError as exc:
            self._set_status(f"Confirm failed: {exc}")
            self._append_event(f"[CONFIRM] Failed: {exc}")

    def _cancel_transaction(self) -> None:
        try:
            client = self._ensure_client()
            tx_id = self.query_one("#tx-input", Input).value.strip()
            if not tx_id:
                self._set_status("Transaction ID is required.")
                return

            self._request(lambda: client.cancel(tx_id))
            self._set_status(f"Cancelled {tx_id}")
            self._append_event(f"[CANCEL] tx={tx_id}")

            if tx_id in self.sessions:
                self.sessions[tx_id].state = "CANCELLED"
            self._render_session_table()
            self._refresh_query(silent=True)
        except ConcertClientError as exc:
            self._set_status(f"Cancel failed: {exc}")
            self._append_event(f"[CANCEL] Failed: {exc}")

    def _refresh_tracked_ttls(self) -> None:
        now = time.time()
        for session in self.sessions.values():
            if session.state == "ACTIVE" and session.expires_at <= now:
                session.state = "EXPIRED"

    def _refresh_log_metrics(self) -> None:
        lines = self.log_tailer.read_new_lines()
        thread_count = 0
        error_count = 0

        for line in lines:
            if "[THREAD]" in line:
                thread_count += 1
            if "[ERROR]" in line:
                error_count += 1
            self._append_event(line)

        self.thread_history.append(thread_count)
        self.error_history.append(error_count)

        if len(self.thread_history) > 40:
            self.thread_history = self.thread_history[-40:]
        if len(self.error_history) > 40:
            self.error_history = self.error_history[-40:]

    def _render_section_table(self) -> None:
        table = self.query_one("#section-table", DataTable)
        table.clear()

        for section_name in ["VIP", "PREFERENTIAL", "GENERAL"]:
            counts = self.section_snapshot[section_name]
            table.add_row(
                section_name,
                str(counts.get("available", 0)),
                str(counts.get("reserved", 0)),
                str(counts.get("sold", 0)),
            )

    def _render_session_table(self) -> None:
        table = self.query_one("#session-table", DataTable)
        table.clear()

        sorted_sessions = sorted(
            self.sessions.values(),
            key=lambda item: item.created_at,
            reverse=True,
        )

        for session in sorted_sessions[:30]:
            ttl_remaining = session.ttl_remaining()
            ttl_text = f"{ttl_remaining:>3}s" if session.state == "ACTIVE" else "-"
            table.add_row(
                session.transaction_id,
                session.operation_type,
                session.state,
                ttl_text,
                session.seat_summary,
            )

    @staticmethod
    def _seat_symbol(state: str) -> str:
        if state == "AVAILABLE":
            return "[green]●[/]"
        if state == "RESERVED":
            return "[yellow]●[/]"
        if state == "SOLD":
            return "[red]●[/]"
        return "[grey50]?[/]"

    def _render_section_grid(self, section_name: str, grid: List[List[str]]) -> str:
        if not grid:
            return f"[bold]{section_name}[/]: no data"

        max_cols = max(len(row) for row in grid)
        header = "    " + " ".join(f"{idx:02d}" for idx in range(max_cols))

        lines = [f"[bold cyan]{section_name}[/]", header]
        for row_index, row in enumerate(grid):
            cells = " ".join(self._seat_symbol(state) for state in row)
            lines.append(f"{row_index:02d}  {cells}")

        return "\n".join(lines)

    def _render_seat_map(self) -> None:
        legend = "[green]● AVAILABLE[/]   [yellow]● RESERVED[/]   [red]● SOLD[/]"
        section_blocks = []
        for section_name in ["VIP", "PREFERENTIAL", "GENERAL"]:
            section_blocks.append(
                self._render_section_grid(section_name, self.seat_map_snapshot.get(section_name, []))
            )

        full_text = legend + "\n\n" + "\n\n".join(section_blocks)
        self.query_one("#seat-map-view", Static).update(full_text)

    def _render_metrics_panels(self) -> None:
        request_chart = self._render_sparkline(self.request_history, "Requests/tick")
        thread_chart = self._render_sparkline(self.thread_history, "THREAD events")
        error_chart = self._render_sparkline(self.error_history, "ERROR events")

        self.query_one("#request-chart", Static).update(request_chart)
        self.query_one("#thread-chart", Static).update(f"{thread_chart}\n{error_chart}")

    @staticmethod
    def _render_sparkline(values: List[int], label: str) -> str:
        if not values:
            return f"{label}: no data"

        charset = "▁▂▃▄▅▆▇█"
        window = values[-40:]
        peak = max(window)

        if peak <= 0:
            spark = "▁" * len(window)
        else:
            spark = "".join(
                charset[min(len(charset) - 1, int((value / peak) * (len(charset) - 1)))]
                for value in window
            )

        return f"{label}: {spark}  peak={peak}"
