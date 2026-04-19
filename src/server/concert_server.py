import socket

from src.server.listener_thread import ListenerThread
from src.server.monitor_thread import MonitorThread
from src.shared_resources.global_log import GlobalLog
from src.shared_resources.reservation_table import ReservationTable
from src.shared_resources.seat_matrix import SeatMatrix
from src.shared_resources.semaphore_manager import SemaphoreManager
from src.utils.config import SERVER_PORT


class ConcertServer:
    def __init__(self, host="localhost", port=SERVER_PORT):
        self.host = host
        self.port = port
        self.seat_matrix = SeatMatrix()
        self.semaphore_mgr = SemaphoreManager()
        self.reservation_table = ReservationTable()
        self.global_log = GlobalLog()

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(1.0)
        self.running = False
        self.monitor_thread = None
        self.listener_thread = None

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True

        self.monitor_thread = MonitorThread(self)
        self.monitor_thread.start()

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