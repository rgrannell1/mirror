"""Photo rows and icons → semantic triples for publish."""

from typing import TYPE_CHECKING, Iterator

from mirror.commons.utils import deterministic_hash_str, short_cdn_url
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase


class PhotoTriples:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for photo in db.photo_data_table().list():
            source = f"urn:ró:photo:{deterministic_hash_str(photo.fpath)}"

            yield SemanticTriple(source, "album_id", photo.album_id)
            yield SemanticTriple(source, "thumbnail_url", short_cdn_url(photo.thumbnail_url))
            yield SemanticTriple(source, "png_url", short_cdn_url(photo.png_url))
            yield SemanticTriple(source, "mid_image_lossy_url", short_cdn_url(photo.mid_image_lossy_url))
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

COUNTRY_COVER_QUERY = """
WITH country_photos AS (
    SELECT
        ph.fpath,
        vps.rating,
        vps.genre
    FROM photos p
    JOIN phashes ph ON p.fpath = ph.fpath
    JOIN view_photo_metadata_summary vps ON ph.fpath = vps.fpath
    JOIN view_album_data vad ON p.dpath = vad.dpath
    WHERE vad.flags IS NOT NULL AND vad.flags != '' AND vad.flags NOT LIKE '%,%'
),
ranked AS (
    SELECT
        fpath,
        ROW_NUMBER() OVER (
            ORDER BY
                CASE WHEN lower(genre) LIKE '%landscape%' THEN 0 ELSE 1 END ASC,
                rating DESC
        ) AS rank
    FROM country_photos
)
SELECT fpath, 'country' AS listing_type FROM ranked WHERE rank = 1
"""


class ListingCoverReader:
    """Selects one representative cover photo per top-level listing type.

    For subject-based types (bird, mammal, etc.) the highest-rated photo is
    chosen.  For place and country the best landscape photo is preferred,
    falling back to highest-rated if no landscape exists.

    Emits triples:  urn:ró:photo:<id>  cover  urn:ró:listing:<type>
    """

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for fpath, listing_type in db.conn.execute(LISTING_COVER_QUERY).fetchall():
            photo_urn = f"urn:ró:photo:{deterministic_hash_str(fpath)}"
            listing_urn = f"urn:ró:listing:{listing_type}"
            yield SemanticTriple(photo_urn, "cover", listing_urn)

        for fpath, listing_type in db.conn.execute(COUNTRY_COVER_QUERY).fetchall():
            photo_urn = f"urn:ró:photo:{deterministic_hash_str(fpath)}"
            listing_urn = f"urn:ró:listing:{listing_type}"
            yield SemanticTriple(photo_urn, "cover", listing_urn)


class PhotosCountryReader:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        # TODO I don't get this logic.

        photos = list(db.photo_data_table().list())

        for album in db.album_data_view().list():
            if len(album.flags) != 1:
                continue

            for photo in photos:
                if photo.album_id == album.id:
                    source = f"urn:ró:photo:{deterministic_hash_str(photo.fpath)}"
                    country = album.flags[0]
                    country_id = country.lower().replace(" ", "-")
                    country_urn = f"urn:ró:country:{country_id}"

                    yield SemanticTriple(source, "country", country_urn)
