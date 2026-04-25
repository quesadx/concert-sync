import threading
import time

from src.utils.enums import ReservationStatus, SeatState, Section


class MonitorThread(threading.Thread):
    def __init__(self, server):
        super().__init__()
        self.server = server
        self.daemon = True

    def run(self):
        while self.server.running:
            time.sleep(1)
            expired = self.server.reservation_table.get_expired_reservations()

            for tx_id in expired:
                self.expire_reservation(tx_id)

    def _group_reservation_seats_by_section(self, reservation):
        seats_by_section = {}

        for seat_info in reservation.seats:
            if len(seat_info) == 3:
                section, row, col = seat_info
            else:
                section = reservation.section
                row, col = seat_info

            if section not in seats_by_section:
                seats_by_section[section] = []
            seats_by_section[section].append((row, col))

        return seats_by_section

    def _ordered_sections(self, sections):
        section_set = set(sections)
        return [section for section in Section if section in section_set]

    def expire_reservation(self, tx_id):
        released_counts = {}

        with self.server.mutex_manager.table():
            reservation = self.server.reservation_table.reservations.get(tx_id)
            if not reservation or reservation.state != ReservationStatus.ACTIVE:
                return

                reservation.state = ReservationStatus.EXPIRED
                for section in ordered_sections:
                    for row, col in seats_by_section[section]:
                        if self.server.seat_matrix.seats[section][row][col] == SeatState.RESERVED:
                            self.server.seat_matrix.seats[section][row][col] = SeatState.AVAILABLE
                            released_counts[section] += 1

            cleared_reservation = self.server.reservation_table.delete_reservation(tx_id, locked=True)
            if cleared_reservation is None:
                return

        for section, count in released_counts.items():
            if count > 0:
                self.server.semaphore_mgr.release_multiple(section, count)

        released_total = sum(released_counts.values())

        self.server.global_log.append(
            "EXPIRE",
            f"TX:{tx_id} expired seats_released:{released_total} sections_released:{len(released_counts)}",
        )