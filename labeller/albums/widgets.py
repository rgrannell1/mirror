"""Album-specific widgets: AlbumFieldTable."""

from textual.widget import Widget
from textual.widgets import Input

from labeller.widgets import FieldTable, UrnSuggester, _EDIT_INPUT_ID

from .parser import EDITABLE_COLUMNS


class AlbumFieldTable(FieldTable):
    """FieldTable with album-specific editors: UrnSuggester for country."""

    def __init__(self, places: dict[str, str], **kwargs) -> None:
        super().__init__(editable_columns=EDITABLE_COLUMNS, **kwargs)
        self._places = places

    def _make_editor(self, field_name: str, current_value: str) -> Widget:
        if field_name == "country":
            return Input(
                value=current_value,
                placeholder="Edit country…",
                suggester=UrnSuggester(self._places),
                id=_EDIT_INPUT_ID,
            )
        return Input(value=current_value, placeholder=f"Edit {field_name}…", id=_EDIT_INPUT_ID)
