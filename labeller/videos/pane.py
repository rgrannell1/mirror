"""VideoPane widget and VideoFilterProvider for the Videos tab."""

import random
import subprocess
from collections.abc import Callable
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.command import Hit, Hits, Provider
from textual.widget import Widget
from textual.widgets import Label, Static

from labeller.messages import EditCancelled, EditRequested, FieldChanged, SaveRequested
from labeller.opener import fpath_for_url, open_in_viewer
from labeller.widgets import ImageFrame

from .filters import PRESET_FILTERS
from .parser import VideoRow, load_videos
from .state import VideoState
from .widgets import VideoFieldTable
from .writer import save_video_row

VIDEOS_PATH = Path(__file__).parent.parent.parent / "videos.md"


class VideoFilterProvider(Provider):
    """Command palette provider: preset filters and per-album/genre filters."""

    async def search(self, query: str) -> Hits:
        from textual.widgets import TabbedContent

        if self.app.query_one(TabbedContent).active != "videos":
            return

        pane: VideoPane = self.app.query_one(VideoPane)
        matcher = self.matcher(query)

        all_label = "All videos"
        all_score = matcher.match(all_label)
        if all_score > 0 or not query:
            yield Hit(
                score=all_score,
                match_display=matcher.highlight(all_label),
                command=lambda: pane._apply_filter(None, None),
                help="Remove filter — show all videos",
            )

        for preset_label, predicate in PRESET_FILTERS:
            namespaced = f"Filter: {preset_label}"
            score = matcher.match(namespaced)
            if score > 0 or not query:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(namespaced),
                    command=(lambda lbl=preset_label, pred=predicate: lambda: pane._apply_filter(lbl, pred))(),
                    help=preset_label.lower(),
                )

        for genre in sorted(pane._state.known_genres):
            namespaced = f"Filter: Genre > {genre}"
            score = matcher.match(namespaced)
            if score > 0 or not query:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(namespaced),
                    command=(
                        lambda g=genre: lambda: pane._apply_filter(
                            f"Genre > {g}", lambda video, genre=g: video.genre == genre
                        )
                    )(),
                    help=genre,
                )

        albums = sorted({video.name for video in pane._state.all_videos})
        for album_name in albums:
            namespaced = f"Album: {album_name}"
            score = matcher.match(namespaced)
            if score > 0 or not query:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(namespaced),
                    command=(
                        lambda name=album_name: lambda: pane._apply_filter(name, lambda video, n=name: video.name == n)
                    )(),
                    help=album_name,
                )


class VideoPane(Widget):
    """Browse and edit videos.md entries."""

    BINDINGS = [
        Binding("left", "prev_video", "Prev video"),
        Binding("right", "next_video", "Next video"),
        Binding("[", "prev_album", "Prev album"),
        Binding("]", "next_album", "Next album"),
        Binding("r", "random_video", "Random"),
        Binding("a", "repeat_edit", "Repeat last edit"),
        Binding("o", "open_image", "Open poster"),
        Binding("p", "play_video", "Play video"),
    ]

    DEFAULT_CSS = """
    VideoPane {
        layout: vertical;
    }

    VideoPane > #counter {
        text-align: center;
        color: $text-muted;
        height: 1;
        padding: 0 1;
    }

    VideoPane > ImageFrame {
        margin: 0 1;
    }

    VideoPane > FieldTable {
        margin: 0 1 1 1;
    }

    VideoPane > #playback-hint {
        text-align: center;
        color: $text-muted;
        height: 1;
        padding: 0 1;
    }
    """

    def __init__(self, places: dict[str, str], subjects: dict[str, str], **kwargs) -> None:
        super().__init__(**kwargs)
        videos = load_videos(VIDEOS_PATH)
        self._state = VideoState(all_videos=videos)
        self._places_urns = places
        self._subject_urns = subjects

    def compose(self) -> ComposeResult:
        yield Label(self._counter_text(), id="counter")
        yield ImageFrame(id="image-frame")
        yield VideoFieldTable(
            genres=self._state.known_genres,
            places=self._places_urns,
            subjects=self._subject_urns,
            id="field-table",
        )
        yield Static("p play  ·  space pause  ·  ← → seek  ·  [ ] speed  ·  q quit", id="playback-hint")

    def on_mount(self) -> None:
        # Populate the field table without loading an image — the pane is
        # hidden at this point and issuing Kitty protocol writes from a hidden
        # widget corrupts the display in the active pane.
        if not self._state.videos:
            self._refresh_counter()
            return
        video = self._state.current_video
        field_table = self.query_one(VideoFieldTable)
        field_table.update_row(video)
        field_table.update_field_index(self._state.field_index)
        self._refresh_counter()

    def on_show(self) -> None:
        """Called when the Videos tab becomes the active tab."""
        self._refresh_all()
        self.query_one(VideoFieldTable).focus()

    # ------------------------------------------------------------------
    # Navigation actions
    # ------------------------------------------------------------------

    def action_prev_video(self) -> None:
        if self._state.move_video(-1):
            self._refresh_all()

    def action_next_video(self) -> None:
        if self._state.move_video(1):
            self._refresh_all()

    def action_repeat_edit(self) -> None:
        if self.app.last_edit is None:
            self.app.notify("No previous edit to repeat", severity="warning")
            return
        field, value = self.app.last_edit
        from .parser import EDITABLE_COLUMNS

        if field not in EDITABLE_COLUMNS:
            self.app.notify(f"Field '{field}' not available for videos", severity="warning")
            return
        video = self._state.current_video
        video.set_field(field, value)
        save_video_row(VIDEOS_PATH, video)
        if field == "genre" and value.strip():
            self._state.known_genres.add(value.strip())
        self.query_one(VideoFieldTable).update_row(video)
        self._refresh_counter()
        self.app.notify(f"{field} → {value}")

    def action_prev_album(self) -> None:
        self._jump_album(-1)

    def action_next_album(self) -> None:
        self._jump_album(1)

    def _jump_album(self, delta: int) -> None:
        videos = self._state.videos
        albums = sorted({video.name for video in videos})
        if len(albums) <= 1:
            return
        current_album = self._state.current_video.name
        current_pos = albums.index(current_album) if current_album in albums else 0
        target_album = albums[(current_pos + delta) % len(albums)]
        target_index = next(idx for idx, video in enumerate(videos) if video.name == target_album)
        self._state.video_index = target_index
        self._refresh_all()

    def action_random_video(self) -> None:
        new_index = random.randrange(len(self._state.videos))
        self._state.video_index = new_index
        self._refresh_all()

    def action_open_image(self) -> None:
        url = self._state.current_video.thumbnail_url
        fpath = fpath_for_url(url)
        if fpath:
            open_in_viewer(fpath)
        else:
            self.app.notify(f"No local file found for {url}", severity="warning")

    _IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    def action_label_image(self) -> None:
        video = self._state.current_video
        url = video.cover.strip() or video.thumbnail_url
        raw_fpath = fpath_for_url(url)
        from pathlib import Path

        fpath = raw_fpath if raw_fpath and Path(raw_fpath).suffix.lower() in self._IMAGE_SUFFIXES else None
        self.app.notify("Asking Google Vision...", timeout=3)
        self.run_worker(
            lambda: self._fetch_labels(fpath, url),
            exclusive=False,
            thread=True,
        )

    def _fetch_labels(self, fpath: str | None, url: str) -> None:
        from rich.markup import escape
        from labeller.photos.vision import label_image

        try:
            labels = label_image(fpath, url)
        except Exception as exc:
            self.app.call_from_thread(self.app.notify, escape(f"Vision API error: {exc}"), severity="error", timeout=8)
            return
        if not labels:
            self.app.call_from_thread(self.app.notify, "No labels returned", severity="warning")
            return
        text = escape("  •  ".join(labels[:6]))
        self.app.call_from_thread(self.app.copy_to_clipboard, "  •  ".join(labels[:6]))
        self.app.call_from_thread(self.app.notify, text, timeout=12)

    def action_play_video(self) -> None:
        fpath = fpath_for_url(self._state.current_video.thumbnail_url)
        if not fpath:
            self.app.notify("No local video file found", severity="warning")
            return
        try:
            with self.app.suspend():
                subprocess.run(["mpv", "--vo=kitty", "--really-quiet", fpath])
        except FileNotFoundError:
            self.app.notify("mpv not found — install it to play videos", severity="error")

    # ------------------------------------------------------------------
    # Message handlers (from VideoFieldTable)
    # ------------------------------------------------------------------

    def on_edit_requested(self, message: EditRequested) -> None:
        message.stop()
        self.query_one(VideoFieldTable).enter_edit_mode()

    def on_save_requested(self, message: SaveRequested) -> None:
        message.stop()
        video = self._state.current_video
        field = self._state.current_field
        new_value = message.value
        video.set_field(field, new_value)
        save_video_row(VIDEOS_PATH, video)
        if field == "genre" and new_value.strip():
            self._state.known_genres.add(new_value.strip())
        self.app.last_edit = (field, new_value)
        field_table = self.query_one(VideoFieldTable)
        field_table.exit_edit_mode()
        field_table.update_row(video)
        self._refresh_counter()

    def on_edit_cancelled(self, message: EditCancelled) -> None:
        message.stop()
        self.query_one(VideoFieldTable).exit_edit_mode()

    def on_field_changed(self, message: FieldChanged) -> None:
        message.stop()
        field_table = self.query_one(VideoFieldTable)
        self._state.field_index = field_table._field_index

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_filter(
        self,
        label: str | None,
        predicate: Callable[[VideoRow], bool] | None,
    ) -> None:
        self._state.apply_filter(label, predicate)
        if not self._state.videos:
            self.app.notify(f"No videos match '{label}'", severity="warning")
            self._state.apply_filter(None, None)
            return
        self._refresh_all()

    def _counter_text(self) -> str:
        total = len(self._state.videos)
        if total == 0:
            return "No videos"
        current = self._state.video_index + 1
        filter_suffix = f"  [{self._state.active_filter}]" if self._state.active_filter else ""
        return f"Video {current} / {total}{filter_suffix}"

    def _refresh_all(self) -> None:
        if not self._state.videos:
            return
        video = self._state.current_video
        self.query_one(ImageFrame).update_photo(video.thumbnail_url)
        field_table = self.query_one(VideoFieldTable)
        field_table.update_row(video)
        field_table.update_field_index(self._state.field_index)
        self._refresh_counter()

    def _refresh_counter(self) -> None:
        self.query_one("#counter", Label).update(self._counter_text())
