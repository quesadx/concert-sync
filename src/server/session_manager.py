import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.utils.config import RESERVATION_TTL
from src.utils.enums import ReservationStatus, Section


@dataclass
class UserSession:
    user_id: str
    session_id: str
    seats: List[Tuple[Section, int, int]] = field(default_factory=list)
    seat_timestamps: Dict[Tuple[Section, int, int], float] = field(default_factory=dict)
    last_activity: float = field(default_factory=time.time)
    ttl_secs: int = RESERVATION_TTL
    state: ReservationStatus = ReservationStatus.ACTIVE

    @property
    def is_expired(self) -> bool:
        if self.state != ReservationStatus.ACTIVE:
            return True
        if not self.seats:
            return True
        now = time.time()
        for seat_key in self.seats:
            ts = self.seat_timestamps.get(seat_key, self.last_activity)
            if now - ts <= self.ttl_secs:
                return False
        return True

    @property
    def has_expired_seats(self) -> bool:
        """Returns True if at least one seat in the session has expired."""
        if self.state != ReservationStatus.ACTIVE:
            return False
        now = time.time()
        for seat_key in self.seats:
            ts = self.seat_timestamps.get(seat_key, self.last_activity)
            if now - ts > self.ttl_secs:
                return True
        return False

    def get_expired_seats(self):
        """Return list of (section, row, col) tuples for seats whose TTL has passed."""
        if self.state != ReservationStatus.ACTIVE:
            return []
        expired = []
        now = time.time()
        for seat_key in self.seats:
            ts = self.seat_timestamps.get(seat_key, self.last_activity)
            if now - ts > self.ttl_secs:
                expired.append(seat_key)
        return expired

    def reset_ttl(self) -> None:
        self.last_activity = time.time()

    def record_seat_timestamp(self, section: Section, row: int, col: int) -> None:
        """Record the reservation timestamp for a single seat."""
        self.seat_timestamps[(section, row, col)] = time.time()
        self.last_activity = time.time()


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, UserSession] = {}
        self._lock = threading.Lock()

    def get_or_create(self, user_id: str) -> UserSession:
        with self._lock:
            if user_id in self._sessions:
                return self._sessions[user_id]
            session = UserSession(
                user_id=user_id,
                session_id=str(uuid.uuid4()),
            )
            self._sessions[user_id] = session
            return session

    def get_by_session_id(self, session_id: str) -> Optional[UserSession]:
        with self._lock:
            for session in self._sessions.values():
                if session.session_id == session_id:
                    return session
            return None

    def get_expired(self) -> List[UserSession]:
        with self._lock:
            return [
                s
                for s in self._sessions.values()
                if s.state == ReservationStatus.ACTIVE and s.has_expired_seats
            ]

    def get_all_active(self) -> List[UserSession]:
        with self._lock:
            return [
                s
                for s in self._sessions.values()
                if s.state == ReservationStatus.ACTIVE
            ]

    def get_by_user_id(self, user_id: str) -> Optional[UserSession]:
        with self._lock:
            return self._sessions.get(user_id, None)

    def reclaim_session(
        self, session_id: str, new_user_id: str
    ) -> Optional[UserSession]:
        """
        Look up session by its UUID and remap to new_user_id.

        This enables session persistence across client disconnects —
        the user provides their previous session_id and reclaims active reservations.

        Args:
            session_id: UUID session_id to reclaim
            new_user_id: New user_id to map the session to

        Returns:
            UserSession if found and reclaimed, None otherwise.
        """
        with self._lock:
            for session in self._sessions.values():
                if session.session_id == session_id:
                    if session.state == ReservationStatus.ACTIVE:
                        # Remove old mapping, create new mapping
                        old_user_id = session.user_id
                        self._sessions.pop(old_user_id, None)
                        session.user_id = new_user_id
                        self._sessions[new_user_id] = session
                        return session
                    else:
                        # Session already expired/confirmed/cancelled
                        return None
            return None

    def remove(self, user_id: str) -> Optional[UserSession]:
        with self._lock:
            return self._sessions.pop(user_id, None)
