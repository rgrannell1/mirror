"""Compute first-seen timestamps for animals from photo EXIF data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Iterator

from mirror.commons.constants import DATE_FORMAT
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase

# Animal types whose first-seen timestamps are worth pre-computing.
ANIMAL_TYPES = ("bird", "mammal", "reptile", "amphibian", "fish", "insect")

_TYPE_FILTERS = " OR ".join(f"pmt.target LIKE 'urn:ró:{animal_type}:%'" for animal_type in ANIMAL_TYPES)

ANIMAL_FIRST_SEEN_QUERY = f"""
SELECT
    pmt.target,
    MIN(exif.created_at) AS earliest
FROM photo_metadata_table pmt
JOIN phashes ON pmt.phash = phashes.phash
JOIN exif ON phashes.fpath = exif.fpath
WHERE pmt.relation = 'subject'
  AND ({_TYPE_FILTERS})
  AND exif.created_at IS NOT NULL
GROUP BY pmt.target
"""


def _to_unix_ms(created_at: str) -> str:
    """Convert an EXIF created_at string (DATE_FORMAT) to millisecond Unix timestamp string."""
    dt = datetime.strptime(created_at, DATE_FORMAT).replace(tzinfo=timezone.utc)
    return str(int(dt.timestamp() * 1000))


def _strip_qs(urn: str) -> str:
    """Strip any query-string suffix from a URN (e.g. ?context=wild)."""
    return urn.split("?")[0]


class AnimalFirstSeenReader:
    """Emits  urn:ró:<animal>:<id>  first_seen  <unix-ms>  for every animal
    that appears as a photo subject, using the earliest EXIF timestamp."""

    def read(self, db: SqliteDatabase) -> Iterator[SemanticTriple]:
        # Track canonical URNs we've already emitted so that subjects with
        # different query-string variants (e.g. ?context=wild) don't produce
        # duplicate triples with different timestamps.
        earliest: dict[str, str] = {}

        for raw_urn, created_at_str in db.conn.execute(ANIMAL_FIRST_SEEN_QUERY).fetchall():
            canonical_urn = _strip_qs(raw_urn)
            existing = earliest.get(canonical_urn)
            if existing is None or created_at_str < existing:
                earliest[canonical_urn] = created_at_str

        for canonical_urn, created_at_str in earliest.items():
            yield SemanticTriple(canonical_urn, "first_seen", _to_unix_ms(created_at_str))
