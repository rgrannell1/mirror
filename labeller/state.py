"""Application state: current photo index, field cursor, edit mode."""

from collections.abc import Callable
from dataclasses import dataclass, field

from .parser import EDITABLE_COLUMNS, PhotoRow


@dataclass
class AppState:
    all_photos: list[PhotoRow]
    photo_index: int = 0
    field_index: int = 0
    active_filter: str | None = None
    photos: list[PhotoRow] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.photos:
            self.photos = list(self.all_photos)

    @property
    def current_photo(self) -> PhotoRow:
        return self.photos[self.photo_index]

    @property
    def current_field(self) -> str:

        return EDITABLE_COLUMNS[self.field_index]

    def move_photo(self, delta: int) -> bool:
        """Move by delta photos with wraparound. Returns True if the index changed."""

        new_index = (self.photo_index + delta) % len(self.photos)
        changed = new_index != self.photo_index
        self.photo_index = new_index

        return changed

    def move_field(self, delta: int) -> bool:
        """Move by delta fields. Returns True if the index changed."""

        new_index = max(0, min(len(EDITABLE_COLUMNS) - 1, self.field_index + delta))
        changed = new_index != self.field_index
        self.field_index = new_index

        return changed

    def apply_filter(
        self,
        label: str | None,
        predicate: Callable[[PhotoRow], bool] | None,
    ) -> None:
        """Apply a named filter predicate, or pass None to show all photos."""

        self.active_filter = label
        self.photos = (
            list(self.all_photos)
            if predicate is None
            else [photo for photo in self.all_photos if predicate(photo)]
        )
        self.photo_index = 0
        self.field_index = 0
