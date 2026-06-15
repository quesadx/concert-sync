"""Network worker module for ConcertSync PySide6 client.

Wraps ConcertClient calls with thread-safe signal emission, mirroring
the TUI's daemon thread + call_from_thread pattern. Each worker class
inherits QObject and defines a do_work() method that runs the network
call on a background thread, emitting Qt signals on completion/error.

Usage:
    worker = ReserveWorker(client, "VIP", 0, 5)
    worker.finished.connect(on_reserve_done)
    worker.error.connect(on_reserve_error)
    run_worker(worker)  # dispatches do_work() on daemon thread
"""

import socket
import threading
import weakref

from PySide6.QtCore import QObject, Signal

from src.client.concert_client import ConcertClient, ConcertClientError


# Track active workers to prevent GC while threads are running
# (prevents use-after-free segfault in PySide6 signal emission).
_active_workers: set[weakref.ref] = set()
_active_workers_lock = threading.Lock()


class ReserveWorker(QObject):
    """Runs ConcertClient.reserve_seat() on a background thread."""

    finished = Signal(dict)  # Response dict
    error = Signal(str)  # Error message

    def __init__(self, client: ConcertClient, section: str, row: int, col: int) -> None:
        """Initialize the worker with reservation parameters.

        Args:
            client: Connected ConcertClient instance.
            section: Section name (VIP, PREFERENTIAL, GENERAL).
            row: Row index (0-based).
            col: Column index (0-based).
        """
        super().__init__()
        self.client = client
        self.section = section
        self.row = row
        self.col = col

    def do_work(self) -> None:
        """Execute reserve_seat on a background thread."""
        try:
            response = self.client.reserve_seat(self.section, self.row, self.col)
            self.finished.emit(response)
        except ConcertClientError as e:
            self.error.emit(str(e))


class ConfirmWorker(QObject):
    """Runs ConcertClient.confirm() on a background thread."""

    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, client: ConcertClient, tx_id: str) -> None:
        """Initialize the worker with a transaction ID.

        Args:
            client: Connected ConcertClient instance.
            tx_id: Transaction ID to confirm.
        """
        super().__init__()
        self.client = client
        self.tx_id = tx_id

    def do_work(self) -> None:
        """Execute confirm on a background thread."""
        try:
            response = self.client.confirm(self.tx_id)
            self.finished.emit(response)
        except ConcertClientError as e:
            self.error.emit(str(e))


class CancelWorker(QObject):
    """Runs ConcertClient.cancel() on a background thread."""

    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, client: ConcertClient, tx_id: str) -> None:
        """Initialize the worker with a transaction ID.

        Args:
            client: Connected ConcertClient instance.
            tx_id: Transaction ID to cancel.
        """
        super().__init__()
        self.client = client
        self.tx_id = tx_id

    def do_work(self) -> None:
        """Execute cancel on a background thread."""
        try:
            response = self.client.cancel(self.tx_id)
            self.finished.emit(response)
        except ConcertClientError as e:
            self.error.emit(str(e))


class ReserveSelectedWorker(QObject):
    """Runs ConcertClient.reserve_selected() on a background thread."""

    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, client: ConcertClient, seats: list) -> None:
        """Initialize the worker with a list of seat selections.

        Args:
            client: Connected ConcertClient instance.
            seats: List of dicts with 'section', 'row', 'col' keys.
        """
        super().__init__()
        self.client = client
        self.seats = seats

    def do_work(self) -> None:
        """Execute reserve_selected on a background thread."""
        try:
            response = self.client.reserve_selected(self.seats)
            self.finished.emit(response)
        except ConcertClientError as e:
            self.error.emit(str(e))


class PollWorker(QObject):
    """Runs QUERY + QUERY_SEAT_MAP on a background thread, emits combined result.

    Mirrors _refresh_query_worker from frontend_tui/app.py lines 422-448.
    """

    finished = Signal(dict, dict, object)  # sections, seat_map_payload, user_session
    error = Signal(str)

    def __init__(self, client: ConcertClient) -> None:
        """Initialize the poll worker.

        Args:
            client: Connected ConcertClient instance.
        """
        super().__init__()
        self.client = client

    def do_work(self) -> None:
        """Execute query() and query_seat_map() on a background thread.

        Combines section counts and full seat map into a single signal emission.
        """
        try:
            response = self.client.query()
            sections = response.get("sections", {})
            seat_map_response = self.client.query_seat_map()
            seat_map_payload = seat_map_response.get("seat_map", {})
            user_session = seat_map_response.get("user_session", None)
            self.finished.emit(sections, seat_map_payload, user_session)
        except ConcertClientError as e:
            self.error.emit(str(e))


class SubscribeNotificationsWorker(QObject):
    """Subscribes to push notifications and returns the long-lived socket."""

    finished = Signal(object)  # subscription socket
    error = Signal(str)

    def __init__(self, client: ConcertClient) -> None:
        """Initialize the subscription worker.

        Args:
            client: Connected ConcertClient instance.
        """
        super().__init__()
        self.client = client

    def do_work(self) -> None:
        """Execute subscribe_notifications on a background thread."""
        try:
            sub_sock = self.client.subscribe_notifications(self.client.user_id)
            self.finished.emit(sub_sock)
        except ConcertClientError as e:
            self.error.emit(str(e))


class ReadNotificationWorker(QObject):
    """Reads a single notification from the subscription socket (non-blocking)."""

    finished = Signal(dict)  # notification dict

    def __init__(self, sub_sock: socket.socket) -> None:
        """Initialize with the subscription socket.

        Args:
            sub_sock: Socket returned by subscribe_notifications.
        """
        super().__init__()
        self.sub_sock = sub_sock

    def do_work(self) -> None:
        """Read one notification with a short timeout."""
        import json as _json

        try:
            self.sub_sock.settimeout(0.1)
            data = self.sub_sock.recv(4096)
            if not data:
                return
            raw = data.decode().strip()
            if not raw:
                return
            for line in raw.split("\n"):
                line = line.strip()
                if not line:
                    continue
                notif = _json.loads(line)
                if isinstance(notif, dict) and notif.get("type") == "NOTIFICATION":
                    self.finished.emit(notif)
        except socket.timeout:
            pass
        except Exception:
            pass


def run_worker(worker: QObject) -> None:
    """Start a worker on a daemon background thread.

    The worker emits Qt signals on completion/error; the caller connects
    slots to those signals before calling run_worker(). The worker is kept
    alive via _active_workers until the thread finishes.

    Args:
        worker: A worker QObject with a do_work() method.
    """
    ref = weakref.ref(worker)
    with _active_workers_lock:
        _active_workers.add(ref)

    original = worker.do_work

    def wrapped():
        try:
            original()
        finally:
            with _active_workers_lock:
                _active_workers.discard(ref)
            worker.deleteLater()

    thread = threading.Thread(target=wrapped, daemon=True)
    thread.start()
