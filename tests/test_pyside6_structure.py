"""Verify the PySide6 frontend package structure (FRNT-02, FRNT-03).

Confirms:
- ``frontend_pyside6`` and its sub-packages import successfully.
- All required widget and worker modules exist.
- The original Textual ``frontend_tui`` is preserved.
- The backend (``src/``) does not accidentally import ``frontend_pyside6``.
"""

import importlib
import os
import subprocess

import pytest


# ============================================================================
# Package import tests (FRNT-02)
# ============================================================================


def test_frontend_pyside6_package_imports():
    """``import frontend_pyside6`` must succeed."""
    import frontend_pyside6


def test_models_module_imports():
    """``TrackedSession`` dataclass must be importable."""
    from frontend_pyside6.models.tracked_session import TrackedSession


def test_widgets_module_structure():
    """All required widget modules exist in ``frontend_pyside6/widgets/``."""
    pkg = importlib.import_module("frontend_pyside6.widgets")
    widget_dir = os.path.dirname(pkg.__file__)
    expected = [
        "__init__.py",
        "seat_map_widget.py",
        "section_stats.py",
        "transaction_panel.py",
        "connection_panel.py",
        "event_log.py",
    ]
    for name in expected:
        path = os.path.join(widget_dir, name)
        assert os.path.exists(path), f"Missing widget module: {name}"


def test_workers_module_structure():
    """Required worker modules exist in ``frontend_pyside6/workers/``."""
    pkg = importlib.import_module("frontend_pyside6.workers")
    worker_dir = os.path.dirname(pkg.__file__)
    for name in ["__init__.py", "network_worker.py"]:
        path = os.path.join(worker_dir, name)
        assert os.path.exists(path), f"Missing worker module: {name}"


# ============================================================================
# Backend stability / TUI preservation tests (FRNT-03)
# ============================================================================


def test_frontend_tui_still_exists():
    """The original Textual frontend must NOT be removed.

    Verifies that ``frontend_tui/__init__.py`` still exists on disk.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tui_init = os.path.join(project_root, "frontend_tui", "__init__.py")
    assert os.path.exists(tui_init), (
        "frontend_tui/__init__.py is missing — the Textual frontend MUST be preserved"
    )


def test_no_backend_imports_from_pyside6():
    """The ``src/`` backend MUST NOT import ``frontend_pyside6``.

    Uses ``grep`` to scan all ``.py`` files under ``src/`` for any reference
    to ``frontend_pyside6``.  Any hit is a backend-stability violation.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(project_root, "src")
    result = subprocess.run(
        ["grep", "-rl", "frontend_pyside6", src_dir],
        capture_output=True,
        text=True,
    )
    matches = [line for line in result.stdout.strip().split("\n") if line]
    assert len(matches) == 0, (
        f"Backend files import frontend_pyside6: {', '.join(matches)}"
    )
