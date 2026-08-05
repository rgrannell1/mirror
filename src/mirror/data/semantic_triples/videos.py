"""Video rows → semantic triples for publish."""

from typing import TYPE_CHECKING, Iterator, Set

import markdown

from mirror.commons.utils import deterministic_hash_str, short_cdn_url
from mirror.data.photo_relations import parse_style
from mirror.data.things import rating_urns_by_name
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase

_style_names_seen: Set[str] = set()


def map_video_metadata(db: "SqliteDatabase") -> dict[str, list]:
    """Build a lookup of fpath → video metadata rows"""
    metadata_by_fpath: dict[str, list] = {}

    query = "select fpath, relation, target from video_metadata_table"
    for fpath, relation, target in db.conn.execute(query):
        metadata_by_fpath.setdefault(fpath, []).append((relation, target))

    return metadata_by_fpath


def video_url_triples(video, source: str) -> Iterator[SemanticTriple]:
    """CDN url triples for one video row, skipping missing renditions."""
    urls = {
        "video_url_unscaled": short_cdn_url(video.video_url_unscaled),
        "video_url_1080p": short_cdn_url(video.video_url_1080p),
        "video_url_720p": short_cdn_url(video.video_url_720p),
        "video_url_480p": short_cdn_url(video.video_url_480p),
        "poster_url": short_cdn_url(video.poster_url),
    }

    for relation, url in urls.items():
        if url:
            yield SemanticTriple(source, relation, url)


def video_style_triples(source: str, target: str) -> Iterator[SemanticTriple]:
    """Style triples for one video, naming each style the first time it is seen."""
    style_urn = parse_style(target)

    if target not in _style_names_seen:
        _style_names_seen.add(target)
        yield SemanticTriple(style_urn, "name", target)

    yield SemanticTriple(source, "style", style_urn)


def video_metadata_triples(source: str, rows: list) -> Iterator[SemanticTriple]:
    """Metadata triples (description, rating, style, links) for one video."""
    for relation, target in rows:
        if relation == "summary":
            yield SemanticTriple(source, "description", markdown.markdown(target))
        elif relation == "rating":
            rating_urn = rating_urns_by_name().get(target)
            if rating_urn is not None:
                yield SemanticTriple(source, "rating", rating_urn)
        elif relation == "style":
            yield from video_style_triples(source, target)
        elif relation in {"location", "subject", "cover"}:
            yield SemanticTriple(source, relation, target)


class VideosReader:
    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        metadata_by_fpath = map_video_metadata(db)

        for video in db.video_data_table().list():
            source = f"urn:ró:video:{deterministic_hash_str(video.fpath)}"

            yield SemanticTriple(source, "album_id", video.album_id)
            yield from video_url_triples(video, source)
            yield from video_metadata_triples(source, metadata_by_fpath.get(video.fpath, []))
