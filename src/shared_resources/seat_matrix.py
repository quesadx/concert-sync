import threading
from utils.enums import Section, SeatState

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