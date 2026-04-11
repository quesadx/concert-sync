import time

class MonitorThread(threading.Thread):
    def __init__(self, server):
        super().__init__()
        self.server = server
        self.daemon = True

    def run(self):
        while True:
            time.sleep(10)

            expired = self.server.reservation_table.get_expired_reservations()

            for tx_id in expired:
                self.expire_reservation(tx_id)

    def expire_reservation(self, tx_id):
        with self.server.reservation_table.mutex_table:
            res = self.server.reservation_table.reservations.get(tx_id)
            if not res or res.state != ReservationState.ACTIVE:
                return

            res.state = ReservationState.EXPIRED

            for row, col in res.seats:
                with self.server.seat_matrix.mutex_sections[res.section]:
                    self.server.seat_matrix.seats[res.section][row][col] = SeatState.AVAILABLE

                self.server.semaphore_mgr.release(res.section)

            self.server.global_log.append("EXPIRE", f"TX:{tx_id} expired")