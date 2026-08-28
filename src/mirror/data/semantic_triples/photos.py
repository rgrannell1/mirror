"""Photo rows and icons → semantic triples for publish."""

import json
from typing import TYPE_CHECKING, Iterator, NamedTuple

from mirror.commons.constants import (
    COVER_MIN_SUBJECT_FILL,
    MISCELLANEOUS_ALBUM_ID,
    PERSON_URN_PREFIX,
)
from mirror.commons.urn import parse_mirror_urn
from mirror.commons.utils import deterministic_hash_str, short_cdn_url
from mirror.data.semantic_triples.queries import ALBUM_BANNER_QUERY
from mirror.data.things import genre_cover_priorities, rating_ranks
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase


def photo_row_triples(photo) -> Iterator[SemanticTriple]:
    """Publishable triples for one photo row."""
    source = f"urn:ró:photo:{deterministic_hash_str(photo.fpath)}"
    mid_lossy_url = short_cdn_url(photo.mid_image_lossy_url)
    created_at_ms = str(int(photo.get_ctime().timestamp() * 1000))

    yield SemanticTriple(source, "album_id", photo.album_id)
    yield SemanticTriple(source, "thumbnail_url", short_cdn_url(photo.thumbnail_url))
    yield SemanticTriple(source, "mid_image_lossy_url", mid_lossy_url)
    yield SemanticTriple(source, "preview_jpeg_url", short_cdn_url(photo.preview_jpeg_url))
    yield SemanticTriple(source, "mosaic_colours", photo.mosaic_colours)
    yield SemanticTriple(source, "full_image", short_cdn_url(photo.full_image))
    yield SemanticTriple(source, "created_at", created_at_ms)


class PhotoTriples:
    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for photo in db.photo_data_table().list():
            if photo.album_id is None:
                continue

            yield from photo_row_triples(photo)

        for fpath, grey_value in db.photo_icon_table().list():
            source = f"urn:ró:photo:{deterministic_hash_str(fpath)}"
            yield SemanticTriple(source, "contrasting_grey", grey_value)


class AlbumBannerReader:
    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        genre_order = genre_priority_sql("album", "vps.genre")
        rating_order = rating_rank_sql("vps.rating")
        query = ALBUM_BANNER_QUERY.format(
            genre_order=genre_order,
            rating_order=rating_order,
        )
        rows = db.conn.execute(query).fetchall()

        for fpath, album_id, mosaic_banner_url in rows:
            # miscellaneous is hidden; no album page exists to show a banner on
            if album_id == MISCELLANEOUS_ALBUM_ID:
                continue

            photo_source = f"urn:ró:photo:{deterministic_hash_str(fpath)}"
            album_source = f"urn:ró:album:{album_id}"
            yield SemanticTriple(photo_source, "mosaic_banner", mosaic_banner_url)
            yield SemanticTriple(album_source, "album_banner", photo_source)


LISTING_COVER_QUERY = """
-- urn:ró: is 7 chars; substr(target, 8) strips the prefix leaving '<type>:<id>'
WITH categorised AS (
    SELECT
        ph.fpath,
        vps.rating,
        vps.genre,
        CASE
            WHEN pmt.relation = 'subject'
                THEN substr(pmt.target, 8, instr(substr(pmt.target, 8), ':') - 1)
            WHEN pmt.relation = 'location' AND pmt.target LIKE 'urn:ró:place:%'
                THEN 'place'
        END AS listing_type
    FROM photo_metadata_table pmt
    JOIN phashes ph ON pmt.phash = ph.phash
    JOIN view_photo_metadata_summary vps ON ph.fpath = vps.fpath
),
ranked AS (
    SELECT
        fpath,
        listing_type,
        ROW_NUMBER() OVER (
            PARTITION BY listing_type
            ORDER BY
                CASE WHEN listing_type = 'place' THEN {place_genre_order} ELSE 1 END ASC,
                {rating_order} DESC
        ) AS rank
    FROM categorised
    WHERE listing_type IS NOT NULL
      AND listing_type NOT IN ({excluded})
)
SELECT fpath, listing_type FROM ranked WHERE rank = 1
"""


def genre_priority(scope: str, genre: str) -> int:
    """Return the configured cover priority for a genre string."""
    priorities = genre_cover_priorities(scope)
    matches = [priority for name, priority in priorities.items() if name in genre.lower()]
    return min(matches, default=max(priorities.values(), default=0) + 1)


def genre_priority_sql(scope: str, column: str) -> str:
    """Build a SQL case expression from configured genre priorities."""
    priorities = genre_cover_priorities(scope)
    clauses = [
        f"WHEN lower({column}) LIKE '%{sql_text(name)}%' THEN {priority}"
        for name, priority in priorities.items()
    ]
    default = max(priorities.values(), default=0) + 1
    return f"CASE {' '.join(clauses)} ELSE {default} END"


def rating_rank_sql(column: str) -> str:
    """Build a SQL case expression from configured rating ranks."""
    clauses = [
        f"WHEN {column} = '{sql_text(name)}' THEN {rank}" for name, rank in rating_ranks().items()
    ]
    return f"CASE {' '.join(clauses)} ELSE -1 END"


def sql_text(value: str) -> str:
    """Escape a trusted configuration value for a SQL text literal."""
    return value.replace("'", "''")


THING_COVER_QUERY = """
-- Explicit cover assignments and subject/location photos
SELECT
    ph.fpath,
    ph.phash,
    pmt.target AS thing_urn,
    vps.rating,
    vps.subjects,
    pmt.relation
FROM photo_metadata_table pmt
JOIN phashes ph ON pmt.phash = ph.phash
JOIN view_photo_metadata_summary vps ON ph.fpath = vps.fpath
WHERE pmt.relation IN ('subject', 'location', 'cover')

UNION ALL

-- Country photos derived from single-country album flags (flags are now place URNs)
SELECT
    ph.fpath,
    ph.phash,
    vad.flags AS thing_urn,
    vps.rating,
    vps.subjects,
    'flag' AS relation
FROM photos p
JOIN phashes ph ON p.fpath = ph.fpath
JOIN view_photo_metadata_summary vps ON ph.fpath = vps.fpath
JOIN view_album_data vad ON p.dpath = vad.dpath
WHERE vad.flags IS NOT NULL AND vad.flags != '' AND vad.flags NOT LIKE '%,%'
"""


class CoverCandidate(NamedTuple):
    """One photo competing to be a thing's cover."""

    fpath: str
    is_explicit: int
    rating_rank: int
    # 2 wild, 1 unspecified, 0 captivity (see context_rank)
    wild_rank: int
    single_subject: int
    # photos with a person subject are never covers, unless explicitly assigned
    has_person: int
    # best detection box's share of the image; None when there is no box information
    fill: float | None
    # base subject URN; taxon covers use it as an alphabetical tie-break
    species: str = ""


def best_box_scans(db: "SqliteDatabase") -> dict[tuple[str, str], tuple[int, int]]:
    """(best box volume, recorded image area) per scanned (phash, subject type).

    Empty scans record volume 0. A recorded area of 0 means the row predates
    area tracking.
    """
    db.subject_detections_table()

    scans: dict[tuple[str, str], tuple[int, int]] = {}
    query = "select phash, subject_type, boxes, image_area from subject_detections"
    for phash, subject_type, boxes_json, image_area in db.conn.execute(query):
        boxes = json.loads(boxes_json)
        best = max((box["volume"] for box in boxes), default=0)
        scans[phash, subject_type] = (best, image_area)
    return scans


def photo_areas(db: "SqliteDatabase") -> dict[str, int]:
    """Image pixel area per fpath, where exif has usable dimensions."""
    areas: dict[str, int] = {}
    for fpath, width, height in db.conn.execute("select fpath, width, height from exif"):
        if width and height and str(width).isdigit() and str(height).isdigit():
            areas[fpath] = int(width) * int(height)
    return areas


def candidate_fill(volume: int | None, area: int | None) -> float | None:
    """Best box share of the image; None without box or area information.

    Volume 0 (searched, nothing found) is also None: the design treats a
    subject the detector could not find neutrally, not as too small.
    """
    if not volume or not area:
        return None
    return volume / area


def count_subjects(subjects: str) -> int:
    """Count the subject URNs in a view_photo_metadata_summary subjects cell."""
    if not subjects:
        return 0
    return len(subjects.split(", "))


def has_person_subject(subjects: str) -> bool:
    """Report whether a subjects cell includes a person URN."""
    if not subjects:
        return False
    return any(urn.startswith(PERSON_URN_PREFIX) for urn in subjects.split(", "))


def subject_type_of(thing_urn: str) -> str | None:
    """The subject type of a thing URN, or None when it does not parse."""
    try:
        return parse_mirror_urn(thing_urn)["type"]
    except ValueError:
        return None


def subject_context(thing_urn: str) -> str:
    """The context query value of a subject URN; '' when absent or unparseable."""
    try:
        return parse_mirror_urn(thing_urn).get("context", "")
    except ValueError:
        return ""


def context_rank(context: str) -> int:
    """Rank a photo's subject context: wild beats unspecified beats captivity."""
    if context == "wild":
        return 2
    if context == "captivity":
        return 0
    return 1


def make_candidate(row: tuple, scans: dict, areas: dict) -> tuple[str, CoverCandidate]:
    """Build one cover candidate from a THING_COVER_QUERY row, keyed by base URN.

    Query-string variants (?context=wild) collapse into one group; the context
    becomes a rank factor instead. The recorded scan area is preferred: it was
    measured on the very file the boxes came from. Exif dimensions are the
    fallback for legacy rows.
    """
    fpath, phash, thing_urn, rating, subjects, relation = row
    base_urn = thing_urn.split("?")[0]

    fill = None
    if relation == "subject":
        subject_type = subject_type_of(base_urn)
        scan = scans.get((phash, subject_type))
        if scan:
            volume, recorded_area = scan
            fill = candidate_fill(volume, recorded_area or areas.get(fpath))

    candidate = CoverCandidate(
        fpath=fpath,
        is_explicit=1 if relation == "cover" else 0,
        rating_rank=rating_ranks().get(rating, -1),
        wild_rank=context_rank(subject_context(thing_urn)),
        single_subject=1 if relation == "subject" and count_subjects(subjects) == 1 else 0,
        has_person=1 if has_person_subject(subjects) else 0,
        fill=fill,
    )
    return base_urn, candidate


def cover_sort_key(candidate: CoverCandidate) -> tuple:
    """Order covers: explicit, rating, wild over captive, single-subject, fill."""
    fill = candidate.fill if candidate.fill is not None else 0.0
    return (
        candidate.is_explicit,
        candidate.rating_rank,
        candidate.wild_rank,
        candidate.single_subject,
        fill,
    )


def person_free(candidates: list[CoverCandidate]) -> list[CoverCandidate]:
    """Drop photos with a person subject. Explicit assignments override.

    A hard rule with no fallback: a subject whose every photo has a person in
    it gets no cover triple.
    """
    return [
        candidate for candidate in candidates if not candidate.has_person or candidate.is_explicit
    ]


def eligible_candidates(candidates: list[CoverCandidate]) -> list[CoverCandidate]:
    """Drop photos whose subject is too small, unless that leaves the thing coverless."""
    kept = [
        candidate
        for candidate in candidates
        if candidate.fill is None or candidate.fill >= COVER_MIN_SUBJECT_FILL
    ]
    return kept or candidates


def genre_then_rating(candidate: tuple) -> tuple:
    """Sort a place-cover candidate by configured genre priority, then rating."""
    rank, genre = candidate[1], candidate[2]
    return (genre_priority("place", genre), -rank)


def map_place_photos(db: "SqliteDatabase", place_urns: list[str]) -> dict[str, list[tuple]]:
    """Group candidate photos by their place URN."""
    placeholders = ",".join("?" * len(place_urns))
    rows = db.conn.execute(
        f"""
        SELECT ph.fpath, vps.rating, vps.genre, pmt.target
        FROM photo_metadata_table pmt
        JOIN phashes ph ON pmt.phash = ph.phash
        JOIN view_photo_metadata_summary vps ON ph.fpath = vps.fpath
        WHERE pmt.relation = 'location'
          AND pmt.target IN ({placeholders})
        """,
        place_urns,
    ).fetchall()

    place_to_photos: dict[str, list[tuple]] = {}
    for fpath, rating, genre, place_urn in rows:
        rank = rating_ranks().get(rating, -1)
        place_to_photos.setdefault(place_urn, []).append((fpath, rank, genre or ""))

    return place_to_photos


def feature_cover_candidates(
    feature_to_places: dict[str, list[str]], place_to_photos: dict[str, list[tuple]]
) -> Iterator[tuple[str, tuple]]:
    """Yield (feature_urn, best photo) for each feature with any candidate photos."""
    for feature_urn, place_urns in feature_to_places.items():
        candidates = [photo for urn in place_urns for photo in place_to_photos.get(urn, [])]
        if not candidates:
            continue

        yield feature_urn, min(candidates, key=genre_then_rating)


class PhotosCountryReader:
    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        photos = list(db.photo_data_table().list())

        for album in db.album_data_view().list():
            if len(album.flags) != 1:
                continue

            place_urn = album.flags[0]
            if not place_urn.startswith("urn:"):
                continue

            for photo in photos:
                if photo.album_id == album.id:
                    source = f"urn:ró:photo:{deterministic_hash_str(photo.fpath)}"
                    yield SemanticTriple(source, "country", place_urn)
