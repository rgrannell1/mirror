"""Scan operations using the zahir workflow engine"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from zahir import JobContext, await_all

from mirror.commons.config import PHOTO_DIRECTORY
from mirror.services.media_scan import (
    DEFAULT_ALBUMS_MARKDOWN_PATH,
    DEFAULT_PHOTOS_MARKDOWN_PATH,
    DEFAULT_VIDEOS_MARKDOWN_PATH,
    ScanOpts,
    index_vault,
    load_album_metadata,
    load_photo_metadata,
    load_video_metadata,
    store_geoname_wikidata,
    store_geonames,
)
from mirror.workflows.output import workflow_output


def media_scan(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Scan media files in the vault and index them in the database"""
    dpath = input.get("dpath", PHOTO_DIRECTORY)

    index_vault(dpath)

    return {"complete": True}
    yield


def geonames_scan(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Scan geonames from external API and store in database"""
    store_geonames()

    return {"complete": True}
    yield


def wikidata_scan(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Scan WikiData for geonames and binomials.

    Binomial lookups fan out one rate-limited job per pending name."""
    pending = store_geoname_wikidata()

    yield await_all([ctx.scope.lookup_binomial({"binomial": name}) for name in pending])

    return {"complete": True}
    yield


def read_albums(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Read album metadata from markdown file and store in database"""
    markdown_path = input.get("markdown_path", "albums.md")
    count, skipped = load_album_metadata(markdown_path)
    for skipped_row in skipped:
        yield workflow_output(f"albums.md: skipped {skipped_row}: thumbnail not in database")

    return {"count": count, "status": "albums_loaded"}
    yield


def read_photos(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Read photo metadata from markdown file and store in database"""
    markdown_path = input.get("markdown_path", "photos.md")
    count = load_photo_metadata(markdown_path)

    return {"count": count, "status": "photos_loaded"}
    yield


def read_videos(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Read video metadata from markdown file and store in database"""
    markdown_path = input.get("markdown_path", "videos.md")
    count = load_video_metadata(markdown_path)

    return {"count": count, "status": "videos_loaded"}
    yield


def scan_media(ctx: JobContext, input: ScanOpts) -> Generator[Any, Any, None]:
    """Top-level scan orchestration workflow"""
    dpath = PHOTO_DIRECTORY

    yield ctx.scope.media_scan({"dpath": dpath})

    albums_md = input.get("albums_markdown_path") or DEFAULT_ALBUMS_MARKDOWN_PATH
    photos_md = input.get("photos_markdown_path") or DEFAULT_PHOTOS_MARKDOWN_PATH
    videos_md = input.get("videos_markdown_path") or DEFAULT_VIDEOS_MARKDOWN_PATH

    yield await_all([
        ctx.scope.read_albums({"markdown_path": albums_md}),
        ctx.scope.read_photos({"markdown_path": photos_md}),
        ctx.scope.read_videos({"markdown_path": videos_md}),
    ])

    yield ctx.scope.wikidata_scan({})
    yield ctx.scope.taxonomy_scan({})
