from typing import Iterator, Set

import markdown

from mirror.constants import URN_PREFIX
from mirror.data.types import SemanticTriple
from mirror.utils import deterministic_hash_str

# Track style names we've already seen to avoid duplicate name triples
style_names: Set[str] = set()


def parse_rating(rating_str: str) -> str:
    """
    Parse a rating string containing star emojis and convert to a rating URN.

    Args:
        rating_str: String containing star emojis (⭐)

    Returns:
        URN in format "urn:ró:rating:{count}" where count is stars - 1

    Examples:
        "⭐" -> "urn:ró:rating:0"
        "⭐⭐⭐" -> "urn:ró:rating:2"
    """
    star_count = rating_str.count("⭐")
    return f"urn:ró:rating:{star_count - 1}"


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


class PhotoRelationsReader:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        allowed_relations = {"summary", "style", "location", "subject", "rating", "wildlife", "cover"}

        for row in db.photo_metadata_table().list():
            # not sure this is useable in practice, check it's used...
            photo_id = deterministic_hash_str(row.fpath)

            if row.relation not in allowed_relations:
                continue

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
