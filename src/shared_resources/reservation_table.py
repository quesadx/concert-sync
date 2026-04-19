import threading
import time
import uuid
from dataclasses import dataclass
from src.utils.config import RESERVATION_TTL
from src.utils.enums import ReservationStatus, Section

@dataclass
class Reservation:
    transaction_id: str
    section: Section
    seats: list
    timestamp_creation: float
    ttl_secs: int
    state: ReservationStatus

class ReservationTable:
    def __init__(self):
        self.reservations = {}
        self.mutex_table = threading.Lock()
        self.cond_var = threading.Condition(self.mutex_table)

    def add_reservation(self, section, seats):
        with self.mutex_table:
            tx_id = str(uuid.uuid4())
            reservation = Reservation(
                transaction_id=tx_id,
                section=section,
                seats=seats,
                timestamp_creation=time.time(),
                ttl_secs=RESERVATION_TTL,
                state=ReservationStatus.ACTIVE
            )
            self.reservations[tx_id] = reservation
            self.cond_var.notify()
            return tx_id

    def get_expired_reservations(self):
        with self.mutex_table:
            now = time.time()
            expired = []
            for tx_id, res in self.reservations.items():
                if (res.state == ReservationStatus.ACTIVE and
                    now - res.timestamp_creation > res.ttl_secs):
                    expired.append(tx_id)
            return expired

    def get_reservation(self, tx_id):
        with self.mutex_table:
            return self.reservations.get(tx_id)