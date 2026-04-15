"""Trip application state: current index and field cursor."""

from dataclasses import dataclass

from labeller.things.trips import EDITABLE_COLUMNS, TripRow


@dataclass
class TripState:
    all_trips: list[TripRow]
    trip_index: int = 0
    field_index: int = 0

    @property
    def current_trip(self) -> TripRow:
        return self.all_trips[self.trip_index]

    @property
    def current_field(self) -> str:
        return EDITABLE_COLUMNS[self.field_index]

    def move(self, delta: int) -> bool:
        new_index = (self.trip_index + delta) % len(self.all_trips)
        changed = new_index != self.trip_index
        self.trip_index = new_index
        return changed
