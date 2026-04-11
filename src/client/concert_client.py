import socket
import json


class ConcertClient:
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port

    def send_request(self, request):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.host, self.port))
            s.send(json.dumps(request).encode())
            response = s.recv(4096).decode()
            return json.loads(response)

    def reserve_seat(self, section, row, col):
        request = {
            "action": "RESERVE",
            "section": section,
            "row": row,
            "col": col
        }
        return self.send_request(request)

    def confirm(self, transaction_id):
        request = {
            "action": "CONFIRM",
            "transaction_id": transaction_id,
        }
        return self.send_request(request)

    def cancel(self, transaction_id):
        request = {
            "action": "CANCEL",
            "transaction_id": transaction_id,
        }
        return self.send_request(request)

    def query(self):
        request = {
            "action": "QUERY",
        }
        return self.send_request(request)