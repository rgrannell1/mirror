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
