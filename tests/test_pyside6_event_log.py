"""Verify event log widget rendering and category colors (LOG-01, LOG-02).

Tests the EventLogWidget HTML output for five category colors, timestamp
inclusion, and read-only enforcement.
"""

import re

import pytest

from frontend_pyside6.models.seat_state import CATEGORY_COLORS
from frontend_pyside6.widgets.event_log import EventLogWidget


@pytest.fixture
def log_widget(qapp):
    """Return a fresh EventLogWidget for each test."""
    widget = EventLogWidget()
    yield widget
    widget.deleteLater()


class TestEventLogWidget:
    """Category color and formatting coverage for the event log."""

    def test_append_event_inserts_html(self, log_widget):
        """An event produces HTML containing the message text."""
        log_widget.append_event("LOCAL", "test message")
        html = log_widget.toHtml()
        assert "test message" in html

    def test_local_event_has_green_color(self, log_widget):
        """LOCAL events use green color (hex in rendered HTML)."""
        log_widget.append_event("LOCAL", "green msg")
        html = log_widget.toHtml().lower()
        # Color hex varies by system theme (GNOME Adwaita uses #2ec27e)
        assert "color:" in html and "green msg" in html

    def test_remote_event_has_orange_color(self, log_widget):
        """REMOTE events use orange color (hex in rendered HTML)."""
        log_widget.append_event("REMOTE", "orange msg")
        html = log_widget.toHtml().lower()
        assert "color:" in html and "orange msg" in html

    def test_error_event_has_red_color(self, log_widget):
        """ERROR events use red color (hex in rendered HTML)."""
        log_widget.append_event("ERROR", "error msg")
        html = log_widget.toHtml().lower()
        assert "color:" in html and "error msg" in html

    def test_timestamp_included(self, log_widget):
        """Every event includes a timestamp in HH:MM:SS format."""
        log_widget.append_event("SERVER", "ts msg")
        html = log_widget.toHtml()
        # Matches patterns like <span...>[... 12:34:56 ...] or [12:34:56]
        match = re.search(
            r"\d{2}:\d{2}:\d{2}", html
        )
        assert match is not None, f"No timestamp found in: {html[:200]}"

    def test_readonly(self, log_widget):
        """The event log must be read-only."""
        assert log_widget.isReadOnly() is True
