"""Photo rows and icons → semantic triples for publish."""

from typing import TYPE_CHECKING, Iterator

from mirror.commons.utils import deterministic_hash_str, short_cdn_url
from mirror.data.things import place_feature_to_places
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase


class PhotoTriples:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for photo in db.photo_data_table().list():
            if photo.album_id is None:
                continue

            source = f"urn:ró:photo:{deterministic_hash_str(photo.fpath)}"

            yield SemanticTriple(source, "album_id", photo.album_id)
            yield SemanticTriple(source, "thumbnail_url", short_cdn_url(photo.thumbnail_url))
            yield SemanticTriple(source, "png_url", short_cdn_url(photo.png_url))
            yield SemanticTriple(source, "mid_image_lossy_url", short_cdn_url(photo.mid_image_lossy_url))
            yield SemanticTriple(source, "preview_jpeg_url", short_cdn_url(photo.preview_jpeg_url))
            yield SemanticTriple(source, "mosaic_colours", photo.mosaic_colours)
            yield SemanticTriple(source, "full_image", short_cdn_url(photo.full_image))
            yield SemanticTriple(source, "created_at", str(int(photo.get_ctime().timestamp() * 1000)))

        for fpath, grey_value in db.photo_icon_table().list():
            source = f"urn:ró:photo:{deterministic_hash_str(fpath)}"
            yield SemanticTriple(source, "contrasting_grey", grey_value)


class AlbumBannerReader:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        rows = db.conn.execute("""
            SELECT fpath, album_id, mosaic_banner_url
            FROM (
                SELECT
                    vps.fpath,
                    vpd.album_id,
                    ep.url AS mosaic_banner_url,
                    ROW_NUMBER() OVER (
                        PARTITION BY vpd.album_id
                        ORDER BY
                            vps.rating DESC,
                            CASE
                                WHEN lower(vps.genre) LIKE '%landscape%' THEN 0
                                WHEN lower(vps.genre) LIKE '%cityscape%' THEN 1
                                WHEN lower(vps.genre) LIKE '%wildlife%'  THEN 2
                                ELSE 3
                            END ASC
                    ) AS rank
                FROM view_photo_metadata_summary vps
                JOIN view_photo_data vpd ON vps.fpath = vpd.fpath
                JOIN encoded_photos ep ON vps.fpath = ep.fpath AND ep.role = 'mosaic_banner'
                WHERE vpd.album_id IS NOT NULL
            )
            WHERE rank = 1
        """).fetchall()

        for fpath, album_id, mosaic_banner_url in rows:
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
                CASE WHEN listing_type = 'place' AND lower(genre) LIKE '%landscape%' THEN 0 ELSE 1 END ASC,
                rating DESC
        ) AS rank
    FROM categorised
    WHERE listing_type IN ('bird', 'mammal', 'reptile', 'amphibian', 'fish', 'insect', 'plane', 'train', 'car', 'place')
)
SELECT fpath, listing_type FROM ranked WHERE rank = 1
"""


class ListingCoverReader:
    """Selects one representative cover photo per top-level listing type.

    For subject-based types (bird, mammal, etc.) the highest-rated photo is
    chosen.  For places the best landscape photo is preferred,
    falling back to highest-rated if no landscape exists.

    Emits triples:  urn:ró:photo:<id>  cover  urn:ró:listing:<type>
    """

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for fpath, listing_type in db.conn.execute(LISTING_COVER_QUERY).fetchall():
            photo_urn = f"urn:ró:photo:{deterministic_hash_str(fpath)}"
            listing_urn = f"urn:ró:listing:{listing_type}"
            yield SemanticTriple(photo_urn, "cover", listing_urn)


THING_COVER_QUERY = """
WITH all_candidates AS (
    -- Explicit cover assignments (is_explicit=1) and subject/location photos (is_explicit=0)
    SELECT
        ph.fpath,
        pmt.target AS thing_urn,
        vps.rating,
        CASE WHEN pmt.relation = 'cover' THEN 1 ELSE 0 END AS is_explicit
    FROM photo_metadata_table pmt
    JOIN phashes ph ON pmt.phash = ph.phash
    JOIN view_photo_metadata_summary vps ON ph.fpath = vps.fpath
    WHERE pmt.relation IN ('subject', 'location', 'cover')

    UNION ALL

    -- Country photos derived from single-country album flags (flags are now place URNs)
    SELECT
        ph.fpath,
        vad.flags AS thing_urn,
        vps.rating,
        0 AS is_explicit
    FROM photos p
    JOIN phashes ph ON p.fpath = ph.fpath
    JOIN view_photo_metadata_summary vps ON ph.fpath = vps.fpath
    JOIN view_album_data vad ON p.dpath = vad.dpath
    WHERE vad.flags IS NOT NULL AND vad.flags != '' AND vad.flags NOT LIKE '%,%'
),
ranked AS (
    SELECT
        fpath,
        thing_urn,
        ROW_NUMBER() OVER (
            PARTITION BY thing_urn
            ORDER BY is_explicit DESC, rating DESC
        ) AS rank
    FROM all_candidates
)
SELECT fpath, thing_urn FROM ranked WHERE rank = 1
"""


class ThingCoverReader:
    """Selects one cover photo per individual thing (bird, place, country, etc.).

    Explicit cover assignments (relation='cover' in photo_metadata_table) take
    priority; otherwise the highest-rated photo referencing the thing is used.

    Emits triples:  urn:ró:photo:<id>  cover  urn:ró:<type>:<thing-id>
    """

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for fpath, thing_urn in db.conn.execute(THING_COVER_QUERY).fetchall():
            photo_urn = f"urn:ró:photo:{deterministic_hash_str(fpath)}"
            yield SemanticTriple(photo_urn, "cover", thing_urn)


class PlaceFeatureCoverReader:
    """Selects one cover photo per place_feature (castle, beach, volcano, etc.).

    Loads the feature→places mapping from things.toml, queries the DB for all
    photos at those places, then picks the best per feature (landscape preferred,
    then highest-rated).

    Emits triples:  urn:ró:photo:<id>  cover  urn:ró:place_feature:<feature-id>
    """

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        feature_to_places = place_feature_to_places()

        all_place_urns = list({urn for urns in feature_to_places.values() for urn in urns})
        if not all_place_urns:
            return

        placeholders = ",".join("?" * len(all_place_urns))
        rows = db.conn.execute(
            f"""
            SELECT ph.fpath, vps.rating, vps.genre, pmt.target
            FROM photo_metadata_table pmt
            JOIN phashes ph ON pmt.phash = ph.phash
            JOIN view_photo_metadata_summary vps ON ph.fpath = vps.fpath
            WHERE pmt.relation = 'location'
              AND pmt.target IN ({placeholders})
            """,
            all_place_urns,
        ).fetchall()

        place_to_photos: dict[str, list[tuple]] = {}
        for fpath, rating, genre, place_urn in rows:
            place_to_photos.setdefault(place_urn, []).append((fpath, rating.count("⭐") if rating else 0, genre or ""))

        all_candidates: list[tuple] = []
        for feature_urn, place_urns in feature_to_places.items():
            candidates = [photo for urn in place_urns for photo in place_to_photos.get(urn, [])]
            if not candidates:
                continue

            best = sorted(
                candidates,
                key=lambda row: (0 if "landscape" in row[2].lower() else 1, -row[1]),
            )[0]

            all_candidates.append(best)
            photo_urn = f"urn:ró:photo:{deterministic_hash_str(best[0])}"
            yield SemanticTriple(photo_urn, "cover", feature_urn)

        if all_candidates:
            listing_best = sorted(
                all_candidates,
                key=lambda row: (0 if "landscape" in row[2].lower() else 1, -row[1]),
            )[0]
            listing_photo_urn = f"urn:ró:photo:{deterministic_hash_str(listing_best[0])}"
            yield SemanticTriple(listing_photo_urn, "cover", "urn:ró:listing:place_feature")


class PhotosCountryReader:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
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
