"""Photo-specific widgets: GenreSuggester, UrnSuggester, PhotoFieldTable."""

from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Input

from labeller.things import load_urn_suggestions
from labeller.widgets import FieldTable, RatingSelector, _EDIT_INPUT_ID, _RATING_SELECTOR_ID, RATING_OPTIONS

from .parser import EDITABLE_COLUMNS

_URN_FIELDS = frozenset({"places", "subjects"})
_PLACE_PREFIXES = ("urn:ró:place:", "urn:ró:country:")


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


class UrnSuggester(Suggester):
    """Autocomplete for places/subjects: match by name or URN prefix.

    Suggestions are displayed as 'Name [ urn ]'.  The input handler strips
    the display wrapper on submit so only the bare URN is stored.

    field_name controls which URNs are offered:
      'places'   → only place/country URNs
      'subjects' → everything except place/country URNs
    """

    def __init__(self, field_name: str) -> None:
        super().__init__(use_cache=False, case_sensitive=False)
        all_suggestions = load_urn_suggestions()
        if field_name == "places":
            self._suggestions = [
                (name, urn) for name, urn in all_suggestions
                if any(urn.startswith(prefix) for prefix in _PLACE_PREFIXES)
            ]
        else:
            self._suggestions = [
                (name, urn) for name, urn in all_suggestions
                if not any(urn.startswith(prefix) for prefix in _PLACE_PREFIXES)
            ]

    async def get_suggestion(self, value: str) -> str | None:
        if not value:
            return None
        for name, urn in self._suggestions:
            if value in name.casefold() or urn.casefold().startswith(value):
                return f"{name} [ {urn} ]"
        return None


class PhotoFieldTable(FieldTable):
    """FieldTable with photo-specific editors: RatingSelector, GenreSuggester, UrnSuggester."""

    def __init__(self, genres: set[str], **kwargs) -> None:
        super().__init__(
            editable_columns=EDITABLE_COLUMNS,
            urn_fields=_URN_FIELDS,
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
        if field_name in _URN_FIELDS:
            return Input(
                value=current_value,
                placeholder="Name or urn:ró:…",
                suggester=UrnSuggester(field_name),
                id=_EDIT_INPUT_ID,
            )
        return Input(value=current_value, placeholder=f"Edit {field_name}…", id=_EDIT_INPUT_ID)
