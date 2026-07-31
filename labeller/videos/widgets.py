"""Video-specific widgets: VideoFieldTable."""

from functools import partial

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Input

from labeller.widgets import (
    _EDIT_INPUT_ID,
    _FIELD_ROW_ID_PREFIX,
    _RATING_SELECTOR_ID,
    FieldRow,
    FieldTable,
    GenreSuggester,
    RatingSelector,
    UrnSuggester,
    format_urn_list,
)

from .parser import EDITABLE_COLUMNS


class VideoFieldTable(FieldTable):
    """FieldTable with video-specific editors: RatingSelector, GenreSuggester, UrnSuggester."""

    def __init__(
        self,
        genres: set[str],
        places: dict[str, str],
        subjects: dict[str, str],
        **kwargs,
    ) -> None:
        super().__init__(
            editable_columns=EDITABLE_COLUMNS,
            **kwargs,
        )
        self._genres = genres
        self._places = places
        self._subjects = subjects
        self._urn_to_place = {urn: name for name, urn in places.items()}
        self._urn_to_subject = {urn: name for name, urn in subjects.items()}

    def compose(self) -> ComposeResult:
        for field_index, field_name in enumerate(EDITABLE_COLUMNS):
            if field_name == "places":
                display_fn = partial(format_urn_list, self._urn_to_place)
            elif field_name == "subjects":
                display_fn = partial(format_urn_list, self._urn_to_subject)
            else:
                display_fn = None
            yield FieldRow(
                field_name=field_name,
                display_fn=display_fn,
                id=f"{_FIELD_ROW_ID_PREFIX}{field_index}",
            )

    def _make_editor(self, field_name: str, current_value: str) -> Widget:
        if field_name == "rating":
            return RatingSelector(current_value=current_value, id=_RATING_SELECTOR_ID)
        if field_name == "genre":
            return Input(
                value=current_value,
                placeholder="Edit genre…",
                suggester=GenreSuggester(self._genres),
                id=_EDIT_INPUT_ID,
            )
        if field_name == "places":
            return Input(
                value=current_value,
                placeholder="Edit places…",
                suggester=UrnSuggester(self._places),
                id=_EDIT_INPUT_ID,
            )
        if field_name == "subjects":
            return Input(
                value=current_value,
                placeholder="Edit subjects…",
                suggester=UrnSuggester(self._subjects),
                id=_EDIT_INPUT_ID,
            )
        return Input(value=current_value, placeholder=f"Edit {field_name}…", id=_EDIT_INPUT_ID)
