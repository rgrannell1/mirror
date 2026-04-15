"""TripPane: browse and edit [[trips]] entries from things.toml."""

import random

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Label

from labeller.messages import EditCancelled, EditRequested, FieldChanged, SaveRequested
from labeller.things.trips import load_trips

from .state import TripState
from .widgets import TripFieldTable, load_album_titles
from .writer import save_trip_row


class TripPane(Widget):
    """Browse and edit [[trips]] in things.toml."""

    BINDINGS = [
        Binding("left", "prev", "Prev trip"),
        Binding("right", "next", "Next trip"),
        Binding("r", "random", "Random"),
    ]

    DEFAULT_CSS = """
    TripPane {
        layout: vertical;
    }
    TripPane > #counter {
        text-align: center;
        color: $text-muted;
        height: 1;
        padding: 0 1;
    }
    TripPane > TripFieldTable {
        margin: 0 1 1 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._state = TripState(all_trips=load_trips())
        self._album_titles = load_album_titles()

    def compose(self) -> ComposeResult:
        yield Label(self._counter_text(), id="counter")
        yield TripFieldTable(album_titles=self._album_titles, id="field-table")

    def on_mount(self) -> None:
        self._refresh_all()
        self.query_one(TripFieldTable).focus()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def action_prev(self) -> None:
        if self._state.move(-1):
            self._refresh_all()

    def action_next(self) -> None:
        if self._state.move(1):
            self._refresh_all()

    def action_random(self) -> None:
        self._state.trip_index = random.randrange(len(self._state.all_trips))
        self._refresh_all()

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    def on_edit_requested(self, message: EditRequested) -> None:
        message.stop()
        self.query_one(TripFieldTable).enter_edit_mode()

    def on_save_requested(self, message: SaveRequested) -> None:
        message.stop()
        trip = self._state.current_trip
        trip.set_field(self._state.current_field, message.value)
        save_trip_row(trip)
        # Reload so all trips have fresh line numbers after the write
        self._state.all_trips = load_trips()
        self._state.trip_index = min(self._state.trip_index, len(self._state.all_trips) - 1)
        field_table = self.query_one(TripFieldTable)
        field_table.exit_edit_mode()
        field_table.update_row(self._state.current_trip)
        self._refresh_counter()

    def on_edit_cancelled(self, message: EditCancelled) -> None:
        message.stop()
        self.query_one(TripFieldTable).exit_edit_mode()

    def on_field_changed(self, message: FieldChanged) -> None:
        message.stop()
        self._state.field_index = self.query_one(TripFieldTable)._field_index

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _counter_text(self) -> str:
        trip = self._state.current_trip
        short_id = trip.trip_id.split(":")[-1]
        return f"Trip {short_id}  ({self._state.trip_index + 1} / {len(self._state.all_trips)})"

    def _refresh_all(self) -> None:
        field_table = self.query_one(TripFieldTable)
        field_table.update_row(self._state.current_trip)
        field_table.update_field_index(self._state.field_index)
        self._refresh_counter()

    def _refresh_counter(self) -> None:
        self.query_one("#counter", Label).update(self._counter_text())
