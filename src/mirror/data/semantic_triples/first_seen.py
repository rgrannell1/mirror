"""Compute first-seen timestamps for animals from photo EXIF and video metadata."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Iterator

import ffmpeg

from mirror.commons.constants import DATE_FORMAT
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase

# Animal types whose first-seen timestamps are worth pre-computing.
ANIMAL_TYPES = ("bird", "mammal", "reptile", "amphibian", "fish", "insect")

_PHOTO_TYPE_FILTERS = " OR ".join(f"pmt.target LIKE 'urn:ró:{animal_type}:%'" for animal_type in ANIMAL_TYPES)

# Earliest EXIF capture time per photographed animal subject.
ANIMAL_PHOTO_FIRST_SEEN_QUERY = f"""
SELECT
    pmt.target,
    MIN(exif.created_at) AS earliest
FROM photo_metadata_table pmt
JOIN phashes ON pmt.phash = phashes.phash
JOIN exif ON phashes.fpath = exif.fpath
WHERE pmt.relation = 'subject'
  AND ({_PHOTO_TYPE_FILTERS})
  AND exif.created_at IS NOT NULL
GROUP BY pmt.target
"""

_VIDEO_TYPE_FILTERS = " OR ".join(f"vmt.target LIKE 'urn:ró:{animal_type}:%'" for animal_type in ANIMAL_TYPES)

# Every video subject; the capture time is read from the file, not the database.
ANIMAL_VIDEO_SUBJECT_QUERY = f"""
SELECT vmt.fpath, vmt.target
FROM video_metadata_table vmt
WHERE vmt.relation = 'subject'
  AND ({_VIDEO_TYPE_FILTERS})
"""


def _exif_created_at_to_unix_ms(created_at: str) -> int:
    """Convert an EXIF created_at string (DATE_FORMAT) to a millisecond Unix timestamp."""
    parsed = datetime.strptime(created_at, DATE_FORMAT).replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def _probe_creation_time_ms(fpath: str) -> int | None:
    """Read the container `creation_time` tag as millisecond Unix time, or None."""
    try:
        metadata = ffmpeg.probe(fpath)
    except ffmpeg.Error:
        return None

    tags = metadata.get("format", {}).get("tags", {})
    raw = tags.get("creation_time")
    if not raw:
        return None

    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None

    return int(parsed.timestamp() * 1000)


def _video_capture_unix_ms(fpath: str) -> int | None:
    """Best-effort capture time for a video, in millisecond Unix time.

    Prefer the container `creation_time` tag — the true recording time — and fall
    back to the file mtime. mtime alone is unreliable: a bulk re-import resets it
    years past the real capture date, so it is only a last resort. Returns None
    when the file is absent and no tag is available."""
    creation_time = _probe_creation_time_ms(fpath)
    if creation_time is not None:
        return creation_time

    if os.path.exists(fpath):
        return int(os.path.getmtime(fpath) * 1000)

    return None


def _strip_qs(urn: str) -> str:
    """Strip any query-string suffix from a URN (e.g. ?context=wild)."""
    return urn.split("?")[0]


def _merge_earliest(earliest: dict[str, int], urn: str, when_ms: int) -> None:
    """Record `when_ms` against the canonical URN if it is the earliest seen so far.

    Different query-string variants (e.g. ?context=wild) collapse to one URN so
    they don't produce duplicate triples with different timestamps."""
    canonical_urn = _strip_qs(urn)
    existing = earliest.get(canonical_urn)
    if existing is None or when_ms < existing:
        earliest[canonical_urn] = when_ms


def _read_photo_first_seen(db: SqliteDatabase, earliest: dict[str, int]) -> None:
    """Merge earliest EXIF capture times for photographed animal subjects."""
    for raw_urn, created_at in db.conn.execute(ANIMAL_PHOTO_FIRST_SEEN_QUERY).fetchall():
        _merge_earliest(earliest, raw_urn, _exif_created_at_to_unix_ms(created_at))


def _read_video_first_seen(db: SqliteDatabase, earliest: dict[str, int]) -> None:
    """Merge earliest capture times for filmed animal subjects."""
    for fpath, raw_urn in db.conn.execute(ANIMAL_VIDEO_SUBJECT_QUERY).fetchall():
        when_ms = _video_capture_unix_ms(fpath)
        if when_ms is not None:
            _merge_earliest(earliest, raw_urn, when_ms)


class AnimalFirstSeenReader:
    """Emits  urn:ró:<animal>:<id>  first_seen  <unix-ms>  for every animal that
    appears as a photo or video subject, using the earliest capture time across
    both. Photos use EXIF; videos use the container creation_time (mtime fallback)."""

    def read(self, db: SqliteDatabase) -> Iterator[SemanticTriple]:
        earliest: dict[str, int] = {}

        _read_photo_first_seen(db, earliest)
        _read_video_first_seen(db, earliest)

        for canonical_urn, when_ms in earliest.items():
            yield SemanticTriple(canonical_urn, "first_seen", str(when_ms))
