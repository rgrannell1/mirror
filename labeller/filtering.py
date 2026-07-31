"""Shared command-palette helpers for the pane filter providers."""

from collections.abc import Callable, Iterable, Iterator

from textual.command import Hit

# One palette row: (label, command to run, help text)
FilterEntry = tuple[str, Callable[[], None], str]


def match_field(field: str, value: str, row) -> bool:
    """True when the row's named field equals value."""
    return getattr(row, field) == value


def iter_hits(matcher, query: str, entries: Iterable[FilterEntry]) -> Iterator[Hit]:
    """Yield a palette Hit for each entry whose label matches the query."""
    for label, command, help_text in entries:
        score = matcher.match(label)
        if score > 0 or not query:
            yield Hit(
                score=score,
                match_display=matcher.highlight(label),
                command=command,
                help=help_text,
            )
