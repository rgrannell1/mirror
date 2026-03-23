from typing import Iterator

from mirror.commons.constants import BINOMIAL_TYPE
from mirror.commons.urn import format_mirror_urn, is_mirror_urn, parse_mirror_urn


def _iter_binomial_targets_from_photo_metadata(db) -> Iterator[dict]:
    photo_metadata_table = db.photo_metadata_table()
    for photo_md in photo_metadata_table.list():
        target = photo_md.target
        if not is_mirror_urn(target):
            continue
        parsed = parse_mirror_urn(target)
        if parsed["type"] not in BINOMIAL_TYPE:
            continue
        yield parsed


def list_photo_binomials(db) -> Iterator[str]:
    """Read distinct species binomials from the photo metadata table. Photos are tagged with `genus-species` labels"""

    binomials = set()
    for parsed in _iter_binomial_targets_from_photo_metadata(db):
        parsed_id = parsed["id"]
        if parsed_id not in binomials:
            yield parsed_id.replace("-", " ").capitalize()
            binomials.add(parsed_id)


def binomial_to_urn(db, binomial: str) -> str | None:
    """Convert a binomial to a URN, if it exists in the database"""

    normalised = binomial.replace(" ", "-").lower()
    for parsed in _iter_binomial_targets_from_photo_metadata(db):
        if parsed["id"] == normalised:
            return format_mirror_urn(
                {
                    "type": parsed["type"],
                    "id": normalised,
                }
            )

    return None
