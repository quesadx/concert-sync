import json
import threading

from src.utils.config import RESERVATION_TTL
from src.utils.enums import ReservationStatus, Section, SeatState


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
        except Exception as e:
            self.server.global_log.append("ERROR", f"Request handling failed: {str(e)}")
            error_response = {"status": "ERROR", "message": str(e)}
            self.client_socket.send(json.dumps(error_response).encode())
        finally:
            self.client_socket.close()

    def handle_reserve(self, request):
        section = Section[request["section"]]
        row = int(request["row"])
        col = int(request["col"])

        try:
            with self.server.seat_matrix.mutex_sections[section]:
                seats = self.server.seat_matrix.seats[section]

                if row < 0 or row >= len(seats) or col < 0 or col >= len(seats[row]):
                    return {"status": "FAILURE", "message": "Invalid seat coordinates"}

                if seats[row][col] != SeatState.AVAILABLE:
                    return {"status": "FAILURE", "message": "Seat not available"}

                seats[row][col] = SeatState.RESERVED

                acquired = self.server.semaphore_mgr.acquire(section, blocking=False)
                if not acquired:
                    seats[row][col] = SeatState.AVAILABLE
                    return {
                        "status": "FAILURE",
                        "message": "No section capacity available",
                    }

            tx_id = self.server.reservation_table.add_reservation(section, [(row, col)])

            self.server.global_log.append(
                "RESERVE",
                f"TX:{tx_id} Section:{section.name} Seat:[{row},{col}]",
            )

            return {
                "status": "SUCCESS",
                "transaction_id": tx_id,
                "ttl": RESERVATION_TTL,
            }
        except Exception as e:
            with self.server.seat_matrix.mutex_sections[section]:
                seats = self.server.seat_matrix.seats[section]
                valid_indices = (
                    0 <= row < len(seats) and 0 <= col < len(seats[row])
                )
                if valid_indices and seats[row][col] == SeatState.RESERVED:
                    seats[row][col] = SeatState.AVAILABLE
                    self.server.semaphore_mgr.release(section)

            self.server.global_log.append("ERROR", f"TX failed: {str(e)}")
            return {"status": "ERROR", "message": str(e)}

    def handle_confirm(self, request):
        tx_id = request.get("transaction_id")
        if not tx_id:
            return {"status": "FAILURE", "message": "transaction_id is required"}

        with self.server.reservation_table.mutex_table:
            reservation = self.server.reservation_table.reservations.get(tx_id)
            if not reservation or reservation.state != ReservationStatus.ACTIVE:
                return {
                    "status": "FAILURE",
                    "message": "Transaction not found or not ACTIVE",
                }

            section = reservation.section
            with self.server.seat_matrix.mutex_sections[section]:
                for row, col in reservation.seats:
                    if self.server.seat_matrix.seats[section][row][col] != SeatState.RESERVED:
                        return {
                            "status": "FAILURE",
                            "message": "Seat state mismatch for confirmation",
                        }

                    self.server.seat_matrix.seats[section][row][col] = SeatState.SOLD

            reservation.state = ReservationStatus.CONFIRMED

        self.server.global_log.append("CONFIRM", f"TX:{tx_id} confirmed")
        return {"status": "SUCCESS", "transaction_id": tx_id}

    def handle_cancel(self, request):
        tx_id = request.get("transaction_id")
        if not tx_id:
            return {"status": "FAILURE", "message": "transaction_id is required"}

        with self.server.reservation_table.mutex_table:
            reservation = self.server.reservation_table.reservations.get(tx_id)
            if not reservation or reservation.state != ReservationStatus.ACTIVE:
                return {
                    "status": "FAILURE",
                    "message": "Transaction not found or not ACTIVE",
                }

            section = reservation.section
            released_count = 0

            with self.server.seat_matrix.mutex_sections[section]:
                for row, col in reservation.seats:
                    if self.server.seat_matrix.seats[section][row][col] == SeatState.RESERVED:
                        self.server.seat_matrix.seats[section][row][col] = SeatState.AVAILABLE
                        released_count += 1

            reservation.state = ReservationStatus.CANCELLED
            self.server.semaphore_mgr.release_multiple(section, released_count)

        self.server.global_log.append(
            "CANCEL",
            f"TX:{tx_id} cancelled seats_released:{released_count}",
        )
        return {"status": "SUCCESS", "transaction_id": tx_id}

    def handle_query(self, request):
        sections_data = {}
        for section in Section:
            sections_data[section.name] = self.server.seat_matrix.get_section_counts(section)

        return {
            "status": "SUCCESS",
            "sections": sections_data,
        }