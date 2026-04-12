"""Custom Textual messages for inter-widget communication."""

from textual.message import Message


class PhotoChanged(Message):
    """Posted when the active photo changes."""


class FieldChanged(Message):
    """Posted when the active field cursor moves."""


class EditRequested(Message):
    """Posted when the user presses Enter to edit the current field."""


class SaveRequested(Message):
    """Posted when the user confirms an edit value."""

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value


class EditCancelled(Message):
    """Posted when the user presses Escape to discard an edit."""
