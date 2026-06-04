from enum import Enum

class SeatState(Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    OWN_RESERVED = "OWN_RESERVED"  # view-only — never stored in SeatMatrix
    SOLD = "SOLD"

class Section(Enum):
    VIP = 0
    PREFERENTIAL = 1
    GENERAL = 2

class ReservationStatus(Enum):
    ACTIVE = "ACTIVE"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


# Backward-compatible alias used in earlier code.
ReservationState = ReservationStatus