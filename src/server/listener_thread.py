import threading
import socket

from src.server.transactional_thread import TransactionalThread


class ListenerThread(threading.Thread):
    def __init__(self, server):
        super().__init__()
        self.server = server

    def run(self):
        while self.server.running:
            try:
                client_socket, addr = self.server.server_socket.accept()
                tx_thread = TransactionalThread(self.server, client_socket, addr)
                tx_thread.start()
            except socket.timeout:
                continue
            except OSError:
                if not self.server.running:
                    break
            except Exception as e:
                if self.server.running:
                    self.server.global_log.append("ERROR", str(e))