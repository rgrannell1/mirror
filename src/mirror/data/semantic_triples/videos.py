"""Video rows → semantic triples for publish."""

from typing import TYPE_CHECKING, Iterator

from mirror.commons.utils import deterministic_hash_str, short_cdn_url
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase


class VideosReader:
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
                short_cdn_url(video.video_url_unscaled),
            )

            yield SemanticTriple(
                source,
                "video_url_1080p",
                short_cdn_url(video.video_url_1080p),
            )

            yield SemanticTriple(
                source,
                "video_url_720p",
                short_cdn_url(video.video_url_720p),
            )

            yield SemanticTriple(
                source,
                "video_url_480p",
                short_cdn_url(video.video_url_480p),
            )

            yield SemanticTriple(
                source,
                "poster_url",
                short_cdn_url(video.poster_url),
            )
