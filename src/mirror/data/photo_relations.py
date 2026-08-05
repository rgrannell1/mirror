from typing import TYPE_CHECKING, Iterator, Set

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase

import markdown

from mirror.commons.constants import URN_PREFIX
from mirror.commons.utils import deterministic_hash_str
from mirror.data.things import rating_urns_by_name
from mirror.data.types import SemanticTriple

# Track style names we've already seen to avoid duplicate name triples
style_names: Set[str] = set()

# Photo metadata relations that publish as triples
ALLOWED_PHOTO_RELATIONS = {"summary", "style", "location", "subject", "rating", "wildlife", "cover"}


def parse_rating(rating_str: str) -> str:
    """Convert a configured rating display name to its URN."""
    try:
        return rating_urns_by_name()[rating_str]
    except KeyError as err:
        raise ValueError(f"Unknown rating {rating_str!r}") from err


def parse_style(style_str: str) -> str:
    """
    Parse a style string and convert to a style URN.

    Args:
        style_str: Style name (e.g., "Street Photography")

    Returns:
        URN in format "urn:ró:style:{id}" where id is lowercase with hyphens

    Examples:
        "Street Photography" -> "urn:ró:style:street-photography"
        "Landscape" -> "urn:ró:style:landscape"
    """
    style_id = style_str.lower().replace(" ", "-")
    return f"urn:ró:style:{style_id}"


def photo_relation_triples(row) -> Iterator[SemanticTriple]:
    """Triples for one photo metadata row, converting summaries, ratings, and styles."""
    # not sure this is useable in practice, check it's used...
    photo_id = deterministic_hash_str(row.fpath)

    target = row.target
    if row.relation == "summary":
        target = markdown.markdown(row.target)

    if row.relation == "rating":
        target = parse_rating(row.target)

    if row.relation == "style":
        style_urn = parse_style(row.target)

        # If this is the first time we've seen this style, also yield the style name triple
        if row.target not in style_names:
            style_names.add(row.target)
            yield SemanticTriple(style_urn, "name", row.target)

        target = style_urn

    yield SemanticTriple(f"{URN_PREFIX}photo:{photo_id}", row.relation, target)


class PhotoRelationsReader:
    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for row in db.photo_metadata_table().list():
            if row.relation not in ALLOWED_PHOTO_RELATIONS:
                continue

            yield from photo_relation_triples(row)
