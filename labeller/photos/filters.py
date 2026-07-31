"""Named preset filters for the photo command palette."""

from itertools import chain
from typing import Callable

from labeller.opener import DB_PATH
from mirror.audit.checks import check_photos_missing_main_image, check_photos_missing_rating
from mirror.services.database.facade import SqliteDatabase

from .parser import PhotoRow

_ANIMAL_PREFIXES = ("urn:ró:bird:", "urn:ró:mammal:")


def _animal_without_context(photo: PhotoRow) -> bool:
    """True if any subject is a bird/mammal URN that lacks a ?context= qualifier."""
    for subject in photo.subjects.split():
        is_animal = any(subject.startswith(prefix) for prefix in _ANIMAL_PREFIXES)
        if is_animal and "?context=" not in subject:
            return True
    return False


def failing_audit_urls() -> set[str]:
    """Thumbnail urls of photos that fail a photo-level audit check."""
    db = SqliteDatabase(str(DB_PATH))
    findings = chain(check_photos_missing_rating(db), check_photos_missing_main_image(db))
    failing_fpaths = {finding.subject for finding in findings}
    return {
        photo.thumbnail_url
        for photo in db.photo_data_table().list()
        if photo.fpath in failing_fpaths and photo.thumbnail_url
    }


def photo_fails_audit(failing_urls: set[str], photo: PhotoRow) -> bool:
    """True when the photo's thumbnail url failed a photo-level audit check."""
    return photo.thumbnail_url in failing_urls


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
