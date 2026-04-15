"""Video application state: current video index, field cursor, edit history."""

from collections.abc import Callable
from dataclasses import dataclass, field

from .parser import EDITABLE_COLUMNS, VideoRow


@dataclass
class VideoState:
    all_videos: list[VideoRow]
    video_index: int = 0
    field_index: int = 0
    active_filter: str | None = None
    videos: list[VideoRow] = field(default_factory=list)
    known_genres: set[str] = field(default_factory=set)
    last_edit: tuple[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.videos:
            self.videos = list(self.all_videos)
        if not self.known_genres:
            self.known_genres = {video.genre for video in self.all_videos if video.genre.strip()}

    @property
    def current_video(self) -> VideoRow:
        return self.videos[self.video_index]

    @property
    def current_field(self) -> str:
        return EDITABLE_COLUMNS[self.field_index]

    def move_video(self, delta: int) -> bool:
        """Move by delta videos with wraparound. Returns True if the index changed."""
        new_index = (self.video_index + delta) % len(self.videos)
        changed = new_index != self.video_index
        self.video_index = new_index
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
        predicate: Callable[[VideoRow], bool] | None,
    ) -> None:
        """Apply a named filter predicate, or pass None to show all videos."""
        self.active_filter = label
        self.videos = (
            list(self.all_videos)
            if predicate is None
            else [video for video in self.all_videos if predicate(video)]
        )
        self.video_index = 0
        self.field_index = 0
