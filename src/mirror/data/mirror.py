from datetime import datetime
from typing import TYPE_CHECKING, Iterator, Optional

import markdown  # type: ignore
from mirror.commons.config import PHOTOS_URL
from mirror.data.types import SemanticTriple
from mirror.commons.utils import deterministic_hash_str
from mirror.commons.dates import date_range

if TYPE_CHECKING:
    # Only imported for static type checking (avoids runtime import cycles / overhead).
    from mirror.services.database import SqliteDatabase


class ExifReader:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        camera_models = set()

        for exif in db.exif_table().list():
            source = f"urn:ró:photo:{deterministic_hash_str(exif.fpath)}"

            yield SemanticTriple(
                source=source,
                relation="f_stop",
                target=exif.f_stop,
            )

            yield SemanticTriple(
                source=source,
                relation="focal_length",
                target=exif.focal_length,
            )

            if exif.model:
                camera_urn = f"urn:ró:camera:{exif.model.lower().replace(' ', '-')}"

                if camera_urn not in camera_models:
                    camera_models.add(camera_urn)
                    yield SemanticTriple(camera_urn, "name", exif.model)

                yield SemanticTriple(
                    source=source,
                    relation="model",
                    target=camera_urn,
                )

            yield SemanticTriple(
                source=source,
                relation="exposure_time",
                target=exif.exposure_time,
            )

            yield SemanticTriple(
                source=source,
                relation="iso",
                target=exif.iso,
            )

            if exif.width and exif.height:
                yield SemanticTriple(
                    source=source,
                    relation="width",
                    target=exif.width,
                )

                yield SemanticTriple(
                    source=source,
                    relation="height",
                    target=exif.height,
                )


class VideosReader:
    @classmethod
    def short_cdn_url(cls, url: Optional[str]) -> str:
        return url.replace(PHOTOS_URL, "") if url else ""

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for video in db.video_data_table().list():
            source = f"urn:ró:video:{deterministic_hash_str(video.fpath)}"

            yield SemanticTriple(
                source,
                "album_id",
                video.album_id,
            )

            yield SemanticTriple(
                source,
                "description",
                video.description,
            )

            yield SemanticTriple(
                source,
                "video_url_unscaled",
                VideosReader.short_cdn_url(video.video_url_unscaled),
            )

            yield SemanticTriple(
                source,
                "video_url_1080p",
                VideosReader.short_cdn_url(video.video_url_1080p),
            )

            yield SemanticTriple(
                source,
                "video_url_720p",
                VideosReader.short_cdn_url(video.video_url_720p),
            )

            yield SemanticTriple(
                source,
                "video_url_480p",
                VideosReader.short_cdn_url(video.video_url_480p),
            )

            yield SemanticTriple(
                source,
                "poster_url",
                VideosReader.short_cdn_url(video.poster_url),
            )


class AlbumTriples:
    @classmethod
    def short_cdn_url(cls, url: Optional[str]) -> str:
        return url.replace(PHOTOS_URL, "") if url else ""

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for album in db.album_data_view().list():
            min_dt: datetime | None = None
            max_dt: datetime | None = None

            if album.min_date is not None and album.max_date is not None:
                min_dt = datetime.strptime(album.min_date, "%Y:%m:%d %H:%M:%S")
                max_dt = datetime.strptime(album.max_date, "%Y:%m:%d %H:%M:%S")
            else:
                # Fallback: derive min/max from photo ctime when EXIF-derived album dates
                # are missing. This prevents publishing albums with partial triples.
                min_dt = None
                max_dt = None
                for photo in db.photo_data_table().list():
                    if photo.album_id != album.id:
                        continue
                    ctime = photo.get_ctime()
                    if min_dt is None or ctime < min_dt:
                        min_dt = ctime
                    if max_dt is None or ctime > max_dt:
                        max_dt = ctime

                # If we still can't compute dates, skip this album.
                if min_dt is None or max_dt is None:
                    continue

            assert min_dt is not None
            assert max_dt is not None

            description = markdown.markdown(album.description) if album.description else ""

            countries = []
            for flag in album.flags:
                country = flag
                country_id = country.lower().replace(" ", "-")
                countries.append(f"urn:ró:country:{country_id}")

            source = f"urn:ró:album:{album.id}"
            yield SemanticTriple(source, "name", album.name)
            yield SemanticTriple(source, "photos_count", album.photos_count)
            yield SemanticTriple(source, "videos_count", album.videos_count)
            yield SemanticTriple(source, "min_date", str(int(min_dt.timestamp() * 1000)))
            yield SemanticTriple(source, "max_date", str(int(max_dt.timestamp() * 1000)))
            yield SemanticTriple(source, "date_range", date_range(min_dt, max_dt, short=False))
            yield SemanticTriple(source, "short_date_range", date_range(min_dt, max_dt, short=True))
            yield SemanticTriple(source, "thumbnail_url", AlbumTriples.short_cdn_url(album.thumbnail_url))
            yield SemanticTriple(source, "mosaic", album.mosaic_colours)
            for country in countries:
                yield SemanticTriple(source, "country", country)
            yield SemanticTriple(source, "description", description)


class PhotoTriples:
    @classmethod
    def short_cdn_url(cls, url: Optional[str]) -> str:
        return url.replace(PHOTOS_URL, "") if url else ""

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for photo in db.photo_data_table().list():
            source = f"urn:ró:photo:{deterministic_hash_str(photo.fpath)}"

            yield SemanticTriple(source, "album_id", photo.album_id)
            yield SemanticTriple(source, "thumbnail_url", PhotoTriples.short_cdn_url(photo.thumbnail_url))
            yield SemanticTriple(source, "png_url", PhotoTriples.short_cdn_url(photo.png_url))
            yield SemanticTriple(source, "mid_image_lossy_url", PhotoTriples.short_cdn_url(photo.mid_image_lossy_url))
            yield SemanticTriple(source, "mosaic_colours", photo.mosaic_colours)
            yield SemanticTriple(source, "full_image", PhotoTriples.short_cdn_url(photo.full_image))
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
