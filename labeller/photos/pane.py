"""PhotoPane widget and PhotoFilterProvider for the Photos tab."""

import random
from collections.abc import Callable
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.command import Hit, Hits, Provider
from textual.widget import Widget
from textual.widgets import Label

from labeller.messages import EditCancelled, EditRequested, FieldChanged, SaveRequested
from labeller.opener import fpath_for_url, open_in_viewer
from labeller.widgets import ImageFrame

from .filters import PRESET_FILTERS
from .parser import PhotoRow, load_photos
from .state import PhotoState
from .widgets import PhotoFieldTable
from .writer import save_photo_row

PHOTOS_PATH = Path(__file__).parent.parent.parent / "photos.md"


class PhotoFilterProvider(Provider):
    """Command palette provider: preset filters and per-album/genre filters."""

    async def search(self, query: str) -> Hits:
        from textual.widgets import TabbedContent

        if self.app.query_one(TabbedContent).active != "photos":
            return

        pane: PhotoPane = self.app.query_one(PhotoPane)
        matcher = self.matcher(query)

        all_label = "All photos"
        all_score = matcher.match(all_label)
        if all_score > 0 or not query:
            yield Hit(
                score=all_score,
                match_display=matcher.highlight(all_label),
                command=lambda: pane._apply_filter(None, None),
                help="Remove filter — show all photos",
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
                            f"Genre > {g}", lambda photo, genre=g: photo.genre == genre
                        )
                    )(),
                    help=genre,
                )

        albums = sorted({photo.name for photo in pane._state.all_photos})
        for album_name in albums:
            namespaced = f"Album: {album_name}"
            score = matcher.match(namespaced)
            if score > 0 or not query:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(namespaced),
                    command=(
                        lambda name=album_name: lambda: pane._apply_filter(name, lambda photo, n=name: photo.name == n)
                    )(),
                    help=album_name,
                )


class PhotoPane(Widget):
    """Browse and edit photos.md entries."""

    BINDINGS = [
        Binding("left", "prev_photo", "Prev photo"),
        Binding("right", "next_photo", "Next photo"),
        Binding("[", "prev_album", "Prev album"),
        Binding("]", "next_album", "Next album"),
        Binding("r", "random_photo", "Random"),
        Binding("a", "repeat_edit", "Repeat last edit"),
        Binding("o", "open_image", "Open image"),
    ]

    DEFAULT_CSS = """
    PhotoPane {
        layout: vertical;
    }

    PhotoPane > #counter {
        text-align: center;
        color: $text-muted;
        height: 1;
        padding: 0 1;
    }

    PhotoPane > ImageFrame {
        margin: 0 1;
    }

    PhotoPane > FieldTable {
        margin: 0 1 1 1;
    }
    """

    def __init__(self, places: dict[str, str], subjects: dict[str, str], **kwargs) -> None:
        super().__init__(**kwargs)
        photos = load_photos(PHOTOS_PATH)
        self._state = PhotoState(all_photos=photos)
        self._places_urns = places
        self._subject_urns = subjects

    def compose(self) -> ComposeResult:
        yield Label(self._counter_text(), id="counter")
        yield ImageFrame(id="image-frame")
        yield PhotoFieldTable(
            genres=self._state.known_genres,
            places=self._places_urns,
            subjects=self._subject_urns,
            id="field-table",
        )

    def on_mount(self) -> None:
        self._refresh_all()
        self.query_one(PhotoFieldTable).focus()

    # ------------------------------------------------------------------
    # Navigation actions
    # ------------------------------------------------------------------

    def action_prev_photo(self) -> None:
        if self._state.move_photo(-1):
            self._refresh_all()

    def action_next_photo(self) -> None:
        if self._state.move_photo(1):
            self._refresh_all()

    def action_repeat_edit(self) -> None:
        if self.app.last_edit is None:
            self.app.notify("No previous edit to repeat", severity="warning")
            return
        field, value = self.app.last_edit
        from .parser import EDITABLE_COLUMNS

        if field not in EDITABLE_COLUMNS:
            self.app.notify(f"Field '{field}' not available for photos", severity="warning")
            return
        photo = self._state.current_photo
        photo.set_field(field, value)
        save_photo_row(PHOTOS_PATH, photo)
        if field == "genre" and value.strip():
            self._state.known_genres.add(value.strip())
        self.query_one(PhotoFieldTable).update_row(photo)
        self._refresh_counter()
        self.app.notify(f"{field} → {value}")

    def action_prev_album(self) -> None:
        self._jump_album(-1)

    def action_next_album(self) -> None:
        self._jump_album(1)

    def _jump_album(self, delta: int) -> None:
        photos = self._state.photos
        albums = sorted({photo.name for photo in photos})
        if len(albums) <= 1:
            return
        current_album = self._state.current_photo.name
        current_pos = albums.index(current_album) if current_album in albums else 0
        target_album = albums[(current_pos + delta) % len(albums)]
        target_index = next(idx for idx, photo in enumerate(photos) if photo.name == target_album)
        self._state.photo_index = target_index
        self._refresh_all()

    def action_random_photo(self) -> None:
        new_index = random.randrange(len(self._state.photos))
        self._state.photo_index = new_index
        self._refresh_all()

    def action_open_image(self) -> None:
        url = self._state.current_photo.thumbnail_url
        fpath = fpath_for_url(url)
        if fpath:
            open_in_viewer(fpath)
        else:
            self.app.notify(f"No local file found for {url}", severity="warning")

    def action_label_image(self) -> None:
        url = self._state.current_photo.thumbnail_url
        fpath = fpath_for_url(url)
        self.app.notify("Asking Google Vision...", timeout=3)
        self.run_worker(
            lambda: self._fetch_labels(fpath, url),
            exclusive=False,
            thread=True,
        )

    def _fetch_labels(self, fpath: str | None, url: str) -> None:
        from rich.markup import escape

        from .vision import label_image

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

    # ------------------------------------------------------------------
    # Message handlers (from PhotoFieldTable)
    # ------------------------------------------------------------------

    def on_edit_requested(self, message: EditRequested) -> None:
        message.stop()
        self.query_one(PhotoFieldTable).enter_edit_mode()

    def on_save_requested(self, message: SaveRequested) -> None:
        message.stop()
        photo = self._state.current_photo
        field = self._state.current_field
        new_value = message.value
        photo.set_field(field, new_value)
        save_photo_row(PHOTOS_PATH, photo)
        if field == "genre" and new_value.strip():
            self._state.known_genres.add(new_value.strip())
        self.app.last_edit = (field, new_value)
        field_table = self.query_one(PhotoFieldTable)
        field_table.exit_edit_mode()
        field_table.update_row(photo)
        self._refresh_counter()

    def on_edit_cancelled(self, message: EditCancelled) -> None:
        message.stop()
        self.query_one(PhotoFieldTable).exit_edit_mode()

    def on_field_changed(self, message: FieldChanged) -> None:
        message.stop()
        field_table = self.query_one(PhotoFieldTable)
        self._state.field_index = field_table._field_index

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_filter(
        self,
        label: str | None,
        predicate: Callable[[PhotoRow], bool] | None,
    ) -> None:
        self._state.apply_filter(label, predicate)
        if not self._state.photos:
            self.app.notify(f"No photos match '{label}'", severity="warning")
            self._state.apply_filter(None, None)
            return
        self._refresh_all()

    def _counter_text(self) -> str:
        total = len(self._state.photos)
        current = self._state.photo_index + 1
        filter_suffix = f"  [{self._state.active_filter}]" if self._state.active_filter else ""
        return f"Photo {current} / {total}{filter_suffix}"

    def _refresh_all(self) -> None:
        photo = self._state.current_photo
        self.query_one(ImageFrame).update_photo(photo.thumbnail_url)
        field_table = self.query_one(PhotoFieldTable)
        field_table.update_row(photo)
        field_table.update_field_index(self._state.field_index)
        self._refresh_counter()

    def _refresh_counter(self) -> None:
        self.query_one("#counter", Label).update(self._counter_text())
