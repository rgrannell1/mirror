from datetime import datetime
from typing import Iterator, Optional

import markdown
from mirror.config import PHOTOS_URL
from mirror.data.types import SemanticTriple
from mirror.utils import deterministic_hash_str


class ExifReader:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        camera_models = set()

        for exif in db.exif_table().list():
            source = f"urn:ró:photo:{deterministic_hash_str(exif.fpath)}"

            parts = exif.created_at.split(" ") if exif.created_at else ""
            date = parts[0].replace(":", "/")
            created_at = f"{date} {parts[1]}"

            yield SemanticTriple(
                source=source,
                relation="created_at",
                target=created_at,
            )

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
                'album_id',
                video.album_id,)

            yield SemanticTriple(
                source,
                'description',
                video.description,)

            yield SemanticTriple(
                source,
                'video_url_unscaled',
                VideosReader.short_cdn_url(video.video_url_unscaled),)

            yield SemanticTriple(
                source,
                'video_url_1080p',
                VideosReader.short_cdn_url(video.video_url_1080p),)

            yield SemanticTriple(
                source,
                'video_url_720p',
                VideosReader.short_cdn_url(video.video_url_720p),)

            yield SemanticTriple(
                source,
                'video_url_480p',
                VideosReader.short_cdn_url(video.video_url_480p),)

            yield SemanticTriple(
                source,
                'poster_url',
                VideosReader.short_cdn_url(video.poster_url),)


class AlbumTriples:
    @classmethod
    def short_cdn_url(cls, url: Optional[str]) -> str:
        return url.replace(PHOTOS_URL, "") if url else ""

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for album in db.album_data_view().list():
            min_date = datetime.strptime(album.min_date, "%Y:%m:%d %H:%M:%S")
            max_date = datetime.strptime(album.max_date, "%Y:%m:%d %H:%M:%S")

            description = markdown.markdown(album.description) if album.description else ""

            source = f"urn:ró:album:{album.id}"
            yield SemanticTriple(source, 'name', album.name)
            yield SemanticTriple(source, 'photos_count', album.photos_count)
            yield SemanticTriple(source, 'videos_count', album.videos_count)
            yield SemanticTriple(source, 'min_date', str(int(min_date.timestamp() * 1000)))
            yield SemanticTriple(source, 'max_date', str(int(max_date.timestamp() * 1000)))
            yield SemanticTriple(source, 'thumbnail_url', AlbumTriples.short_cdn_url(album.thumbnail_url))
            yield SemanticTriple(source, 'mosaic', album.mosaic_colours)
            yield SemanticTriple(source, 'flags', album.flags)
            yield SemanticTriple(source, 'description', description)


class PhotoTriples:
    @classmethod
    def short_cdn_url(cls, url: Optional[str]) -> str:
        return url.replace(PHOTOS_URL, "") if url else ""

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for photo in db.photo_data_table().list():
            source = f"urn:ró:photo:{deterministic_hash_str(photo.fpath)}"

            yield SemanticTriple(source, 'album_id', photo.album_id)
            yield SemanticTriple(source, 'thumbnail_url', PhotoTriples.short_cdn_url(photo.thumbnail_url))
            yield SemanticTriple(source, 'mosaic_colours', photo.mosaic_colours)
            yield SemanticTriple(source, 'full_image', PhotoTriples.short_cdn_url(photo.full_image))
            yield SemanticTriple(source, 'created_at', str(int(photo.get_ctime().timestamp() * 1000)))
