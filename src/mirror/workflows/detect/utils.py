"""Find photo-subject pairs that need bounding-box detection."""

import os
from collections.abc import Iterator

from mirror.commons.constants import DETECTION_CONFIDENCE_THRESHOLD, URN_PREFIX
from mirror.commons.urn import parse_mirror_urn
from mirror.services.database import SqliteDatabase
from mirror.services.detector import build_prompt

# (phash, subject_type, fpath, subject names known for the pair)
type DetectionPair = tuple[str, str, str, tuple[str, ...]]


def resolve_fpath(db: SqliteDatabase, phash: str) -> str | None:
    """Find a file on disk for a phash. Duplicate files share a phash; any copy works."""
    for row in db.conn.execute("select fpath from phashes where phash = ?", (phash,)):
        if os.path.exists(row[0]):
            return row[0]

    return None


def group_subject_urns(db: SqliteDatabase) -> dict[tuple[str, str], set[str]]:
    """Group subject URNs by (phash, subject type), query strings stripped."""
    query = (
        "select distinct phash, target from photo_metadata_table"
        " where relation = 'subject' and target like ?"
    )
    grouped: dict[tuple[str, str], set[str]] = {}

    for phash, target in db.conn.execute(query, (f"{URN_PREFIX}%",)):
        base_urn = target.split("?")[0]
        parsed = parse_mirror_urn(base_urn)
        grouped.setdefault((phash, parsed["type"]), set()).add(base_urn)

    return grouped


def is_scanned(scans: dict, phash: str, subject_type: str, expected_prompt: str) -> bool:
    """Report whether a pair already has a row scanned with the current settings.

    A row is fresh only when both its prompt and threshold match today's. Rows
    from before prompt tracking store '': the prompt they used is unknown, so
    they are always stale.
    """
    if (phash, subject_type) not in scans:
        return False

    stored_prompt, stored_threshold = scans[phash, subject_type]
    if not stored_prompt:
        return False

    fresh_prompt = stored_prompt == expected_prompt
    return fresh_prompt and stored_threshold == DETECTION_CONFIDENCE_THRESHOLD


def list_missing_detections(db: SqliteDatabase, names: dict[str, str]) -> Iterator[DetectionPair]:
    """Yield each pair with no detection row, or a row whose provenance is stale.

    `names` maps subject URN → display name (see thing_names). Stale rows are
    re-scanned and replaced, so prompt or name changes roll out without manual
    deletes. Pairs whose file is missing from disk are skipped.
    """
    scans = db.subject_detections_table().list_scan_provenance()

    for (phash, subject_type), urns in group_subject_urns(db).items():
        subject_names = tuple(sorted(names[urn] for urn in urns if urn in names))
        expected_prompt = build_prompt(subject_type, subject_names)

        if is_scanned(scans, phash, subject_type, expected_prompt):
            continue

        fpath = resolve_fpath(db, phash)
        if not fpath:
            continue

        yield phash, subject_type, fpath, subject_names
