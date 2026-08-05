"""Compute first-seen timestamps for animals from photo EXIF and video metadata."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Iterator

import ffmpeg

from mirror.commons.constants import DATE_FORMAT
from mirror.data.things import animal_types
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase

# concurrent ffprobe subprocesses; each probe is subprocess-bound, not CPU-bound
PROBE_WORKERS = 12


def animal_type_filters(column: str) -> str:
    """SQL disjunction matching any animal-typed subject URN in the given column."""
    return " OR ".join(
        f"{column}.target LIKE 'urn:ró:{animal_type}:%'" for animal_type in animal_types()
    )


def animal_photo_first_seen_query() -> str:
    """Earliest EXIF capture time per photographed animal subject."""
    return f"""
SELECT
    pmt.target,
    MIN(exif.created_at) AS earliest
FROM photo_metadata_table pmt
JOIN phashes ON pmt.phash = phashes.phash
JOIN exif ON phashes.fpath = exif.fpath
WHERE pmt.relation = 'subject'
  AND ({animal_type_filters("pmt")})
  AND exif.created_at IS NOT NULL
GROUP BY pmt.target
"""


def animal_video_subject_query() -> str:
    """Every video subject; the capture time is read from the file, not the database."""
    return f"""
SELECT vmt.fpath, vmt.target
FROM video_metadata_table vmt
WHERE vmt.relation = 'subject'
  AND ({animal_type_filters("vmt")})
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
    for raw_urn, created_at in db.conn.execute(animal_photo_first_seen_query()).fetchall():
        _merge_earliest(earliest, raw_urn, _exif_created_at_to_unix_ms(created_at))


def _probe_capture_times(fpaths: list[str]) -> dict[str, int | None]:
    """Capture time per video path. Each probe spawns ffprobe, so run them concurrently."""
    if not fpaths:
        return {}
    with ThreadPoolExecutor(max_workers=PROBE_WORKERS) as pool:
        return dict(zip(fpaths, pool.map(_video_capture_unix_ms, fpaths), strict=True))


def _read_video_first_seen(db: SqliteDatabase, earliest: dict[str, int]) -> None:
    """Merge earliest capture times for filmed animal subjects."""
    rows = db.conn.execute(animal_video_subject_query()).fetchall()
    captured = _probe_capture_times(sorted({fpath for fpath, _ in rows}))

    for fpath, raw_urn in rows:
        when_ms = captured[fpath]
        if when_ms is not None:
            _merge_earliest(earliest, raw_urn, when_ms)


class AnimalFirstSeenReader:
    """Emits  urn:ró:<animal>:<id>  first_seen  <unix-ms>  for every animal that
    appears as a photo or video subject, using the earliest capture time across
    both. Photos use EXIF; videos use the container creation_time (mtime fallback)."""

    @staticmethod
    def read(db: SqliteDatabase) -> Iterator[SemanticTriple]:
        earliest: dict[str, int] = {}

        _read_photo_first_seen(db, earliest)
        _read_video_first_seen(db, earliest)

        for canonical_urn, when_ms in earliest.items():
            yield SemanticTriple(canonical_urn, "first_seen", str(when_ms))
