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
