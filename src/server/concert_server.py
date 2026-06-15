import socket
import threading
import time
from collections import defaultdict

from src.server.listener_thread import ListenerThread
from src.server.monitor_thread import MonitorThread
from src.server.notification_manager import NotificationManager, NotifierThread
from src.server.session_manager import SessionManager, UserSession
from src.shared_resources.global_log import GlobalLog
from src.shared_resources.reservation_table import ReservationTable
from src.shared_resources.seat_matrix import SeatMatrix
from src.shared_resources.semaphore_manager import SemaphoreManager
from src.shared_resources.sqlite_store import SqliteStore
from src.synchronization.mutex_manager import MutexManager
from src.utils.config import SERVER_PORT
from src.utils.enums import ReservationStatus, SeatState, Section


class ConcertServer:
    def __init__(self, host="localhost", port=SERVER_PORT):
        self.host = host
        self.port = port
        self.seat_matrix = SeatMatrix()
        self.semaphore_mgr = SemaphoreManager()
        self.reservation_table = ReservationTable()
        self.global_log = GlobalLog()
        self.mutex_manager = MutexManager(self.seat_matrix, self.reservation_table)
        self.session_manager = SessionManager()
        self.store = SqliteStore()
        self.notification_manager = NotificationManager(self.global_log)
        self.notifier_thread = None

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(1.0)
        self.running = False
        self.monitor_thread = None
        self.listener_thread = None
        self.active_threads: list[threading.Thread] = []
        self.active_threads_lock = threading.Lock()

    def _load_persisted_state(self):
        """Restore server state from SQLite on startup.

        Loads seat matrix, active sessions, and semaphore counts from the
        persistent store. Expired sessions are released (seats and semaphore
        slots freed) and deleted from the DB. Non-expired sessions are
        reinserted into the in-memory session manager so users can reconnect
        and see their OWN_RESERVED seats.

        Semaphores are restored by counting RESERVED + SOLD seats per section
        in the loaded seat matrix and acquiring that many slots. Since semaphores
        are initialized at full capacity before this method runs, acquiring N
        slots leaves (capacity - N) available — matching the persisted state.
        """
        # ── Restore seat matrix ──────────────────────────────────────────
        loaded = self.store.load_all_seats()
        if loaded is not None:
            for section in Section:
                self.seat_matrix.seats[section] = loaded[section]

        # ── Restore sessions with TTL handling ───────────────────────────
        sessions_data = self.store.load_all_sessions()
        expired_count = 0
        restored_count = 0
        for sdata in sessions_data:
            try:
                session_state = ReservationStatus(sdata["state"])
                session = UserSession(
                    user_id=sdata["user_id"],
                    session_id=sdata["session_id"],
                    seats=sdata["seats"],
                    last_activity=sdata["last_activity"],
                    ttl_secs=sdata["ttl_secs"],
                    state=session_state,
                )
            except (KeyError, ValueError) as exc:
                self.global_log.append(
                    "ERROR",
                    f"Failed to restore session {sdata.get('user_id', '?')}: {exc}",
                )
                continue

            if session.is_expired:
                # Release seats and semaphore slots for expired sessions
                released_by_section: dict = {}
                for section, row, col in session.seats:
                    with self.seat_matrix.mutex_sections[section]:
                        if (
                            self.seat_matrix.seats[section][row][col]
                            == SeatState.RESERVED
                        ):
                            self.seat_matrix.seats[section][row][
                                col
                            ] = SeatState.AVAILABLE
                            released_by_section[section] = (
                                released_by_section.get(section, 0) + 1
                            )
                for section, count in released_by_section.items():
                    if count > 0:
                        self.semaphore_mgr.release_multiple(section, count)

                self.store.delete_session(session.user_id)
                expired_count += 1
                self.global_log.append(
                    "EXPIRE",
                    f"Startup: released expired session {session.session_id} "
                    f"(user={session.user_id}, seats={len(session.seats)})",
                )
            else:
                self.session_manager.set_session(session)
                restored_count += 1

        if restored_count > 0:
            self.global_log.append(
                "SERVER",
                f"Restored {restored_count} active session(s) from persistent store",
            )
        if expired_count > 0:
            self.global_log.append(
                "SERVER",
                f"Released {expired_count} expired session(s) on startup",
            )

        # ── Restore semaphore state ──────────────────────────────────────
        # Acquire slots for all RESERVED + SOLD seats to match the loaded matrix.
        # Semaphores were initialized at full capacity; acquiring N sets
        # available to (capacity - N).
        for section in Section:
            taken = 0
            for row in self.seat_matrix.seats[section]:
                for seat in row:
                    if seat in (SeatState.RESERVED, SeatState.SOLD):
                        taken += 1
            for _ in range(taken):
                self.semaphore_mgr.acquire(section, blocking=False)

    def _cleanup_stale_reservations(self):
        """Release seats from stale ReservationTable entries on startup.

        Iterates the reservation table, releases any ACTIVE reservations
        back to AVAILABLE, and restores semaphore capacity.
        Handles both 2-tuple (row, col) and 3-tuple (section, row, col) seat formats.
        """
        released_by_section = {}
        stale_count = 0

        with self.reservation_table.mutex_table:
            for tx_id, res in list(self.reservation_table.reservations.items()):
                if res.state == ReservationStatus.ACTIVE:
                    section = res.section
                    if section not in released_by_section:
                        released_by_section[section] = 0

                    for seat in res.seats:
                        if len(seat) == 3:
                            sec, row, col = seat
                            seat_section = sec
                        else:
                            row, col = seat
                            seat_section = section

                        with self.seat_matrix.mutex_sections[seat_section]:
                            if self.seat_matrix.seats[seat_section][row][col] == SeatState.RESERVED:
                                self.seat_matrix.seats[seat_section][row][col] = SeatState.AVAILABLE
                                released_by_section[section] += 1

                    del self.reservation_table.reservations[tx_id]
                    stale_count += 1

        for section, count in released_by_section.items():
            if count > 0:
                self.semaphore_mgr.release_multiple(section, count)

        if stale_count > 0:
            self.global_log.append(
                "CLEANUP",
                f"Released {stale_count} stale reservation(s): {dict(released_by_section)}",
            )

    def _release_all_sessions(self):
        """Release all ACTIVE session seats back to AVAILABLE on shutdown.

        Acquires per-session locks in the same table_and_sections hierarchy as
        expire_session. Double-checks session state inside the lock to avoid
        racing with in-flight TransactionalThreads.
        """
        sessions = self.session_manager.get_all_active()
        if not sessions:
            return

        total_released = 0
        for session in sessions:
            seats_by_section = {}
            for section, row, col in session.seats:
                if section not in seats_by_section:
                    seats_by_section[section] = []
                seats_by_section[section].append((row, col))

            ordered_sections = [s for s in (Section.VIP, Section.PREFERENTIAL, Section.GENERAL) if s in seats_by_section]

            with self.mutex_manager.table_and_sections(ordered_sections):
                current = self.session_manager.get_by_session_id(session.session_id)
                if current is None or current.state != ReservationStatus.ACTIVE:
                    continue

                released_counts = defaultdict(int)
                for section in ordered_sections:
                    for row, col in seats_by_section[section]:
                        if self.seat_matrix.seats[section][row][col] == SeatState.RESERVED:
                            self.seat_matrix.seats[section][row][col] = SeatState.AVAILABLE
                            released_counts[section] += 1

                self.session_manager.remove(session.user_id)

                for section, count in released_counts.items():
                    if count > 0:
                        self.semaphore_mgr.release_multiple(section, count)

                total_released += sum(released_counts.values())

        if total_released > 0:
            self.global_log.append(
                "SHUTDOWN",
                f"Released {total_released} seat(s) from {len(sessions)} session(s)",
            )

    def register_thread(self, thread: threading.Thread) -> None:
        with self.active_threads_lock:
            self.active_threads.append(thread)

    def unregister_thread(self, thread: threading.Thread) -> None:
        with self.active_threads_lock:
            self.active_threads[:] = [t for t in self.active_threads if t is not thread]

    def start(self):
        try:
            self.server_socket.bind((self.host, self.port))
        except OSError as e:
            self.global_log.append("ERROR", f"Failed to bind: {e}")
            self.running = False
            raise
        self.server_socket.listen(5)
        self.running = True

        self._load_persisted_state()

        self._cleanup_stale_reservations()

        self.monitor_thread = MonitorThread(self)
        self.monitor_thread.start()

        self.notifier_thread = NotifierThread(self)
        self.notifier_thread.start()

        self.listener_thread = ListenerThread(self)
        self.listener_thread.start()

        self.global_log.append("SERVER", f"Server started on {self.host}:{self.port}")

    def stop(self):
        self.running = False
        try:
            self.server_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            self.server_socket.close()
        except OSError:
            pass

        time.sleep(0.5)

        self._release_all_sessions()

        self.store.save_all_seats(self.seat_matrix)
        self.store.close()

        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2)

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)

        self.notification_manager.cleanup()

        with self.active_threads_lock:
            for t in self.active_threads:
                if t.is_alive():
                    t.join(timeout=1)
            self.active_threads.clear()

        self.global_log.append("SERVER", "Server stopped")