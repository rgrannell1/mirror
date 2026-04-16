"""Reusable Textual widgets: ImageFrame, RatingSelector, FieldRow, and FieldTable."""

import tomllib
from collections.abc import Callable
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.markup import escape
from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Input, Static
from textual_image.widget import Image as TIImage

from .image_loader import fetch_image
from .messages import EditCancelled, EditRequested, FieldChanged, SaveRequested

THINGS_PATH = Path(__file__).parent.parent / "things.toml"


def load_places() -> dict[str, str]:
    """Return {name: urn} for all named places in things.toml."""
    if not THINGS_PATH.exists():
        return {}
    with open(THINGS_PATH, "rb") as fh:
        data = tomllib.load(fh)
    return {
        entry["name"]: entry["id"]
        for entry in data.get("places", [])
        if "name" in entry and "id" in entry
    }


def load_subjects() -> dict[str, str]:
    """Return {name: urn} for all non-place entries in things.toml."""
    if not THINGS_PATH.exists():
        return {}
    with open(THINGS_PATH, "rb") as fh:
        data = tomllib.load(fh)
    result: dict[str, str] = {}
    for section, entries in data.items():
        if section == "places" or not isinstance(entries, list):
            continue
        for entry in entries:
            if "name" in entry and "id" in entry:
                result[entry["name"]] = entry["id"]
    return result

_FIELD_ROW_ID_PREFIX = "field-row-"
_EDIT_INPUT_ID = "edit-input"
_RATING_SELECTOR_ID = "rating-selector"

RATING_OPTIONS = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]


class CyclingSuggester(Suggester):
    """Base suggester with separate ghost-text and cycling state.

    Ghost text (`get_suggestion`) only fires for prefix matches, so Textual's
    ``suggestion[len(value):]`` rendering always shows a sensible suffix.

    Cycling (`cycle`) keeps its own ``_cycle_base`` / ``_cycle_matches`` /
    ``_cycle_index`` state that is independent of the ghost-text path, so
    programmatic value replacements by FieldTable don't reset the cycle.
    """

    def __init__(self) -> None:
        super().__init__(use_cache=False, case_sensitive=False)
        # Ghost-text state
        self._last_query: str = ""
        self._prefix_matches: list[str] = []
        # Cycling state (independent — not touched by get_suggestion)
        self._cycle_base: str = ""
        self._cycle_matches: list[str] = []
        self._cycle_index: int = -1

    def _compute_matches(self, value: str) -> list[str]:
        raise NotImplementedError

    async def get_suggestion(self, value: str) -> str | None:
        if not value:
            self._last_query = ""
            self._prefix_matches = []
            return None
        if value != self._last_query:
            self._last_query = value
            lower = value.casefold()
            all_matches = self._compute_matches(value)
            self._prefix_matches = [m for m in all_matches if m.casefold().startswith(lower)]
        return self._prefix_matches[0] if self._prefix_matches else None

    def cycle(self, base_query: str, delta: int) -> str | None:
        """Cycle through all matches (prefix + infix) for *base_query*.

        Cycling state is keyed on *base_query* so repeated calls with the same
        query continue where they left off even if the input value has been
        replaced by a previous cycle step.
        """
        if base_query != self._cycle_base:
            self._cycle_base = base_query
            self._cycle_matches = self._compute_matches(base_query)
            self._cycle_index = -1
        if not self._cycle_matches:
            return None
        self._cycle_index = (self._cycle_index + delta) % len(self._cycle_matches)
        return self._cycle_matches[self._cycle_index]


class GenreSuggester(CyclingSuggester):
    """Autocomplete from a mutable genre set; new values extend the set live."""

    def __init__(self, genres: set[str]) -> None:
        super().__init__()
        self._genres = genres

    def _compute_matches(self, value: str) -> list[str]:
        lower = value.casefold()
        prefix = [genre for genre in sorted(self._genres) if genre.casefold().startswith(lower)]
        infix = [genre for genre in sorted(self._genres) if lower in genre.casefold() and not genre.casefold().startswith(lower)]
        return prefix + infix


class UrnSuggester(CyclingSuggester):
    """Autocomplete from a name→URN mapping; suggests 'Name [ urn ]' format.

    The display wrapper is stripped back to the raw URN by on_input_submitted
    in FieldTable.
    """

    def __init__(self, name_to_urn: dict[str, str]) -> None:
        super().__init__()
        self._entries = sorted(name_to_urn.items())

    def _compute_matches(self, value: str) -> list[str]:
        lower = value.casefold()
        prefix = [f"{name} [ {urn} ]" for name, urn in self._entries if name.casefold().startswith(lower)]
        infix = [f"{name} [ {urn} ]" for name, urn in self._entries if lower in name.casefold() and not name.casefold().startswith(lower)]
        return prefix + infix


class ImageFrame(Widget):
    """
    Central panel that renders the current item's thumbnail.
    Uses the Kitty graphics protocol when available, falls back to half-blocks.
    Image fetching happens in a worker thread so the UI stays responsive.
    """

    DEFAULT_CSS = """
    ImageFrame {
        border: round $primary;
        height: 1fr;
    }
    ImageFrame > TIImage {
        width: 1fr;
        height: 1fr;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_url: str = ""

    def compose(self) -> ComposeResult:
        yield TIImage()

    def update_photo(self, thumbnail_url: str) -> None:
        if thumbnail_url == self._current_url:
            return
        self._current_url = thumbnail_url
        self.run_worker(
            lambda: self._fetch_and_set(thumbnail_url),
            exclusive=True,
            thread=True,
        )

    def _fetch_and_set(self, url: str) -> None:
        """Runs in a thread: fetch image, then hand PIL image to the main thread."""
        pil_image = fetch_image(url)
        if pil_image is None or url != self._current_url:
            return
        self.app.call_from_thread(self._apply_image, pil_image)

    def _apply_image(self, pil_image) -> None:
        self.query_one(TIImage).image = pil_image


class RatingSelector(Static, can_focus=True):
    """
    Inline enum picker for the rating field.
    Left/right cycles through RATING_OPTIONS; Enter confirms, Escape cancels.
    """

    BINDINGS = [
        Binding("left", "prev_option", show=False),
        Binding("right", "next_option", show=False),
        Binding("enter", "confirm", show=False),
    ]

    DEFAULT_CSS = """
    RatingSelector {
        margin: 0 0 0 14;
        height: 1;
    }
    """

    def __init__(self, current_value: str, **kwargs) -> None:
        try:
            self._option_index = RATING_OPTIONS.index(current_value)
        except ValueError:
            self._option_index = 0
        super().__init__(self._build_markup(), **kwargs)

    def action_prev_option(self) -> None:
        self._option_index = max(0, self._option_index - 1)
        self.update(self._build_markup())

    def action_next_option(self) -> None:
        self._option_index = min(len(RATING_OPTIONS) - 1, self._option_index + 1)
        self.update(self._build_markup())

    def action_confirm(self) -> None:
        self.post_message(SaveRequested(value=RATING_OPTIONS[self._option_index]))

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.post_message(EditCancelled())
            event.stop()

    def _build_markup(self) -> str:
        parts = []
        for option_index, option in enumerate(RATING_OPTIONS):
            if option_index == self._option_index:
                parts.append(f"[reverse]{escape(option)}[/reverse]")
            else:
                parts.append(f"[dim]{escape(option)}[/dim]")
        return "  ".join(parts)


class FieldRow(Static):
    """One row in the FieldTable: shows a field name and its current value."""

    DEFAULT_CSS = """
    FieldRow {
        height: 1;
        padding: 0 1;
    }
    FieldRow.selected {
        background: $accent 20%;
    }
    """

    def __init__(self, field_name: str, display_fn: Callable[[str], str] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._field_name = field_name
        self._value: str = ""
        self._display_fn = display_fn

    def refresh_value(self, value: str, selected: bool) -> None:
        self._value = value
        self._render_label()
        self.set_class(selected, "selected")

    def on_mount(self) -> None:
        self._render_label()

    def _render_label(self) -> None:
        if not self._value:
            display_value = "[dim](empty)[/dim]"
        elif self._display_fn is not None:
            display_value = escape(self._display_fn(self._value))
        else:
            display_value = escape(self._value)
        name_markup = f"[bold cyan]{self._field_name:>12}[/bold cyan]"
        self.update(f"{name_markup}  {display_value}")


class FieldTable(Widget, can_focus=True):
    """
    Generic editable field table for any row type with get_field/set_field.
    Rows are composed once; row changes update values in place.
    An Input or other editor widget is dynamically mounted/removed for edit mode.

    Subclass and override _make_editor to provide field-specific editors.
    """

    BINDINGS = [
        Binding("up", "move_up", "Previous field", show=False),
        Binding("down", "move_down", "Next field", show=False),
        Binding("enter", "begin_edit", "Edit", show=False),
    ]

    DEFAULT_CSS = """
    FieldTable {
        border: round $secondary;
        padding: 0 1;
        height: auto;
    }
    FieldTable:focus {
        border: round $accent;
    }
    #edit-input {
        margin: 0 0 0 14;
        height: 3;
    }
    """

    def __init__(
        self,
        editable_columns: list[str],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._editable_columns = editable_columns
        self._row = None
        self._field_index: int = 0
        self._edit_mode: bool = False
        # Tracks the query that started the current cycle session so repeated
        # up/down presses continue from where they left off.
        self._cycle_base_query: str | None = None
        # True while we're programmatically replacing inp.value during cycling
        # so on_input_changed doesn't clear _cycle_base_query.
        self._cycling_in_progress: bool = False

    # ------------------------------------------------------------------
    # Composition — rows are created once and never removed
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        for field_index, field_name in enumerate(self._editable_columns):
            yield FieldRow(
                field_name=field_name,
                id=f"{_FIELD_ROW_ID_PREFIX}{field_index}",
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_row(self, row) -> None:
        self._row = row
        self._edit_mode = False
        self._sync_all_rows()

    def update_field_index(self, index: int) -> None:
        self._field_index = index
        if not self._edit_mode:
            self._sync_selection()

    def enter_edit_mode(self) -> None:
        if self._row is None or self._edit_mode:
            return
        self._edit_mode = True

        field_name = self._editable_columns[self._field_index]
        current_value = self._row.get_field(field_name)
        selected_row = self.query_one(f"#{_FIELD_ROW_ID_PREFIX}{self._field_index}", FieldRow)
        selected_row.display = False

        editor = self._make_editor(field_name, current_value)
        self.mount(editor, after=selected_row)
        editor.focus()

    def exit_edit_mode(self) -> None:
        if not self._edit_mode:
            return
        self._edit_mode = False

        for widget in self.query(f"#{_EDIT_INPUT_ID}, #{_RATING_SELECTOR_ID}"):
            widget.remove()

        selected_row = self.query_one(f"#{_FIELD_ROW_ID_PREFIX}{self._field_index}", FieldRow)
        selected_row.display = True

        if self._row is not None:
            selected_row.refresh_value(
                value=self._row.get_field(self._editable_columns[self._field_index]),
                selected=True,
            )

        self.focus()

    # ------------------------------------------------------------------
    # Override in subclasses for field-specific editors
    # ------------------------------------------------------------------

    def _make_editor(self, field_name: str, current_value: str) -> Widget:
        return Input(value=current_value, placeholder=f"Edit {field_name}…", id=_EDIT_INPUT_ID)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sync_all_rows(self) -> None:
        """Refresh every row's value and selection state from the current row."""
        if self._row is None:
            return
        for field_index, field_name in enumerate(self._editable_columns):
            row = self.query_one(f"#{_FIELD_ROW_ID_PREFIX}{field_index}", FieldRow)
            row.display = True
            row.refresh_value(
                value=self._row.get_field(field_name),
                selected=(field_index == self._field_index),
            )

    def _sync_selection(self) -> None:
        """Update only the selected/deselected highlight without changing values."""
        for field_index in range(len(self._editable_columns)):
            row = self.query_one(f"#{_FIELD_ROW_ID_PREFIX}{field_index}", FieldRow)
            row.set_class(field_index == self._field_index, "selected")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_move_up(self) -> None:
        if self._edit_mode:
            return
        self._field_index = max(0, self._field_index - 1)
        self._sync_selection()
        self.post_message(FieldChanged())

    def action_move_down(self) -> None:
        if self._edit_mode:
            return
        self._field_index = min(len(self._editable_columns) - 1, self._field_index + 1)
        self._sync_selection()
        self.post_message(FieldChanged())

    def action_begin_edit(self) -> None:
        if not self._edit_mode:
            self.post_message(EditRequested())

    # ------------------------------------------------------------------
    # Editor event handlers
    # ------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value
        # Strip display wrapper inserted by UrnSuggester: "Name [ urn ]" → "urn"
        if value.endswith("]") and " [ " in value:
            value = value.split(" [ ", 1)[1].rstrip("]").strip()
        self.post_message(SaveRequested(value=value))
        event.stop()

    def on_input_changed(self, event: Input.Changed) -> None:
        # Programmatic replacements during cycling must not reset the cycle.
        if self._cycling_in_progress:
            self._cycling_in_progress = False
        else:
            self._cycle_base_query = None

    def on_key(self, event) -> None:
        if event.key == "escape" and self._edit_mode:
            self.post_message(EditCancelled())
            event.stop()
            return
        if self._edit_mode and event.key in ("up", "down"):
            try:
                inp = self.query_one(f"#{_EDIT_INPUT_ID}", Input)
            except Exception:
                return
            if isinstance(inp.suggester, CyclingSuggester) and inp.value:
                if self._cycle_base_query is None:
                    self._cycle_base_query = inp.value
                delta = -1 if event.key == "up" else 1
                new_suggestion = inp.suggester.cycle(self._cycle_base_query, delta)
                if new_suggestion is not None:
                    self._cycling_in_progress = True
                    inp.value = new_suggestion
                    inp.cursor_position = len(new_suggestion)
                event.stop()
