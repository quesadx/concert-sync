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
            expired = self.server.session_manager.get_expired()

            for session in expired:
                self.expire_session(session)

    def _group_seats_by_section(self, seats):
        seats_by_section = {}
        for section, row, col in seats:
            if section not in seats_by_section:
                seats_by_section[section] = []
            seats_by_section[section].append((row, col))
        return seats_by_section

    def _ordered_sections(self, sections):
        section_set = set(sections)
        return [section for section in Section if section in section_set]

    def expire_session(self, session):
        released_counts = {}

        seats_by_section = self._group_seats_by_section(session.seats)
        ordered_sections = self._ordered_sections(seats_by_section.keys())

        with self.server.mutex_manager.table_and_sections(ordered_sections):
            # Double-check session still ACTIVE inside lock (racing with CONFIRM)
            current = self.server.session_manager.get_by_session_id(session.session_id)
            if current is None or current.state != ReservationStatus.ACTIVE:
                return

            for section in ordered_sections:
                released_counts[section] = 0
                for row, col in seats_by_section[section]:
                    if self.server.seat_matrix.seats[section][row][col] == SeatState.RESERVED:
                        self.server.seat_matrix.seats[section][row][col] = SeatState.AVAILABLE
                        released_counts[section] += 1

            self.server.session_manager.remove(session.user_id)

        for section, count in released_counts.items():
            if count > 0:
                self.server.semaphore_mgr.release_multiple(section, count)

        total = sum(released_counts.values())
        self.server.global_log.append(
            "EXPIRE",
            f"Session:{session.session_id} User:{session.user_id} seats_released:{total}",
        )

    # DEPRECATED in Phase 1 — kept for Phase 2 analysis. No longer called from run().
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
