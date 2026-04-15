"""Preset filter predicates for VideoPane."""

from collections.abc import Callable

from .parser import VideoRow

PRESET_FILTERS: list[tuple[str, Callable[[VideoRow], bool]]] = [
    ("Has subjects", lambda video: bool(video.subjects.strip())),
    ("No subjects", lambda video: not video.subjects.strip()),
    ("Has description", lambda video: bool(video.description.strip())),
    ("No description", lambda video: not video.description.strip()),
    ("Has rating", lambda video: bool(video.rating.strip())),
    ("No rating", lambda video: not video.rating.strip()),
]
