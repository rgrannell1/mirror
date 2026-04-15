"""Photo-specific widgets: GenreSuggester, PhotoFieldTable."""

from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Input

from labeller.widgets import FieldTable, RatingSelector, _EDIT_INPUT_ID, _RATING_SELECTOR_ID

from .parser import EDITABLE_COLUMNS


class GenreSuggester(Suggester):
    """Autocomplete from a mutable genre set; new values extend the set live."""

    def __init__(self, genres: set[str]) -> None:
        super().__init__(use_cache=False, case_sensitive=False)
        self._genres = genres

    async def get_suggestion(self, value: str) -> str | None:
        if not value:
            return None
        for genre in sorted(self._genres):
            if genre.casefold().startswith(value):
                return genre
        return None


class PhotoFieldTable(FieldTable):
    """FieldTable with photo-specific editors: RatingSelector and GenreSuggester."""

    def __init__(self, genres: set[str], **kwargs) -> None:
        super().__init__(
            editable_columns=EDITABLE_COLUMNS,
            **kwargs,
        )
        self._genres = genres

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
        return Input(value=current_value, placeholder=f"Edit {field_name}…", id=_EDIT_INPUT_ID)
