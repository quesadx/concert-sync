import socket
import threading
from shared_resources import *

class ConcertServer:
    def __init__(self, port=9999):
        self.port = port
        self.seat_matrix = SeatMatrix()
        self.semaphore_mgr = SemaphoreManager()
        self.reservation_table = ReservationTable()
        self.global_log = GlobalLog()

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.running = False

    def start(self):
        self.server_socket.bind(('localhost', self.port))
        self.server_socket.listen(5)
        self.running = True

        monitor = MonitorThread(self)
        monitor.daemon = True
        monitor.start()

        listener = ListenerThread(self)
        listener.start()

        self.global_log.append("SERVER", "Server started")