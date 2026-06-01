import socket

from src.server.listener_thread import ListenerThread
from src.server.monitor_thread import MonitorThread
from src.server.session_manager import SessionManager
from src.shared_resources.global_log import GlobalLog
from src.shared_resources.reservation_table import ReservationTable
from src.shared_resources.seat_matrix import SeatMatrix
from src.shared_resources.semaphore_manager import SemaphoreManager
from src.synchronization.mutex_manager import MutexManager
from src.utils.config import SERVER_PORT
from src.utils.enums import ReservationStatus, SeatState


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

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(1.0)
        self.running = False
        self.monitor_thread = None
        self.listener_thread = None

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

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True

        self.monitor_thread = MonitorThread(self)
        self.monitor_thread.start()

        self._cleanup_stale_reservations()

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

        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2)

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)

        self.global_log.append("SERVER", "Server stopped")