import threading
import time

from src.utils.enums import ReservationStatus, SeatState


class MonitorThread(threading.Thread):
    def __init__(self, server):
        super().__init__()
        self.server = server
        self.daemon = True

    def run(self):
        while self.server.running:
            time.sleep(10)
            expired = self.server.reservation_table.get_expired_reservations()

            for tx_id in expired:
                self.expire_reservation(tx_id)

    def expire_reservation(self, tx_id):
        with self.server.reservation_table.mutex_table:
            reservation = self.server.reservation_table.reservations.get(tx_id)
            if not reservation or reservation.state != ReservationStatus.ACTIVE:
                return

            reservation.state = ReservationStatus.EXPIRED
            section = reservation.section
            released_count = 0

            with self.server.seat_matrix.mutex_sections[section]:
                for row, col in reservation.seats:
                    if self.server.seat_matrix.seats[section][row][col] == SeatState.RESERVED:
                        self.server.seat_matrix.seats[section][row][col] = SeatState.AVAILABLE
                        released_count += 1

            self.server.semaphore_mgr.release_multiple(section, released_count)

        self.server.global_log.append(
            "EXPIRE",
            f"TX:{tx_id} expired seats_released:{released_count}",
        )