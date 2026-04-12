# Named preset filters available in the command palette.
# Each entry is (display_label, predicate).
from typing import Callable

from labeller.parser import PhotoRow

_ANIMAL_PREFIXES = ("urn:ró:bird:", "urn:ró:mammal:")


def _animal_without_context(photo: PhotoRow) -> bool:
    """True if any subject is a bird/mammal URN that lacks a ?context= qualifier."""
    for subject in photo.subjects.split():
        if any(subject.startswith(prefix) for prefix in _ANIMAL_PREFIXES):
            if "?context=" not in subject:
                return True
    return False


PRESET_FILTERS: list[tuple[str, Callable[[PhotoRow], bool]]] = [
    ("Has description", lambda photo: bool(photo.description.strip())),
    ("Has subjects", lambda photo: bool(photo.subjects.strip())),
    ("No subjects", lambda photo: not photo.subjects.strip()),
    ("Unknown subject", lambda photo: ":unknown" in photo.subjects),
    ("No place", lambda photo: not photo.places.strip()),
    ("Has cover", lambda photo: bool(photo.cover.strip())),
    ("Animal without context", _animal_without_context),
    ("Wildlife no subject", lambda photo: photo.genre == "Wildlife" and not photo.subjects.strip()),
]
