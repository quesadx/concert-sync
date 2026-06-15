"""Shared pytest fixtures for ConcertSync PySide6 test suite.

Provides reusable fixtures for server lifecycle, ConcertClient instances,
seat matrix access, and QApplication creation.
"""

import os
import sys
import threading
import time

import pytest

# Ensure project root is on sys.path so that 'src.*' and 'frontend_pyside6.*'
# imports resolve during test collection.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


@pytest.fixture(scope="function")
def server():
    """Start a ConcertServer on port 9999 in a background daemon thread.

    Yields the server instance so tests can inspect shared state.  Stops the
    server and joins threads during teardown.
    """
    from src.server.concert_server import ConcertServer

    # Remove stale SQLite DB to prevent cross-test state pollution.
    _db = os.path.join(_project_root, "data", "concert_sync.db")
    try:
        os.remove(_db)
    except FileNotFoundError:
        pass

    srv = ConcertServer(host="localhost", port=9999)
    srv_thread = threading.Thread(target=srv.start, daemon=True)
    srv_thread.start()
    # Wait for server to be ready or fail
    for _ in range(10):
        if srv.running:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Server failed to start")

    yield srv

    try:
        srv.stop()
    except Exception:
        pass
    srv_thread.join(timeout=3)
    time.sleep(0.1)  # Let SO_REUSEADDR settle


@pytest.fixture(scope="function")
def client(server):
    """Create a ConcertClient for user ``test_user`` connected to the server fixture.

    Yields the client instance.  After the test the fixture attempts to cancel
    any active transactions to leave the server in a clean state.
    """
    from src.client.concert_client import ConcertClient
    from src.utils.enums import ReservationStatus

    cl = ConcertClient(user_id="test_user", host="localhost", port=9999)

    yield cl

    # Best-effort cleanup: cancel any sessions still held by this user
    srv = server
    try:
        if srv.session_manager and srv.session_manager.get_by_user_id("test_user"):
            session = srv.session_manager.get_by_user_id("test_user")
            if session and session.state == ReservationStatus.ACTIVE:
                cl.send_request(
                    {"action": "CANCEL", "transaction_id": session.session_id}
                )
    except Exception:
        pass


@pytest.fixture(scope="function")
def client2(server):
    """Create a second ConcertClient for multi-user concurrency tests.

    Connected as ``test_user2`` so tests can simulate two concurrent users.
    """
    from src.client.concert_client import ConcertClient

    cl = ConcertClient(user_id="test_user2", host="localhost", port=9999)
    yield cl


@pytest.fixture(scope="function")
def seat_matrix(server):
    """Return ``server.seat_matrix`` for direct state inspection in tests."""
    return server.seat_matrix


@pytest.fixture(scope="function")
def qapp():
    """Create or return the singleton ``QApplication`` for widget tests.

    If a ``QApplication`` already exists (e.g. from a previous test) it is
    reused to avoid Qt warnings about multiple instances.
    """
    from PySide6.QtWidgets import QApplication

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
    except RuntimeError:
        app = QApplication(sys.argv)

    yield app
