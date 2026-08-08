"""Photo rows and icons → semantic triples for publish."""

import json
from typing import TYPE_CHECKING, Iterator, NamedTuple

from mirror.commons.constants import COVER_MIN_SUBJECT_FILL, MISCELLANEOUS_ALBUM_ID
from mirror.commons.urn import parse_mirror_urn
from mirror.commons.utils import deterministic_hash_str, short_cdn_url
from mirror.data.things import (
    genre_cover_priorities,
    place_feature_to_places,
    rating_ranks,
    unlisted_types,
)
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
        query = f"""
            SELECT fpath, album_id, mosaic_banner_url
            FROM (
                SELECT
                    vps.fpath,
                    vpd.album_id,
                    ep.url AS mosaic_banner_url,
                    ROW_NUMBER() OVER (
                        PARTITION BY vpd.album_id
                        ORDER BY
                            {rating_order} DESC,
                            {genre_order} ASC
                    ) AS rank
                FROM view_photo_metadata_summary vps
                JOIN view_photo_data vpd ON vps.fpath = vpd.fpath
                JOIN encoded_photos ep ON vps.fpath = ep.fpath AND ep.role = 'mosaic_banner'
                WHERE vpd.album_id IS NOT NULL
            )
            WHERE rank = 1
        """
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


class ListingCoverReader:
    """Selects one representative cover photo per top-level listing type.

    Subject listings use rating. Place listings first use configured genre priority.

    Emits triples:  urn:ró:photo:<id>  cover  urn:ró:listing:<type>
    """

    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        excluded = tuple(sorted(unlisted_types()))
        query = LISTING_COVER_QUERY.format(
            excluded=",".join("?" for _ in excluded),
            place_genre_order=genre_priority_sql("place", "genre"),
            rating_order=rating_rank_sql("rating"),
        )
        for fpath, listing_type in db.conn.execute(query, excluded).fetchall():
            photo_urn = f"urn:ró:photo:{deterministic_hash_str(fpath)}"
            listing_urn = f"urn:ró:listing:{listing_type}"
            yield SemanticTriple(photo_urn, "cover", listing_urn)


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
    single_subject: int
    # best detection box's share of the image; None when there is no box information
    fill: float | None


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


def subject_type_of(thing_urn: str) -> str | None:
    """The subject type of a thing URN, or None when it does not parse."""
    try:
        return parse_mirror_urn(thing_urn)["type"]
    except ValueError:
        return None


def make_candidate(row: tuple, scans: dict, areas: dict) -> tuple[str, CoverCandidate]:
    """Build one cover candidate from a THING_COVER_QUERY row.

    The recorded scan area is preferred: it was measured on the very file the
    boxes came from. Exif dimensions are the fallback for legacy rows.
    """
    fpath, phash, thing_urn, rating, subjects, relation = row

    fill = None
    if relation == "subject":
        subject_type = subject_type_of(thing_urn)
        scan = scans.get((phash, subject_type))
        if scan:
            volume, recorded_area = scan
            fill = candidate_fill(volume, recorded_area or areas.get(fpath))

    candidate = CoverCandidate(
        fpath=fpath,
        is_explicit=1 if relation == "cover" else 0,
        rating_rank=rating_ranks().get(rating, -1),
        single_subject=1 if relation == "subject" and count_subjects(subjects) == 1 else 0,
        fill=fill,
    )
    return thing_urn, candidate


def cover_sort_key(candidate: CoverCandidate) -> tuple:
    """Order covers: explicit wins, then rating, then single-subject, then fill."""
    fill = candidate.fill if candidate.fill is not None else 0.0
    return (candidate.is_explicit, candidate.rating_rank, candidate.single_subject, fill)


def eligible_candidates(candidates: list[CoverCandidate]) -> list[CoverCandidate]:
    """Drop photos whose subject is too small, unless that leaves the thing coverless."""
    kept = [
        candidate
        for candidate in candidates
        if candidate.fill is None or candidate.fill >= COVER_MIN_SUBJECT_FILL
    ]
    return kept or candidates


class ThingCoverReader:
    """Selects one cover photo per individual thing (bird, place, country, etc.).

    Explicit cover assignments (relation='cover' in photo_metadata_table) take
    priority. Otherwise photos rank by rating, then single-subject labelling,
    then how much of the image the detected subject fills. Photos whose subject
    box is too small are not eligible. Photos with no boxes — never scanned, or
    scanned and nothing found — rank neutrally on fill.

    Emits triples:  urn:ró:photo:<id>  cover  urn:ró:<type>:<thing-id>
    """

    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        scans = best_box_scans(db)
        areas = photo_areas(db)

        groups: dict[str, list[CoverCandidate]] = {}
        for row in db.conn.execute(THING_COVER_QUERY).fetchall():
            thing_urn, candidate = make_candidate(row, scans, areas)
            groups.setdefault(thing_urn, []).append(candidate)

        for thing_urn, group in groups.items():
            best = max(eligible_candidates(group), key=cover_sort_key)
            photo_urn = f"urn:ró:photo:{deterministic_hash_str(best.fpath)}"
            yield SemanticTriple(photo_urn, "cover", thing_urn)


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


class PlaceFeatureCoverReader:
    """Selects one cover photo per place_feature (castle, beach, volcano, etc.).

    Loads the feature→places mapping from things.toml, queries the DB for all
    photos at those places, then applies configured genre priority and rating.

    Emits triples:  urn:ró:photo:<id>  cover  urn:ró:place_feature:<feature-id>
    """

    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        feature_to_places = place_feature_to_places()

        all_place_urns = list({urn for urns in feature_to_places.values() for urn in urns})
        if not all_place_urns:
            return

        place_to_photos = map_place_photos(db, all_place_urns)

        all_candidates: list[tuple] = []
        for feature_urn, best in feature_cover_candidates(feature_to_places, place_to_photos):
            all_candidates.append(best)
            photo_urn = f"urn:ró:photo:{deterministic_hash_str(best[0])}"
            yield SemanticTriple(photo_urn, "cover", feature_urn)

        if all_candidates:
            listing_best = min(all_candidates, key=genre_then_rating)
            listing_photo_urn = f"urn:ró:photo:{deterministic_hash_str(listing_best[0])}"
            yield SemanticTriple(listing_photo_urn, "cover", "urn:ró:listing:place_feature")


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
