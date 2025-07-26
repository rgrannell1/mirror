

from typing import Iterator
from src.constants import BINOMIAL_TYPE
from src.things import Things


def list_photo_binomials(db) -> Iterator[str]:
    """Read distinct species binomials from the photo metadata table. Photos are tagged with `genus-species` labels"""

    photo_metadata_table = db.photo_metadata_table()
    binomials = set()

    for photo_md in photo_metadata_table.list():
        target = photo_md.target
        if not Things.is_urn(target):
            continue

        parsed = Things.from_urn(target)
        if parsed["type"] not in BINOMIAL_TYPE:
            continue

        id = parsed["id"]
        if not id in binomials:
            yield id.replace('-', ' ').capitalize()
            binomials.add(id)


def find_common_name(db) -> Iterator[str]: # type: ignore
    """Read distinct common names from the photo metadata table."""

    wikidata_table = db.wikidata_table()
    binomials = set(list_photo_binomials(db))
