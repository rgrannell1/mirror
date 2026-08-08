"""Which photos each selective rendition role is generated for.

Most roles are produced for every photo. A few (social_card, banner) are only
produced for a subset of source files, so we don't generate, upload and store a
big rendition for all 1400+ photos.
"""

from functools import cache

from mirror.commons.config import DATABASE_PATH
from mirror.data.covers import cover_fpaths
from mirror.data.things import banner_fpaths
from mirror.services.database import SqliteDatabase


@cache
def computed_cover_fpaths() -> frozenset[str]:
    """Cover fpaths chosen by the shared selection, memoised for this process.

    The underlying funes cache makes the selection cheap across runs. This memo
    only avoids re-gathering the selection inputs on every per-photo check.
    """
    with SqliteDatabase(DATABASE_PATH) as db:
        return cover_fpaths(db)


def is_cover(fpath: str) -> bool:
    """Is this file an album cover (+cover marker), or a computed thing cover?

    Trip cards reuse album covers, so the +cover marker also covers trips.
    """
    return "+cover" in fpath or fpath in computed_cover_fpaths()


def is_banner_source(fpath: str) -> bool:
    """Banner heroes are an explicit allow-list (renaming would change the URN)."""
    return fpath in banner_fpaths()


# Roles generated only for a subset of source files: role -> predicate on fpath.
# A role absent here is generated for every photo.
SELECTIVE_ROLE_FILTERS = {
    "social_card": is_cover,
    "banner": is_banner_source,
}


def is_role_skipped(role: str, fpath: str) -> bool:
    """Whether this selective role should be skipped for this source file."""
    selector = SELECTIVE_ROLE_FILTERS.get(role)
    return selector is not None and not selector(fpath)
