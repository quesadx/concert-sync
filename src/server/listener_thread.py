import threading
import socket
import time

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
                tx_thread.name = f"TxThread-{addr[0]}:{addr[1]}-{time.time_ns()}"
                self.server.register_thread(tx_thread)
                tx_thread.start()
                self.server.global_log.append(
                    "THREAD",
                    f"Started {tx_thread.name} for client {addr[0]}:{addr[1]}",
                )
            except socket.timeout:
                continue
            except OSError:
                if not self.server.running:
                    break
            except Exception as e:
                if self.server.running:
                    self.server.global_log.append("ERROR", str(e))