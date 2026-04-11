import threading
from src.utils.config import SECTION_CONFIG
from src.utils.enums import Section, SeatState

class SeatMatrix:
    def __init__(self):
        self.seats = {}
        self.rwlocks = {}
        self.mutex_sections = {}
        self._initialize_seats()

    def _initialize_seats(self):
        for section in Section:
            rows = SECTION_CONFIG[section]["rows"]
            cols = SECTION_CONFIG[section]["cols"]

            self.seats[section] = [
                [SeatState.AVAILABLE for _ in range(cols)]
                for _ in range(rows)
            ]

            self.rwlocks[section] = threading.RLock()
            self.mutex_sections[section] = threading.Lock()

    def check_availability(self, section, row, col):
        with self.rwlocks[section]:
            return self.seats[section][row][col] == SeatState.AVAILABLE

    def reserve_seat(self, section, row, col):
        with self.mutex_sections[section]:
            if self.seats[section][row][col] == SeatState.AVAILABLE:
                self.seats[section][row][col] = SeatState.RESERVED
                return True
            return False

    def set_seat_state(self, section, row, col, state):
        with self.mutex_sections[section]:
            self.seats[section][row][col] = state

    def get_section_counts(self, section):
        with self.mutex_sections[section]:
            total = 0
            available = 0
            reserved = 0
            sold = 0

            for row in self.seats[section]:
                for seat in row:
                    total += 1
                    if seat == SeatState.AVAILABLE:
                        available += 1
                    elif seat == SeatState.RESERVED:
                        reserved += 1
                    elif seat == SeatState.SOLD:
                        sold += 1

            return {
                "total": total,
                "available": available,
                "reserved": reserved,
                "sold": sold,
            }