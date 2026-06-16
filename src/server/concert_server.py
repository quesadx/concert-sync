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
from src.utils.ticket_generator import TicketGenerator


class ConcertServer:
    def __init__(self, host="0.0.0.0", port=SERVER_PORT):
        self.host = host
        self.port = port
        self.seat_matrix = SeatMatrix()
        self.semaphore_mgr = SemaphoreManager()
        self.reservation_table = ReservationTable()
        self.global_log = GlobalLog()
        self.mutex_manager = MutexManager(self.seat_matrix, self.reservation_table)
        self.session_manager = SessionManager()
        self.store = SqliteStore(global_log=self.global_log)
        self.notification_manager = NotificationManager(self.global_log)
        self.ticket_generator = TicketGenerator(self.global_log)
        self.notifier_thread = None

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(1.0)
        self.running = False
        self.monitor_thread = None
        self.listener_thread = None
        self.active_threads: list[threading.Thread] = []
        self.active_threads_lock = threading.Lock()

    def _release_orphaned_reserved_seats(self):
        """Release RESERVED seats with no active session.

        After loading persisted state, any seat still in RESERVED state that
        is NOT referenced by any active session is an orphan — the reserving
        session was lost (e.g., server crash between RESERVE and CONFIRM).
        These seats are released back to AVAILABLE and semaphore slots freed.
        """
        total_released = 0
        released_by_section = defaultdict(int)

        for section in Section:
            mutex = self.seat_matrix.mutex_sections[section]
            with mutex:
                seats_grid = self.seat_matrix.seats[section]
                for row_idx, row in enumerate(seats_grid):
                    for col_idx, seat in enumerate(row):
                        if seat != SeatState.RESERVED:
                            continue
                        # Check if this seat belongs to any active session
                        has_owner = any(
                            (section, row_idx, col_idx) in s.seats
                            for s in self.session_manager.get_all_sessions()
                            if s.state == ReservationStatus.ACTIVE
                        )
                        if not has_owner:
                            seats_grid[row_idx][col_idx] = SeatState.AVAILABLE
                            released_by_section[section] += 1
                            total_released += 1

        for section, count in released_by_section.items():
            if count > 0:
                self.semaphore_mgr.release_multiple(section, count)

        if total_released > 0:
            self.global_log.append(
                "CLEANUP",
                f"Released {total_released} orphaned RESERVED seat(s): "
                f"{dict(released_by_section)}",
            )

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
                # Validate that this session's seats are actually RESERVED
                # in the loaded matrix. After an unclean shutdown or
                # stop()-order inconsistency, the DB may contain ACTIVE
                # sessions whose seats were released back to AVAILABLE.
                validated_seats = []
                for sec, row, col in list(session.seats):
                    if self.seat_matrix.seats[sec][row][col] == SeatState.RESERVED:
                        validated_seats.append((sec, row, col))

                phantom_count = len(session.seats) - len(validated_seats)
                if phantom_count > 0:
                    session.seats = validated_seats
                    self.global_log.append(
                        "CLEANUP",
                        f"Removed {phantom_count} phantom seat(s) from "
                        f"session {session.session_id} "
                        f"(user={session.user_id})",
                    )

                if not session.seats:
                    self.store.delete_session(session.user_id)
                    expired_count += 1
                    self.global_log.append(
                        "EXPIRE",
                        f"Startup: expired phantom session "
                        f"{session.session_id} "
                        f"(user={session.user_id})",
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
                            if (
                                self.seat_matrix.seats[seat_section][row][col]
                                == SeatState.RESERVED
                            ):
                                self.seat_matrix.seats[seat_section][row][
                                    col
                                ] = SeatState.AVAILABLE
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

            ordered_sections = [
                s
                for s in (Section.VIP, Section.PREFERENTIAL, Section.GENERAL)
                if s in seats_by_section
            ]

            with self.mutex_manager.table_and_sections(ordered_sections):
                current = self.session_manager.get_by_session_id(session.session_id)
                if current is None or current.state != ReservationStatus.ACTIVE:
                    continue

                released_counts = defaultdict(int)
                for section in ordered_sections:
                    for row, col in seats_by_section[section]:
                        if (
                            self.seat_matrix.seats[section][row][col]
                            == SeatState.RESERVED
                        ):
                            self.seat_matrix.seats[section][row][
                                col
                            ] = SeatState.AVAILABLE
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

        self._release_orphaned_reserved_seats()

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

        # Persist consistent state BEFORE releasing in-memory:
        # 1. Save seat matrix (seats are still RESERVED)
        # 2. Save sessions (still ACTIVE with seat lists)
        # This ensures the DB snapshot is self-consistent on restart.
        self.store.save_all_seats(self.seat_matrix)
        self.store.save_all_sessions(self.session_manager)
        self._release_all_sessions()

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
