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


class NotificationType(Enum):
    """Types of push notifications sent to subscribed clients.

    These correspond to the notification_type field in NOTIFICATION
    async push messages sent over subscription sockets.
    """

    TTL_WARNING = "TTL_WARNING"
    CONFIRMED = "CONFIRMED"
    EXPIRED = "EXPIRED"
    AVAILABILITY = "AVAILABILITY"
    SUBSCRIBED = "SUBSCRIBED"
    UNSUBSCRIBED = "UNSUBSCRIBED"