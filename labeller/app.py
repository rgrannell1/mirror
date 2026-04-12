"""Main Textual application: layout, keybindings, and event wiring."""

import random
from collections.abc import Callable
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import Hit, Hits, Provider
from textual.widgets import Footer, Header, Label

from labeller.filters import PRESET_FILTERS

from .messages import EditCancelled, EditRequested, PhotoChanged, SaveRequested
from .opener import fpath_for_url, open_in_viewer
from .parser import PhotoRow, load_photos
from .state import AppState
from .widgets import FieldTable, ImageFrame
from .writer import save_row

PHOTOS_PATH = Path(__file__).parent.parent / "photos.md"

class PhotoFilterProvider(Provider):
    """Command palette provider: preset filters and per-album filters."""

    async def search(self, query: str) -> Hits:
        app: PhotoTUI = self.app  # type: ignore[assignment]
        matcher = self.matcher(query)

        # "Show all" entry
        all_label = "All photos"
        all_score = matcher.match(all_label)
        if all_score > 0 or not query:
            yield Hit(
                score=all_score,
                match_display=matcher.highlight(all_label),
                command=lambda: app._apply_filter(None, None),
                help="Remove filter — show all photos",
            )

        # Preset filters
        for preset_label, predicate in PRESET_FILTERS:
            namespaced = f"Filter: {preset_label}"
            score = matcher.match(namespaced)
            if score > 0 or not query:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(namespaced),
                    command=(
                        lambda lbl=preset_label, pred=predicate: lambda: app._apply_filter(lbl, pred)
                    )(),
                    help=preset_label.lower(),
                )

        # Per-genre entries
        for genre in sorted(app._state.known_genres):
            namespaced = f"Filter: Genre > {genre}"
            score = matcher.match(namespaced)
            if score > 0 or not query:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(namespaced),
                    command=(
                        lambda g=genre: lambda: app._apply_filter(
                            f"Genre > {g}", lambda photo, genre=g: photo.genre == genre
                        )
                    )(),
                    help=genre,
                )

        # Per-album entries
        albums = sorted({photo.name for photo in app._state.all_photos})
        for album_name in albums:
            namespaced = f"Album: {album_name}"
            score = matcher.match(namespaced)
            if score > 0 or not query:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(namespaced),
                    command=(
                        lambda name=album_name: lambda: app._apply_filter(
                            name, lambda photo, n=name: photo.name == n
                        )
                    )(),
                    help=album_name,
                )


class PhotoTUI(App):
    """Browse and edit photos.md entries in the terminal."""

    COMMANDS = App.COMMANDS | {PhotoFilterProvider}

    CSS = """
    Screen {
        layout: vertical;
    }

    #counter {
        dock: top;
        text-align: center;
        color: $text-muted;
        height: 1;
        padding: 0 1;
    }

    ImageFrame {
        margin: 0 1;
    }

    FieldTable {
        margin: 0 1 1 1;
    }
    """

    BINDINGS = [
        Binding("left", "prev_photo", "Prev photo"),
        Binding("right", "next_photo", "Next photo"),
        Binding("[", "prev_album", "Prev album"),
        Binding("]", "next_album", "Next album"),
        Binding("r", "random_photo", "Random"),
        Binding("a", "repeat_edit", "Repeat last edit"),
        Binding("o", "open_image", "Open image"),
        Binding("m", "open_things", "Open things.toml"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        photos = load_photos(PHOTOS_PATH)
        self._state = AppState(all_photos=photos)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(self._counter_text(), id="counter")
        yield ImageFrame(id="image-frame")
        yield FieldTable(id="field-table")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_all()
        self.query_one(FieldTable).focus()

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
        if self._state.last_edit is None:
            self.notify("No previous edit to repeat", severity="warning")
            return
        field, value = self._state.last_edit
        photo = self._state.current_photo
        photo.set_field(field, value)
        save_row(PHOTOS_PATH, photo)
        if field == "genre" and value.strip():
            self._state.known_genres.add(value.strip())
        field_table = self.query_one(FieldTable)
        field_table.update_photo(photo)
        self._refresh_counter()
        self.notify(f"{field} → {value}")

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
        photos = self._state.photos
        new_index = random.randrange(len(photos))
        self._state.photo_index = new_index
        self._refresh_all()

    def action_open_things(self) -> None:
        import subprocess
        from .things import THINGS_PATH
        subprocess.Popen(["code", str(THINGS_PATH)])

    def action_open_image(self) -> None:
        url = self._state.current_photo.thumbnail_url
        fpath = fpath_for_url(url)
        if fpath:
            open_in_viewer(fpath)
        else:
            self.notify(f"No local file found for {url}", severity="warning")

    # ------------------------------------------------------------------
    # Message handlers (from FieldTable)
    # ------------------------------------------------------------------

    def on_edit_requested(self, message: EditRequested) -> None:
        message.stop()
        self.query_one(FieldTable).enter_edit_mode()

    def on_save_requested(self, message: SaveRequested) -> None:
        message.stop()
        photo = self._state.current_photo
        field = self._state.current_field
        new_value = message.value
        photo.set_field(field, new_value)
        save_row(PHOTOS_PATH, photo)
        if field == "genre" and new_value.strip():
            self._state.known_genres.add(new_value.strip())
        self._state.last_edit = (field, new_value)
        field_table = self.query_one(FieldTable)
        field_table.exit_edit_mode()
        field_table.update_photo(photo)
        self._refresh_counter()

    def on_edit_cancelled(self, message: EditCancelled) -> None:
        message.stop()
        self.query_one(FieldTable).exit_edit_mode()

    # ------------------------------------------------------------------
    # Sync field_index from FieldTable back to AppState
    # ------------------------------------------------------------------

    def on_field_changed(self, message: PhotoChanged) -> None:
        message.stop()
        # FieldTable manages its own field_index internally; we keep AppState in sync
        field_table = self.query_one(FieldTable)
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
            self.notify(f"No photos match '{label}'", severity="warning")
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
        self.query_one(ImageFrame).update_photo(photo)
        field_table = self.query_one(FieldTable)
        field_table.update_photo(photo)
        field_table.update_field_index(self._state.field_index)
        self._refresh_counter()

    def _refresh_counter(self) -> None:

        self.query_one("#counter", Label).update(self._counter_text())
