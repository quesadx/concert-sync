"""Test TUI seat map rendering and empty-state handling."""

from unittest.mock import MagicMock, call, patch

import pytest
from rich.text import Text

from frontend_tui.app import ConcertTextualApp


@pytest.fixture
def app():
    """Return a ConcertTextualApp instance with mocked widgets."""
    app = ConcertTextualApp()
    # DataTable mock with trackable cursor_type
    table_mock = MagicMock()
    table_mock.cursor_type = "cell"
    table_mock.row_count = 0
    app.query_one = MagicMock(return_value=table_mock)
    # Use known grid data
    app.pending_selections = []
    return app


class TestRenderSeatMap:
    def _call_render(self, app):
        """Call _render_seat_map and return the DataTable mock."""
        app._render_seat_map()
        return app.query_one.return_value

    def test_empty_grid_sets_cursor_none(self, app):
        """Empty grid → cursor_type set to 'none', no rows added."""
        app.seat_map_snapshot = {"GENERAL": []}
        app.selected_map_section = "GENERAL"

        table = self._call_render(app)

        assert table.cursor_type == "none"
        table.clear.assert_called_with(columns=True)
        table.add_columns.assert_not_called()
        table.add_row.assert_not_called()

    def test_empty_grid_updates_legend(self, app):
        """Empty grid → legend shows 'No seat map data'."""
        app.seat_map_snapshot = {"GENERAL": []}
        app.selected_map_section = "GENERAL"
        legend_mock = MagicMock()

        def query_one_side_effect(selector, widget_type=None):
            if selector == "#seat-map-legend":
                return legend_mock
            return MagicMock()

        app.query_one = MagicMock(side_effect=query_one_side_effect)

        app._render_seat_map()

        legend_mock.update.assert_called_with("No seat map data")

    def test_single_row_renders_correctly(self, app):
        """Grid with 1 row → cursor_type='cell', 1 row added."""
        app.seat_map_snapshot = {"GENERAL": [["AVAILABLE", "RESERVED"]]}
        app.selected_map_section = "GENERAL"

        table = self._call_render(app)

        assert table.cursor_type == "cell"
        table.clear.assert_called_with(columns=True)
        table.add_columns.assert_called_once_with("0", "1")
        table.add_row.assert_called_once()

    def test_multi_row_renders_correctly(self, app):
        """Grid with multiple rows → all rows added, cursor_type='cell'."""
        grid = [
            ["AVAILABLE", "SOLD"],
            ["RESERVED", "AVAILABLE"],
            ["SOLD", "AVAILABLE"],
        ]
        app.seat_map_snapshot = {"GENERAL": grid}
        app.selected_map_section = "GENERAL"

        table = self._call_render(app)

        assert table.cursor_type == "cell"
        assert table.add_row.call_count == 3

    def test_pending_selection_renders_as_pending(self, app):
        """Pending selections show 'P' style in cell."""
        app.seat_map_snapshot = {"GENERAL": [["AVAILABLE"]]}
        app.selected_map_section = "GENERAL"
        app.pending_selections = [{"section": "GENERAL", "row": 0, "col": 0}]

        table = self._call_render(app)

        # PENDING has style → rich Text object passed to add_row
        add_row_args = table.add_row.call_args
        assert add_row_args is not None
        cell = add_row_args[0][0]
        assert isinstance(cell, Text)
        assert cell.plain == "P"

    def test_different_section_selected(self, app):
        """Switching sections renders the correct section grid."""
        app.seat_map_snapshot = {
            "VIP": [["AVAILABLE"]],
            "GENERAL": [["SOLD"]],
        }
        app.selected_map_section = "VIP"

        table = self._call_render(app)

        token = table.add_row.call_args[0][0]
        assert token == "A"

    def test_empty_section_falls_back_to_no_data(self, app):
        """Section with missing key in snapshot → 'No seat map data'."""
        app.seat_map_snapshot = {"VIP": [["AVAILABLE"]]}
        app.selected_map_section = "GENERAL"
        legend_mock = MagicMock()

        def query_one_side_effect(selector, widget_type=None):
            if selector == "#seat-map-legend":
                return legend_mock
            return MagicMock()

        app.query_one = MagicMock(side_effect=query_one_side_effect)

        app._render_seat_map()

        legend_mock.update.assert_called_with("No seat map data")

    def test_empty_grid_cursor_type_not_cell(self, app):
        """Regression: empty grid must NOT leave cursor_type='cell'."""
        app.seat_map_snapshot = {"GENERAL": []}
        app.selected_map_section = "GENERAL"

        table = self._call_render(app)

        assert table.cursor_type != "cell"
        assert table.cursor_type == "none"

    def test_non_empty_grid_restores_cursor_type_cell(self, app):
        """Regression: populated grid must set cursor_type='cell'."""
        app.seat_map_snapshot = {"GENERAL": [["AVAILABLE"]]}
        app.selected_map_section = "GENERAL"

        table = self._call_render(app)

        assert table.cursor_type == "cell"

    def test_data_loading_failure_preserves_empty_state(self, app):
        """After failed refresh, grid can be empty and render safely."""
        # Simulate server returning empty after failure
        app.seat_map_snapshot = {"GENERAL": []}
        app.selected_map_section = "GENERAL"

        table = self._call_render(app)

        assert table.cursor_type == "none"
        table.add_row.assert_not_called()
