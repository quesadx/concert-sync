import json

class TransactionalThread(threading.Thread):
    def __init__(self, server, client_socket, addr):
        super().__init__()
        self.server = server
        self.client_socket = client_socket
        self.addr = addr

    def run(self):
        try:
            data = self.client_socket.recv(4096).decode()
            request = json.loads(data)

            action = request.get("action")

            if action == "RESERVE":
                response = self.handle_reserve(request)
            elif action == "CONFIRM":
                response = self.handle_confirm(request)
            elif action == "CANCEL":
                response = self.handle_cancel(request)
            elif action == "QUERY":
                response = self.handle_query(request)
            else:
                response = {"status": "ERROR", "message": "Unknown action"}

            self.client_socket.send(json.dumps(response).encode())
        finally:
            self.client_socket.close()

    def handle_reserve(self, request):
        section = Section[request["section"]]
        row = request["row"]
        col = request["col"]

        self.server.semaphore_mgr.acquire(section)

        try:
            success = self.server.seat_matrix.reserve_seat(section, row, col)

            if not success:
                self.server.semaphore_mgr.release(section)
                return {"status": "FAILURE", "message": "Seat not available"}

            tx_id = self.server.reservation_table.add_reservation(
                section, [(row, col)]
            )

            self.server.global_log.append(
                "RESERVE",
                f"TX:{tx_id} Section:{section.name} Seat:[{row},{col}]"
            )

            return {
                "status": "SUCCESS",
                "transaction_id": tx_id,
                "ttl": RESERVATION_TTL
            }
        except Exception as e:
            self.server.semaphore_mgr.release(section)
            raise