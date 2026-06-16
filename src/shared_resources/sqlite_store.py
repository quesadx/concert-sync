"""Thread-safe SQLite persistence for ConcertSync seat states and sessions.

Provides a SqliteStore class that mirrors server in-memory state to a SQLite database
at data/concert_sync.db. All database access is serialized via threading.Lock() and
each operation creates a fresh connection with WAL mode enabled. Connections are
closed in finally blocks to prevent leaks.

Supports an optional GlobalLog reference for proper error logging instead of stderr.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.utils.enums import SeatState, Section


class SqliteStore:
    """Thread-safe SQLite persistence layer for ConcertSync server state.

    Serializes all DB access through a single threading.Lock(). Each public
    method opens a fresh sqlite3 connection, executes in WAL mode, and closes
    in a finally block.

    If a global_log is provided, errors are logged there instead of stderr.

    Attributes:
        db_path: Path to the SQLite database file.
        _lock: threading.Lock for serializing all database access.
    """

    def __init__(
        self, db_path: str = "data/concert_sync.db", global_log: Any = None
    ) -> None:
        """Initialize the store, create data directory, and ensure tables exist.

        Args:
            db_path: Relative or absolute path to the SQLite database file.
            global_log: Optional GlobalLog instance for error logging.
        """
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._global_log = global_log
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _log_error(self, msg: str) -> None:
        if self._global_log:
            self._global_log.append("ERROR", f"SqliteStore: {msg}")
        else:
            import sys

            print(f"[SqliteStore] {msg}", file=sys.stderr)

    # ════════════════════════════════════════════════════════════════════════
    # Schema initialization
    # ════════════════════════════════════════════════════════════════════════

    def _ensure_tables(self) -> None:
        """Create all required tables if they don't already exist.

        Creates three tables:
        - seat_states: Per-seat state with CHECK constraint on valid states.
        - sessions: User session metadata with TTL tracking.
        - session_seats: Junction table linking sessions to reserved seats.

        Foreign key enforcement is enabled via PRAGMA foreign_keys=ON.
        """
        tables_sql = """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS seat_states (
            section TEXT NOT NULL,
            row INTEGER NOT NULL,
            col INTEGER NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('AVAILABLE','RESERVED','SOLD')),
            PRIMARY KEY (section, row, col)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            user_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('ACTIVE','CONFIRMED','CANCELLED','EXPIRED')),
            last_activity REAL NOT NULL,
            ttl_secs INTEGER NOT NULL,
            created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS session_seats (
            user_id TEXT NOT NULL,
            section TEXT NOT NULL,
            row INTEGER NOT NULL,
            col INTEGER NOT NULL,
            reserved_at REAL NOT NULL DEFAULT 0.0,
            PRIMARY KEY (user_id, section, row, col),
            FOREIGN KEY (user_id) REFERENCES sessions(user_id) ON DELETE CASCADE
        );
        """
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(tables_sql)
                try:
                    conn.execute(
                        "ALTER TABLE session_seats ADD COLUMN reserved_at REAL "
                        "NOT NULL DEFAULT 0.0"
                    )
                except sqlite3.OperationalError:
                    pass
            except sqlite3.Error as exc:
                self._log_error(f"Failed to create tables: {exc}")
            finally:
                if conn:
                    conn.close()

    # ════════════════════════════════════════════════════════════════════════
    # Seat state persistence
    # ════════════════════════════════════════════════════════════════════════

    def save_all_seats(self, seat_matrix: Any) -> None:
        """Persist the entire seat matrix to SQLite in a single transaction.

        Iterates all sections, rows, and columns, upserting each seat's state
        via INSERT OR REPLACE. The operation is wrapped in a single transaction
        for atomicity and performance.

        Args:
            seat_matrix: A SeatMatrix instance with .seats dict keyed by Section
                         enum, containing 2D lists of SeatState values.
        """
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("BEGIN")
                for section in Section:
                    seats = seat_matrix.seats[section]
                    for row_idx, row in enumerate(seats):
                        for col_idx, seat in enumerate(row):
                            conn.execute(
                                "INSERT OR REPLACE INTO seat_states (section, row, col, state) "
                                "VALUES (?, ?, ?, ?)",
                                (section.name, row_idx, col_idx, seat.value),
                            )
                conn.execute("COMMIT")
            except sqlite3.Error as exc:
                self._log_error(f"Failed to save seats: {exc}")
            finally:
                if conn:
                    conn.close()

    def load_all_seats(self) -> Optional[Dict[Section, List[List[SeatState]]]]:
        """Load the full seat matrix from SQLite.

        Returns a dict keyed by Section enum with 2D lists of SeatState values.
        If the seat_states table is empty (no rows), returns None so the
        caller can fall back to default initialization.

        Returns:
            Dict mapping Section to 2D list of SeatState, or None if DB is empty.
        """
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.execute("PRAGMA journal_mode=WAL")
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT section, row, col, state FROM seat_states "
                    "ORDER BY section, row, col"
                )
                rows = cursor.fetchall()
                if not rows:
                    return None

                # Pre-initialize grid with AVAILABLE, then fill from DB
                seats: Dict[Section, List[List[SeatState]]] = {}
                for section in Section:
                    from src.utils.config import SECTION_CONFIG

                    cfg = SECTION_CONFIG[section]
                    seats[section] = [
                        [SeatState.AVAILABLE for _ in range(cfg["cols"])]
                        for _ in range(cfg["rows"])
                    ]

                for row in rows:
                    section = Section[row["section"]]
                    seats[section][row["row"]][row["col"]] = SeatState(row["state"])

                return seats
            except sqlite3.Error as exc:
                self._log_error(f"Failed to load seats: {exc}")
                return None
            finally:
                if conn:
                    conn.close()

    # ════════════════════════════════════════════════════════════════════════
    # Session persistence
    # ════════════════════════════════════════════════════════════════════════

    def save_all_sessions(self, session_manager: Any) -> None:
        """Persist all active sessions to SQLite in a single transaction.

        Deletes all existing session_seats rows, then re-inserts for each
        session. Uses a single transaction for atomicity.

        Args:
            session_manager: A SessionManager instance with UserSession
                             objects accessible via get_all_sessions().
        """
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("BEGIN")

                for session in session_manager.get_all_sessions():
                    user_id = session.user_id
                    conn.execute(
                        "INSERT OR REPLACE INTO sessions "
                        "(user_id, session_id, state, last_activity, ttl_secs) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            user_id,
                            session.session_id,
                            session.state.value,
                            session.last_activity,
                            session.ttl_secs,
                        ),
                    )
                    # Clear and re-insert seat references
                    conn.execute(
                        "DELETE FROM session_seats WHERE user_id = ?",
                        (user_id,),
                    )
                    for section, row, col in session.seats:
                        conn.execute(
                            "INSERT OR REPLACE INTO session_seats "
                            "(user_id, section, row, col, reserved_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (user_id, section.name, row, col, session.last_activity),
                        )

                conn.execute("COMMIT")
            except sqlite3.Error as exc:
                self._log_error(f"Failed to save sessions: {exc}")
            finally:
                if conn:
                    conn.close()

    def load_all_sessions(self) -> List[dict]:
        """Load all sessions and their seat assignments from SQLite.

        Returns a list of dicts, each representing a session with its seats.
        Sessions without any seat assignments are still included (empty seats list).

        Returns:
            List of dicts with keys: user_id, session_id, state, last_activity,
            ttl_secs, seats (list of (Section, row, col) tuples).
            Returns empty list if DB is empty or on error.
        """
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.execute("PRAGMA journal_mode=WAL")
                conn.row_factory = sqlite3.Row

                session_rows = conn.execute(
                    "SELECT user_id, session_id, state, last_activity, ttl_secs "
                    "FROM sessions"
                ).fetchall()

                result: List[dict] = []
                for srow in session_rows:
                    seat_rows = conn.execute(
                        "SELECT section, row, col, reserved_at FROM session_seats "
                        "WHERE user_id = ?",
                        (srow["user_id"],),
                    ).fetchall()
                    seats: List[Tuple[Section, int, int]] = [
                        (Section[sr["section"]], sr["row"], sr["col"])
                        for sr in seat_rows
                    ]
                    result.append(
                        {
                            "user_id": srow["user_id"],
                            "session_id": srow["session_id"],
                            "state": srow["state"],
                            "last_activity": srow["last_activity"],
                            "ttl_secs": srow["ttl_secs"],
                            "seats": seats,
                        }
                    )
                return result
            except sqlite3.Error as exc:
                self._log_error(f"Failed to load sessions: {exc}")
                return []
            finally:
                if conn:
                    conn.close()

    def delete_session(self, user_id: str) -> None:
        """Delete a session and its associated seat references from SQLite.

        The ON DELETE CASCADE foreign key on session_seats automatically
        removes seat rows when the parent session row is deleted.

        Args:
            user_id: The user_id whose session should be removed.
        """
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            except sqlite3.Error as exc:
                self._log_error(f"Failed to delete session {user_id}: {exc}")
            finally:
                if conn:
                    conn.close()

    # ════════════════════════════════════════════════════════════════════════
    # Lifecycle
    # ════════════════════════════════════════════════════════════════════════

    def close(self) -> None:
        """No-op kept for API symmetry with other resource managers.

        Connections are created and closed per-operation, so there is no
        persistent connection to shut down.
        """
        pass
