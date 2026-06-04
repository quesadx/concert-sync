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
    last_activity: float = field(default_factory=time.time)
    ttl_secs: int = RESERVATION_TTL
    state: ReservationStatus = ReservationStatus.ACTIVE

    @property
    def is_expired(self) -> bool:
        if self.state != ReservationStatus.ACTIVE:
            return True
        return time.time() - self.last_activity > self.ttl_secs

    def reset_ttl(self) -> None:
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
                s for s in self._sessions.values()
                if s.state == ReservationStatus.ACTIVE and s.is_expired
            ]

    def get_by_user_id(self, user_id: str) -> Optional[UserSession]:
        with self._lock:
            return self._sessions.get(user_id, None)

    def remove(self, user_id: str) -> Optional[UserSession]:
        with self._lock:
            return self._sessions.pop(user_id, None)
