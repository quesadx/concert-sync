from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Dict, List, Optional, Set

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
        self.selected_map_section = "GENERAL"
        self.requests_this_tick = 0
        self.request_history: List[int] = []
        self.thread_history: List[int] = []
        self.error_history: List[int] = []
        self.pending_clicks: Set[tuple[str, int, int]] = set()
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
                    placeholder="VIP:0:0,VIP:0:1,GENERAL:2:3",
                    id="batch-input",
                )
                yield Static(
                    "Format: SECTION:ROW:COL\n"
                    "Example: VIP:0:0,VIP:0:1,GENERAL:2:3",
                    id="batch-help",
                )
                yield Button("Reserve Batch", id="reserve-batch-btn", variant="success")

                yield Static("Transaction actions", classes="panel-title")
                yield Input(placeholder="Transaction ID", id="tx-input")
                with Horizontal(id="tx-helpers-row"):
                    yield Button("Use Last TX", id="use-last-tx-btn")
                    yield Button("Use Last ACTIVE", id="use-last-active-tx-btn")
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

                yield Static("Visual seat map (click a seat to select)", classes="panel-title")
                yield Select(
                    SECTION_OPTIONS,
                    value="GENERAL",
                    id="map-section-select",
                    allow_blank=False,
                )
                yield Static("A=AVAILABLE  R=RESERVED  S=SOLD  (click an available seat to reserve)", id="seat-map-legend")
                yield DataTable(id="seat-map-table")

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

        seat_map_table = self.query_one("#seat-map-table", DataTable)
        seat_map_table.cursor_type = "cell"

        self.set_interval(1.0, self._refresh_every_second)
        self._render_section_table()
        self._render_seat_map()
        self._render_session_table()
        self._render_metrics_panels()

    def action_manual_refresh(self) -> None:
        self._refresh_query(silent=False)

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        """Handle seat selection from the visual seat table."""
        if event.data_table.id != "seat-map-table":
            return

        try:
            grid = self.seat_map_snapshot.get(self.selected_map_section, [])
            if not grid:
                return

            row_idx = event.coordinate.row
            col_idx = event.coordinate.column
            if row_idx < 0 or row_idx >= len(grid) or col_idx < 0 or col_idx >= len(grid[row_idx]):
                return

            section = self.selected_map_section
            state = grid[row_idx][col_idx]

            self.query_one("#row-input", Input).value = str(row_idx)
            self.query_one("#col-input", Input).value = str(col_idx)
            self.query_one("#section-select", Select).value = section

            self._append_event(
                f"[UI] Clicked seat {section}({row_idx},{col_idx}) - state={state}"
            )

            if state == "AVAILABLE":
                seat_key = (section, row_idx, col_idx)
                if seat_key not in self.pending_clicks:
                    self.pending_clicks.add(seat_key)
                    self._set_status(f"Reserving {section}({row_idx},{col_idx})...")
                    threading.Thread(
                        target=self._reserve_click_worker,
                        args=(section, row_idx, col_idx, seat_key),
                        daemon=True,
                    ).start()
                else:
                    self._set_status(
                        f"Already reserving {section}({row_idx},{col_idx})..."
                    )
            else:
                self._set_status(
                    f"Selected {section}({row_idx},{col_idx}) - State: {state}"
                )
        except Exception as e:
            self._set_status(f"Seat select error: {e}")

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
        elif button_id == "use-last-tx-btn":
            self._fill_transaction_input_with_latest(active_only=False)
        elif button_id == "use-last-active-tx-btn":
            self._fill_transaction_input_with_latest(active_only=True)
        elif button_id == "query-btn":
            self._refresh_query(silent=False)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "map-section-select" and event.value:
            self.selected_map_section = str(event.value)
            self._render_seat_map()

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
            self._ensure_client()
            section = self.query_one("#section-select", Select).value
            row = int(self.query_one("#row-input", Input).value.strip())
            col = int(self.query_one("#col-input", Input).value.strip())
        except ValueError:
            self._set_status("Row and column must be valid integers.")
            return
        except ConcertClientError as exc:
            self._set_status(f"Reserve failed: {exc}")
            self._append_event(f"[RESERVE] Failed: {exc}")
            return

        self._set_status(f"Reserving {section}({row},{col})...")
        self._append_event(f"[RESERVE] tx=start seat={section}({row},{col})")
        threading.Thread(
            target=self._reserve_single_seat_worker,
            args=(section, row, col),
            daemon=True,
        ).start()

    def _reserve_single_seat_worker(self, section: str, row: int, col: int) -> None:
        try:
            response = self._request(
                lambda: self._ensure_client().reserve_seat(section, row, col)
            )
            try:
                self.call_from_thread(
                    self._reserve_single_seat_succeeded,
                    section,
                    row,
                    col,
                    response,
                )
            except Exception:
                self._reserve_single_seat_succeeded(section, row, col, response)
        except ConcertClientError as exc:
            try:
                self.call_from_thread(
                    self._reserve_single_seat_failed,
                    section,
                    row,
                    col,
                    str(exc),
                )
            except Exception:
                self._reserve_single_seat_failed(section, row, col, str(exc))

    def _reserve_single_seat_succeeded(self, section: str, row: int, col: int, response) -> None:
        transaction_id = response["transaction_id"]
        ttl = int(response.get("ttl", 0))

        self.sessions[transaction_id] = TrackedSession(
            transaction_id=transaction_id,
            operation_type="SINGLE",
            seat_summary=f"{section}({row},{col})",
            ttl_seconds=ttl,
            created_at=time.time(),
        )
        self.query_one("#tx-input", Input).value = transaction_id

        self._set_status(f"Reserved {section}({row},{col}) -> {transaction_id}")
        self._append_event(f"[RESERVE] tx={transaction_id} seat={section}({row},{col}) ttl={ttl}s")
        self._render_session_table()
        self._refresh_query(silent=True)

    def _reserve_single_seat_failed(self, section: str, row: int, col: int, error_message: str) -> None:
        self._set_status(f"Reserve failed: {error_message}")
        self._append_event(f"[RESERVE] Failed: {error_message}")

    def _reserve_click_submit(self, section: str, row: int, col: int):
        client = self._ensure_client()
        return self._request(lambda: client.reserve_seat(section, row, col))

    def _reserve_click_succeeded(self, section: str, row: int, col: int, response) -> None:
        transaction_id = response["transaction_id"]
        ttl = int(response.get("ttl", 0))

        self.sessions[transaction_id] = TrackedSession(
            transaction_id=transaction_id,
            operation_type="CLICK",
            seat_summary=f"{section}({row},{col})",
            ttl_seconds=ttl,
            created_at=time.time(),
        )
        self.query_one("#tx-input", Input).value = transaction_id

        self._set_status(f"Reserved {section}({row},{col}) via click -> {transaction_id}")
        self._append_event(f"[RESERVE_CLICK] tx={transaction_id} seat={section}({row},{col}) ttl={ttl}s")
        self._render_session_table()
        self._refresh_query(silent=True)

    def _reserve_click_failed(self, section: str, row: int, col: int, error_message: str) -> None:
        self._set_status(f"Click reserve failed: {error_message}")
        self._append_event(f"[RESERVE_CLICK] Failed: {error_message}")

    def _reserve_click_worker(self, section: str, row: int, col: int, seat_key: tuple[str, int, int]) -> None:
        try:
            response = self._reserve_click_submit(section, row, col)
            try:
                self.call_from_thread(self._reserve_click_succeeded, section, row, col, response)
            except Exception:
                self._reserve_click_succeeded(section, row, col, response)
        except ConcertClientError as exc:
            try:
                self.call_from_thread(self._reserve_click_failed, section, row, col, str(exc))
            except Exception:
                self._reserve_click_failed(section, row, col, str(exc))
        finally:
            # Remove the pending marker in the main thread context.
            try:
                self.call_from_thread(self.pending_clicks.discard, seat_key)
            except Exception:
                self.pending_clicks.discard(seat_key)

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
            self.query_one("#tx-input", Input).value = transaction_id

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
        tx_id = self._resolve_transaction_id_from_input()
        if tx_id is None:
            return

        try:
            self._ensure_client()
        except ConcertClientError as exc:
            self._set_status(f"Confirm failed: {exc}")
            self._append_event(f"[CONFIRM] Failed: {exc}")
            return

        self._set_status(f"Confirming {tx_id}...")
        self._append_event(f"[CONFIRM] tx={tx_id} started")
        threading.Thread(
            target=self._confirm_transaction_worker,
            args=(tx_id,),
            daemon=True,
        ).start()

    def _cancel_transaction(self) -> None:
        tx_id = self._resolve_transaction_id_from_input()
        if tx_id is None:
            return

        try:
            self._ensure_client()
        except ConcertClientError as exc:
            self._set_status(f"Cancel failed: {exc}")
            self._append_event(f"[CANCEL] Failed: {exc}")
            return

        self._set_status(f"Cancelling {tx_id}...")
        self._append_event(f"[CANCEL] tx={tx_id} started")
        threading.Thread(
            target=self._cancel_transaction_worker,
            args=(tx_id,),
            daemon=True,
        ).start()

    def _confirm_transaction_worker(self, tx_id: str) -> None:
        try:
            client = self._ensure_client()
            self._request(lambda: client.confirm(tx_id))
            try:
                self.call_from_thread(self._confirm_transaction_succeeded, tx_id)
            except Exception:
                self._confirm_transaction_succeeded(tx_id)
        except ConcertClientError as exc:
            try:
                self.call_from_thread(self._confirm_transaction_failed, tx_id, str(exc))
            except Exception:
                self._confirm_transaction_failed(tx_id, str(exc))

    def _cancel_transaction_worker(self, tx_id: str) -> None:
        try:
            client = self._ensure_client()
            self._request(lambda: client.cancel(tx_id))
            try:
                self.call_from_thread(self._cancel_transaction_succeeded, tx_id)
            except Exception:
                self._cancel_transaction_succeeded(tx_id)
        except ConcertClientError as exc:
            try:
                self.call_from_thread(self._cancel_transaction_failed, tx_id, str(exc))
            except Exception:
                self._cancel_transaction_failed(tx_id, str(exc))

    def _confirm_transaction_succeeded(self, tx_id: str) -> None:
        self._set_status(f"Confirmed {tx_id}")
        self._append_event(f"[CONFIRM] tx={tx_id}")
        if tx_id in self.sessions:
            self.sessions[tx_id].state = "CONFIRMED"
        self._render_session_table()
        self._refresh_query(silent=True)

    def _confirm_transaction_failed(self, tx_id: str, error_message: str) -> None:
        self._set_status(f"Confirm failed: {error_message}")
        self._append_event(f"[CONFIRM] Failed: {error_message}")

    def _cancel_transaction_succeeded(self, tx_id: str) -> None:
        self._set_status(f"Cancelled {tx_id}")
        self._append_event(f"[CANCEL] tx={tx_id}")
        if tx_id in self.sessions:
            self.sessions[tx_id].state = "CANCELLED"
        self._render_session_table()
        self._refresh_query(silent=True)

    def _cancel_transaction_failed(self, tx_id: str, error_message: str) -> None:
        self._set_status(f"Cancel failed: {error_message}")
        self._append_event(f"[CANCEL] Failed: {error_message}")

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
    def _seat_token(state: str) -> str:
        if state == "AVAILABLE":
            return "A"
        if state == "RESERVED":
            return "R"
        if state == "SOLD":
            return "S"
        return "?"

    def _render_seat_map(self) -> None:
        """Render seat map as a simple clickable table."""
        table = self.query_one("#seat-map-table", DataTable)
        table.clear(columns=True)

        selected_grid = self.seat_map_snapshot.get(self.selected_map_section, [])
        if not selected_grid:
            self.query_one("#seat-map-legend", Static).update("No seat map data")
            return

        num_cols = len(selected_grid[0])
        table.add_columns(*[str(col_idx) for col_idx in range(num_cols)])

        for row_idx, row in enumerate(selected_grid):
            table.add_row(
                *[self._seat_token(state) for state in row],
                label=f"{row_idx:02d}",
            )

        self.query_one(
            "#seat-map-legend", Static
        ).update("A=AVAILABLE  R=RESERVED  S=SOLD  (click an available seat to reserve)")

    def _latest_session(self, active_only: bool) -> Optional[TrackedSession]:
        filtered = [
            session
            for session in self.sessions.values()
            if (session.state == "ACTIVE" if active_only else True)
        ]
        if not filtered:
            return None
        return max(filtered, key=lambda session: session.created_at)

    def _fill_transaction_input_with_latest(self, active_only: bool) -> None:
        latest = self._latest_session(active_only=active_only)
        if latest is None:
            if active_only:
                self._set_status("No ACTIVE transactions tracked yet.")
            else:
                self._set_status("No transactions tracked yet.")
            return

        self.query_one("#tx-input", Input).value = latest.transaction_id
        state_hint = "ACTIVE" if active_only else latest.state
        self._set_status(f"Transaction input set to {latest.transaction_id} ({state_hint}).")

    def _resolve_transaction_id_from_input(self) -> Optional[str]:
        tx_input = self.query_one("#tx-input", Input)
        tx_id = tx_input.value.strip()
        if tx_id:
            return tx_id

        # Friendly fallback when clipboard is inconvenient.
        latest_active = self._latest_session(active_only=True)
        if latest_active is not None:
            tx_input.value = latest_active.transaction_id
            self._set_status(
                f"Transaction ID was empty. Using latest ACTIVE: {latest_active.transaction_id}."
            )
            return latest_active.transaction_id

        self._set_status("Transaction ID is required. Reserve first or press Use Last ACTIVE.")
        return None

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
