"""Album application state: current album index, field cursor, edit history."""

from collections.abc import Callable
from dataclasses import dataclass, field

from .parser import EDITABLE_COLUMNS, AlbumRow


@dataclass
class AlbumState:
    all_albums: list[AlbumRow]
    album_index: int = 0
    field_index: int = 0
    active_filter: str | None = None
    albums: list[AlbumRow] = field(default_factory=list)
    last_edit: tuple[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.albums:
            self.albums = list(self.all_albums)

    @property
    def current_album(self) -> AlbumRow:
        return self.albums[self.album_index]

    @property
    def current_field(self) -> str:
        return EDITABLE_COLUMNS[self.field_index]

    def move_album(self, delta: int) -> bool:
        """Move by delta albums with wraparound. Returns True if the index changed."""
        new_index = (self.album_index + delta) % len(self.albums)
        changed = new_index != self.album_index
        self.album_index = new_index
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
        predicate: Callable[[AlbumRow], bool] | None,
    ) -> None:
        """Apply a named filter predicate, or pass None to show all albums."""
        self.active_filter = label
        self.albums = (
            list(self.all_albums)
            if predicate is None
            else [album for album in self.all_albums if predicate(album)]
        )
        self.album_index = 0
        self.field_index = 0
