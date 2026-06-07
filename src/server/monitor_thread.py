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
        # EXPR-01/EXPR-02/EXPR-03 — TTL expiration race safety:
        # Per-seat TTL tracking: only seats whose individual TTL has passed are
        # released. Sessions with remaining unexpired seats stay alive.
        # Double-check inside table_and_sections lock prevents racing with
        # CONFIRM (state change) and RESERVE (TTL refresh) — if the session or
        # its seats are no longer expired inside the lock, return early.
        # Semaphore release is inside the same critical section, ensuring seats
        # and slots release atomically.
        seats_by_section = self._group_seats_by_section(session.seats)
        ordered_sections = self._ordered_sections(seats_by_section.keys())

        with self.server.mutex_manager.table_and_sections(ordered_sections):
            current = self.server.session_manager.get_by_session_id(session.session_id)
            if current is None or current.state != ReservationStatus.ACTIVE:
                return

            expired_seats = current.get_expired_seats()
            if not expired_seats:
                return

            expired_by_section = self._group_seats_by_section(expired_seats)
            released_counts = {section: 0 for section in ordered_sections}
            for section in ordered_sections:
                if section not in expired_by_section:
                    continue
                for row, col in expired_by_section[section]:
                    if (
                        self.server.seat_matrix.seats[section][row][col]
                        == SeatState.RESERVED
                    ):
                        self.server.seat_matrix.seats[section][row][
                            col
                        ] = SeatState.AVAILABLE
                        released_counts[section] += 1

                    current.seats.remove((section, row, col))
                    current.seat_timestamps.pop((section, row, col), None)

            if not current.seats:
                self.server.session_manager.remove(session.user_id)
                self.server.store.delete_session(session.user_id)

            for section, count in released_counts.items():
                if count > 0:
                    self.server.semaphore_mgr.release_multiple(section, count)

        self.server.store.save_all_seats(self.server.seat_matrix)

        total = sum(released_counts.values())
        self.server.global_log.append(
            "EXPIRE",
            f"Session:{session.session_id} User:{session.user_id} seats_released:{total}",
        )

    def expire_reservation(self, tx_id):
        """Legacy safety wrapper — no longer called from run().

        Attempts to find session by transaction_id and expire it.
        If no matching session found, logs and returns.
        """
        for session in list(self.server.session_manager._sessions.values()):
            if session.session_id == tx_id:
                self.expire_session(session)
                return
        self.server.global_log.append(
            "EXPIRE",
            f"TX:{tx_id} not found in active sessions (already expired/confirmed)",
        )
