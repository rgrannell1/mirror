from typing import Iterator, Optional
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
