"""Which photos each selective rendition role is generated for.

Most roles are produced for every photo. A few (social_card, banner) are only
produced for a subset of source files, so we don't generate, upload and store a
big rendition for all 1400+ photos.
"""

from mirror.commons.constants import BANNER_SOURCE_FILES


def _is_cover_source(fpath: str) -> bool:
    """Cover photos are marked with a +cover suffix in their filename."""
    return "+cover" in fpath


def _is_banner_source(fpath: str) -> bool:
    """Banner heroes are an explicit allow-list (renaming would change the URN)."""
    return fpath in BANNER_SOURCE_FILES


# Roles generated only for a subset of source files: role -> predicate on fpath.
# A role absent here is generated for every photo.
SELECTIVE_ROLE_FILTERS = {
    "social_card": _is_cover_source,
    "banner": _is_banner_source,
}


def is_role_skipped(role: str, fpath: str) -> bool:
    """Whether this selective role should be skipped for this source file."""
    selector = SELECTIVE_ROLE_FILTERS.get(role)
    return selector is not None and not selector(fpath)
