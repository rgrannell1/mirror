"""Trip-specific widgets: AlbumMultiSelect, TripFieldRow, TripFieldTable."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.markup import escape
from textual.widget import Widget
from textual.widgets import SelectionList

from labeller.messages import EditCancelled, SaveRequested
from labeller.things.trips import EDITABLE_COLUMNS
from labeller.widgets import FieldRow, FieldTable, _EDIT_INPUT_ID, _FIELD_ROW_ID_PREFIX, _RATING_SELECTOR_ID

ALBUMS_PATH = Path(__file__).parent.parent.parent / "albums.md"

_ALBUM_MULTI_SELECT_ID = "album-multi-select"


# ---------------------------------------------------------------------------
# Album metadata helpers
# ---------------------------------------------------------------------------

def load_album_titles(path: Path = ALBUMS_PATH) -> dict[str, str]:
    """Return {urn:ró:album:{permalink}: title} for all rows in albums.md."""
    titles: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "---" in line or line.startswith("| embedding"):
            continue
        cells = [cell.strip() for cell in line.split("|")][1:-1]
        if len(cells) >= 3 and cells[2]:
            titles[f"urn:ró:album:{cells[2]}"] = cells[1]
    return titles


def all_albums_ordered(album_titles: dict[str, str]) -> list[tuple[str, str]]:
    """Return [(title, urn), ...] in albums.md order."""
    return [(title, urn) for urn, title in album_titles.items()]


# ---------------------------------------------------------------------------
# AlbumMultiSelect
# ---------------------------------------------------------------------------

class AlbumMultiSelect(Widget):
    """Checkbox list for assigning albums to a trip.

    Space / Enter toggles an item. ctrl+s confirms; Escape cancels.
    Bindings propagate from the focused SelectionList up to this widget.
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save selection"),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    AlbumMultiSelect {
        height: 20;
        margin: 0 0 0 14;
        border: round $accent;
    }
    AlbumMultiSelect SelectionList {
        height: 1fr;
        border: none;
    }
    """

    def __init__(self, current_urns: list[str], albums: list[tuple[str, str]], **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_urns = set(current_urns)
        self._albums = albums

    def compose(self) -> ComposeResult:
        selections = [
            (title, urn, urn in self._current_urns)
            for title, urn in self._albums
        ]
        yield SelectionList(*selections)

    def on_mount(self) -> None:
        self.query_one(SelectionList).focus()

    def action_save(self) -> None:
        selected_set = set(self.query_one(SelectionList).selected)
        # Preserve albums.md order rather than arbitrary selection order
        ordered = [urn for _, urn in self._albums if urn in selected_set]
        self.post_message(SaveRequested(value=" ".join(ordered)))

    def action_cancel(self) -> None:
        self.post_message(EditCancelled())


# ---------------------------------------------------------------------------
# TripFieldRow
# ---------------------------------------------------------------------------

class TripFieldRow(FieldRow):
    """FieldRow that renders contains_album as resolved album titles."""

    def __init__(self, album_titles: dict[str, str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._album_titles = album_titles

    def _render_label(self) -> None:
        if self._field_name != "contains_album":
            super()._render_label()
            return

        if not self._value:
            display = "[dim](empty)[/dim]"
        else:
            urns = self._value.split()
            titles = [self._album_titles.get(urn, urn.split(":")[-1]) for urn in urns]
            noun = "album" if len(titles) == 1 else "albums"
            display = f"{len(titles)} {noun}: {escape(', '.join(titles))}"

        name_markup = f"[bold cyan]{self._field_name:>12}[/bold cyan]"
        self.update(f"{name_markup}  {display}")


# ---------------------------------------------------------------------------
# TripFieldTable
# ---------------------------------------------------------------------------

class TripFieldTable(FieldTable):
    """FieldTable for trips: opens AlbumMultiSelect for contains_album."""

    def __init__(self, album_titles: dict[str, str], **kwargs) -> None:
        super().__init__(editable_columns=EDITABLE_COLUMNS, **kwargs)
        self._album_titles = album_titles
        self._albums = all_albums_ordered(album_titles)

    def compose(self) -> ComposeResult:
        for field_index, field_name in enumerate(self._editable_columns):
            yield TripFieldRow(
                album_titles=self._album_titles,
                field_name=field_name,
                id=f"{_FIELD_ROW_ID_PREFIX}{field_index}",
            )

    def _make_editor(self, field_name: str, current_value: str) -> Widget:
        if field_name == "contains_album":
            current_urns = current_value.split() if current_value.strip() else []
            return AlbumMultiSelect(
                current_urns=current_urns,
                albums=self._albums,
                id=_ALBUM_MULTI_SELECT_ID,
            )
        return super()._make_editor(field_name, current_value)

    def exit_edit_mode(self) -> None:
        if not self._edit_mode:
            return
        self._edit_mode = False
        for widget in self.query(
            f"#{_EDIT_INPUT_ID}, #{_RATING_SELECTOR_ID}, #{_ALBUM_MULTI_SELECT_ID}"
        ):
            widget.remove()
        selected_row = self.query_one(f"#{_FIELD_ROW_ID_PREFIX}{self._field_index}", FieldRow)
        selected_row.display = True
        if self._row is not None:
            selected_row.refresh_value(
                value=self._row.get_field(self._editable_columns[self._field_index]),
                selected=True,
            )
        self.focus()
