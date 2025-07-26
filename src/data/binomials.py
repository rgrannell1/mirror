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
            yield id.replace("-", " ").capitalize()
            binomials.add(id)


def binomial_to_urn(db, binomial: str) -> str | None:
    """Convert a binomial to a URN, if it exists in the database"""

    photo_metadata_table = db.photo_metadata_table()

    normalised = binomial.replace(" ", "-").lower()
    for photo_md in photo_metadata_table.list():
        target = photo_md.target
        if not Things.is_urn(target):
            continue

        parsed = Things.from_urn(target)
        if parsed["type"] not in BINOMIAL_TYPE:
            continue

        if parsed["id"] == normalised:
            return Things.to_urn(
                {
                    "type": parsed["type"],
                    "id": normalised,
                }
            )

    return None
