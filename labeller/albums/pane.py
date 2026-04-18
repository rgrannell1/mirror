"""AlbumPane widget and AlbumFilterProvider for the Albums tab."""

import random
from collections.abc import Callable
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.command import Hit, Hits, Provider
from textual.widget import Widget
from textual.widgets import Label

from labeller.messages import EditCancelled, EditRequested, FieldChanged, SaveRequested
from labeller.widgets import FieldTable, ImageFrame

from .parser import AlbumRow, load_albums, EDITABLE_COLUMNS
from .state import AlbumState
from .widgets import AlbumFieldTable
from .writer import save_album_row

ALBUMS_PATH = Path(__file__).parent.parent.parent / "albums.md"

PRESET_FILTERS: list[tuple[str, Callable[[AlbumRow], bool]]] = [
    ("Has summary", lambda album: bool(album.summary.strip())),
    ("No summary", lambda album: not album.summary.strip()),
    ("Has permalink", lambda album: bool(album.permalink.strip())),
]


class AlbumFilterProvider(Provider):
    """Command palette provider: preset filters and per-country filters for albums."""

    async def search(self, query: str) -> Hits:
        from textual.widgets import TabbedContent

        if self.app.query_one(TabbedContent).active != "albums":
            return

        pane: AlbumPane = self.app.query_one(AlbumPane)
        matcher = self.matcher(query)

        all_label = "All albums"
        all_score = matcher.match(all_label)
        if all_score > 0 or not query:
            yield Hit(
                score=all_score,
                match_display=matcher.highlight(all_label),
                command=lambda: pane._apply_filter(None, None),
                help="Remove filter — show all albums",
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

        countries = sorted({album.country for album in pane._state.all_albums if album.country.strip()})
        for country in countries:
            namespaced = f"Country: {country}"
            score = matcher.match(namespaced)
            if score > 0 or not query:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(namespaced),
                    command=(
                        lambda c=country: lambda: pane._apply_filter(
                            c, lambda album, country=c: album.country == country
                        )
                    )(),
                    help=country,
                )


class AlbumPane(Widget):
    """Browse and edit albums.md entries."""

    BINDINGS = [
        Binding("left", "prev_album", "Prev album"),
        Binding("right", "next_album", "Next album"),
        Binding("r", "random_album", "Random"),
        Binding("a", "repeat_edit", "Repeat last edit"),
        Binding("o", "open_image", "Open image"),
    ]

    DEFAULT_CSS = """
    AlbumPane {
        layout: vertical;
    }

    AlbumPane > #counter {
        text-align: center;
        color: $text-muted;
        height: 1;
        padding: 0 1;
    }

    AlbumPane > ImageFrame {
        margin: 0 1;
    }

    AlbumPane > FieldTable {
        margin: 0 1 1 1;
    }
    """

    def __init__(self, places: dict[str, str], **kwargs) -> None:
        super().__init__(**kwargs)
        albums = load_albums(ALBUMS_PATH)
        self._state = AlbumState(all_albums=albums)
        self._places = places

    def compose(self) -> ComposeResult:
        yield Label(self._counter_text(), id="counter")
        yield ImageFrame(id="image-frame")
        yield AlbumFieldTable(places=self._places, id="field-table")

    def on_mount(self) -> None:
        self._refresh_all()
        self.query_one(FieldTable).focus()

    # ------------------------------------------------------------------
    # Navigation actions
    # ------------------------------------------------------------------

    def action_prev_album(self) -> None:
        if self._state.move_album(-1):
            self._refresh_all()

    def action_next_album(self) -> None:
        if self._state.move_album(1):
            self._refresh_all()

    def action_repeat_edit(self) -> None:
        if self.app.last_edit is None:
            self.app.notify("No previous edit to repeat", severity="warning")
            return
        field, value = self.app.last_edit
        if field not in EDITABLE_COLUMNS:
            self.app.notify(f"Field '{field}' not available for albums", severity="warning")
            return
        album = self._state.current_album
        album.set_field(field, value)
        save_album_row(ALBUMS_PATH, album)
        self.query_one(FieldTable).update_row(album)
        self._refresh_counter()
        self.app.notify(f"{field} → {value}")

    def action_random_album(self) -> None:
        new_index = random.randrange(len(self._state.albums))
        self._state.album_index = new_index
        self._refresh_all()

    def action_open_image(self) -> None:
        from labeller.opener import fpath_for_url, open_in_viewer

        url = self._state.current_album.thumbnail_url
        fpath = fpath_for_url(url)
        if fpath:
            open_in_viewer(fpath)
        else:
            self.app.notify(f"No local file found for {url}", severity="warning")

    # ------------------------------------------------------------------
    # Message handlers (from FieldTable)
    # ------------------------------------------------------------------

    def on_edit_requested(self, message: EditRequested) -> None:
        message.stop()
        self.query_one(FieldTable).enter_edit_mode()

    def on_save_requested(self, message: SaveRequested) -> None:
        message.stop()
        album = self._state.current_album
        field = self._state.current_field
        new_value = message.value
        album.set_field(field, new_value)
        save_album_row(ALBUMS_PATH, album)
        self.app.last_edit = (field, new_value)
        field_table = self.query_one(FieldTable)
        field_table.exit_edit_mode()
        field_table.update_row(album)
        self._refresh_counter()

    def on_edit_cancelled(self, message: EditCancelled) -> None:
        message.stop()
        self.query_one(FieldTable).exit_edit_mode()

    def on_field_changed(self, message: FieldChanged) -> None:
        message.stop()
        field_table = self.query_one(FieldTable)
        self._state.field_index = field_table._field_index

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_filter(
        self,
        label: str | None,
        predicate: Callable[[AlbumRow], bool] | None,
    ) -> None:
        self._state.apply_filter(label, predicate)
        if not self._state.albums:
            self.app.notify(f"No albums match '{label}'", severity="warning")
            self._state.apply_filter(None, None)
            return
        self._refresh_all()

    def _counter_text(self) -> str:
        total = len(self._state.albums)
        current = self._state.album_index + 1
        filter_suffix = f"  [{self._state.active_filter}]" if self._state.active_filter else ""
        return f"Album {current} / {total}{filter_suffix}"

    def _refresh_all(self) -> None:
        album = self._state.current_album
        self.query_one(ImageFrame).update_photo(album.thumbnail_url)
        field_table = self.query_one(FieldTable)
        field_table.update_row(album)
        field_table.update_field_index(self._state.field_index)
        self._refresh_counter()

    def _refresh_counter(self) -> None:
        self.query_one("#counter", Label).update(self._counter_text())
