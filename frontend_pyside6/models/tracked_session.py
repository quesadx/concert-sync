"""Tracked session tracking for TTL-based reservation management.

Mirrors TrackedSession from frontend_tui/app.py exactly — same fields, properties, behavior.
"""

from dataclasses import dataclass, field
import time


@dataclass
class TrackedSession:
    """Tracks a server-side reservation session with TTL countdown.

    Attributes:
        transaction_id: Unique transaction identifier from the server.
        operation_type: Protocol action (RESERVE, RESERVE_BATCH, etc.).
        seat_summary: Human-readable seat description (e.g., "VIP(0,0)").
        ttl_seconds: Reservation time-to-live in seconds (typically 300).
        created_at: Unix timestamp when the session was created.
        state: Session state string ("ACTIVE", "CONFIRMED", "CANCELLED", "EXPIRED").
        seats: List of seat dicts with section/row/col for per-coordinate TTL lookup.
    """

    transaction_id: str
    operation_type: str
    seat_summary: str
    ttl_seconds: int
    created_at: float
    state: str = "ACTIVE"
    seats: list = field(default_factory=list)

    @property
    def expires_at(self) -> float:
        """Unix timestamp when this session's TTL expires."""
        return self.created_at + self.ttl_seconds

    def ttl_remaining(self) -> int:
        """Seconds remaining before TTL expiration.

        Returns 0 for non-ACTIVE sessions.
        """
        if self.state != "ACTIVE":
            return 0
        return max(0, int(self.expires_at - time.time()))
