"""Video rows → semantic triples for publish."""

import markdown
from typing import TYPE_CHECKING, Iterator

from mirror.commons.utils import deterministic_hash_str, short_cdn_url
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase

_RATING_MAP = {"⭐": "0", "⭐⭐": "1", "⭐⭐⭐": "2", "⭐⭐⭐⭐": "3", "⭐⭐⭐⭐⭐": "4"}


class VideosReader:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        # Build a lookup of fpath → video metadata rows
        metadata_by_fpath: dict[str, list] = {}
        for row in db.conn.execute(
            "select fpath, relation, target from video_metadata_table"
        ):
            fpath, relation, target = row
            metadata_by_fpath.setdefault(fpath, []).append((relation, target))

        for video in db.video_data_table().list():
            source = f"urn:ró:video:{deterministic_hash_str(video.fpath)}"

            yield SemanticTriple(source, "album_id", video.album_id)

            video_url_unscaled = short_cdn_url(video.video_url_unscaled)
            if video_url_unscaled:
                yield SemanticTriple(source, "video_url_unscaled", video_url_unscaled)

            video_url_1080p = short_cdn_url(video.video_url_1080p)
            if video_url_1080p:
                yield SemanticTriple(source, "video_url_1080p", video_url_1080p)

            video_url_720p = short_cdn_url(video.video_url_720p)
            if video_url_720p:
                yield SemanticTriple(source, "video_url_720p", video_url_720p)

            video_url_480p = short_cdn_url(video.video_url_480p)
            if video_url_480p:
                yield SemanticTriple(source, "video_url_480p", video_url_480p)

            poster_url = short_cdn_url(video.poster_url)
            if poster_url:
                yield SemanticTriple(source, "poster_url", poster_url)

            for relation, target in metadata_by_fpath.get(video.fpath, []):
                if relation == "summary":
                    yield SemanticTriple(source, "description", markdown.markdown(target))
                elif relation == "rating":
                    rating_index = _RATING_MAP.get(target)
                    if rating_index is not None:
                        yield SemanticTriple(source, "rating", f"urn:ró:rating:{rating_index}")
                elif relation in ("style", "location", "subject", "cover"):
                    yield SemanticTriple(source, relation, target)
