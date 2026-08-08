from typing import Iterator

from mirror.commons.urn import format_mirror_urn, is_mirror_urn, parse_mirror_urn
from mirror.data.things import binomial_types


def _iter_binomial_targets_from_photo_metadata(db) -> Iterator[dict]:
    photo_metadata_table = db.photo_metadata_table()
    for photo_md in photo_metadata_table.list():
        target = photo_md.target
        if not is_mirror_urn(target):
            continue
        parsed = parse_mirror_urn(target)
        if parsed["type"] not in binomial_types():
            continue
        yield parsed


def list_photo_binomials(db) -> Iterator[str]:
    """Read distinct species binomials from the photo metadata table.

    Photos are tagged with `genus-species` labels."""

    binomials = set()
    for parsed in _iter_binomial_targets_from_photo_metadata(db):
        parsed_id = parsed["id"]
        # 'unknown' marks an unidentified subject, not a species
        if parsed_id == "unknown":
            continue
        if parsed_id not in binomials:
            yield parsed_id.replace("-", " ").capitalize()
            binomials.add(parsed_id)


def binomial_urn_map(db) -> dict[str, str]:
    """Map every normalised binomial in the photo metadata table to its URN.

    Build this once per reader. Scanning the table per binomial is quadratic."""

    urns: dict[str, str] = {}
    for parsed in _iter_binomial_targets_from_photo_metadata(db):
        parsed_id = parsed["id"]
        if parsed_id in urns:
            continue
        urns[parsed_id] = format_mirror_urn({"type": parsed["type"], "id": parsed_id})
    return urns


def normalise_binomial(binomial: str) -> str:
    """Normalise a binomial to the hyphenated, lower-case form used in URNs."""
    return binomial.replace(" ", "-").lower()
