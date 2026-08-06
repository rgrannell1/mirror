"""Publish one listing entity per subject type present in the photo data.

The site builds its listings index from these triples; no type registry
exists in the frontend. Labels derive from things.toml section headers.
"""

from typing import TYPE_CHECKING, Iterator

from mirror.data.things import (
    binomial_types,
    listing_labels,
    listing_type_config,
    unlisted_types,
)
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase

# urn:ró: is 7 chars; substr(target, 8) strips the prefix leaving '<type>:<id>'
SUBJECT_TYPES_QUERY = """
SELECT DISTINCT substr(target, 8, instr(substr(target, 8), ':') - 1) AS noun
FROM photo_metadata_table
WHERE relation = 'subject' AND target LIKE 'urn:ró:%'
"""

# any located photo gives the place and place-feature listings content
HAS_LOCATION_QUERY = """
SELECT EXISTS (
    SELECT 1 FROM photo_metadata_table
    WHERE relation = 'location' AND target LIKE 'urn:ró:place:%'
)
"""


def listed_types(db: "SqliteDatabase") -> set[str]:
    """Distinct subject URN nouns, plus the place types when located photos exist."""
    nouns = {row[0] for row in db.conn.execute(SUBJECT_TYPES_QUERY) if row[0]}

    has_location = db.conn.execute(HAS_LOCATION_QUERY).fetchone()[0]
    if has_location:
        nouns.update({"place", "place_feature", "country"})
    return nouns


def flag_value(entry: dict, key: str) -> str:
    """A site behaviour flag as a published string; flags default to true."""
    return "true" if entry.get(key, True) else "false"


def listing_entity_triples(types: set[str]) -> Iterator[SemanticTriple]:
    """Name, binomial, and behaviour-flag triples for each listed type.

    Types with neither a things.toml section nor a listing_types entry are skipped."""
    labels = listing_labels()
    binomials = binomial_types()
    config = listing_type_config()

    for noun in sorted(types - unlisted_types()):
        entry = config.get(noun, {})
        label = entry.get("label") or labels.get(noun)
        if label is None:
            continue
        listing_urn = f"urn:ró:listing:{noun}"
        yield SemanticTriple(listing_urn, "name", label)
        if noun in binomials:
            yield SemanticTriple(listing_urn, "binomial", "true")
        yield SemanticTriple(listing_urn, "listable", flag_value(entry, "listable"))
        yield SemanticTriple(listing_urn, "browseable", flag_value(entry, "browseable"))


class ListingEntityReader:
    """Emits:  urn:ró:listing:<type>  name        <plural label>
    urn:ró:listing:<type>  binomial    true          (binomial types only)
    urn:ró:listing:<type>  listable    true|false
    urn:ró:listing:<type>  browseable  true|false
    """

    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        yield from listing_entity_triples(listed_types(db))
