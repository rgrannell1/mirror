"""Scan operations using the zahir workflow engine"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from zahir import JobContext, await_all

from mirror.commons.config import DATABASE_PATH, GEONAMES_USERNAME, PHOTO_DIRECTORY
from mirror.commons.urn import parse_mirror_urn
from mirror.data.geoname import GeonameClient
from mirror.data.wikidata import WikidataClient
from mirror.services.database import SqliteDatabase
from mirror.services.metadata import (
    MarkdownAlbumMetadataReader,
    MarkdownTablePhotoMetadataReader,
    MarkdownTableVideoMetadataReader,
)
from mirror.services.vault_sync import VaultIndexSync
from mirror.workflows.scan.utils import (
    DEFAULT_ALBUMS_MARKDOWN_PATH,
    DEFAULT_PHOTOS_MARKDOWN_PATH,
    DEFAULT_VIDEOS_MARKDOWN_PATH,
    ScanOpts,
    index_media_files,
    list_geonames_from_metadata,
    list_unsaved_exifs,
    list_unsaved_phashes,
    scan_binomial_wikidata,
    scan_geoname_wikidata,
    write_miscellaneous_permalinks,
)


def media_scan(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Scan media files in the vault and index them in the database"""
    dpath = input.get("dpath", PHOTO_DIRECTORY)

    with SqliteDatabase(DATABASE_PATH) as db:
        db.refresh_dependent_views()

        current_fpaths = index_media_files(db, dpath)
        VaultIndexSync(db).remove_deleted_photos(current_fpaths)

        db.exif_table().add_many(list_unsaved_exifs(db, dpath))
        db.phashes_table().add_many(list_unsaved_phashes(db, dpath))

    return {"complete": True}
    yield


def geonames_scan(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Scan geonames from external API and store in database"""
    if not GEONAMES_USERNAME:
        raise ValueError("GEONAMES_USERNAME environment variable not set")

    geoname_client = GeonameClient(GEONAMES_USERNAME)

    with SqliteDatabase(DATABASE_PATH) as db:
        geoname_table = db.geoname_table()

        for geoname_urn in list_geonames_from_metadata(db):
            parsed = parse_mirror_urn(geoname_urn)
            gid = parsed["id"]

            if geoname_table.has(gid):
                continue

            res = geoname_client.get_by_id(gid)
            if res:
                geoname_table.add(gid, res)

    return {"complete": True}
    yield


def wikidata_scan(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Scan WikiData for geonames and binomials"""
    wikidata_client = WikidataClient()

    with SqliteDatabase(DATABASE_PATH) as db:
        scan_geoname_wikidata(db, wikidata_client)
        scan_binomial_wikidata(db, wikidata_client)

    return {"complete": True}
    yield


def read_albums(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Read album metadata from markdown file and store in database"""
    markdown_path = input.get("markdown_path", "albums.md")
    album_reader = MarkdownAlbumMetadataReader(markdown_path)

    with SqliteDatabase(DATABASE_PATH) as db:
        db.conn.execute("delete from media_metadata_table where src_type = 'album'")

        insert_query = (
            "insert or replace into media_metadata_table"
            " (src, src_type, relation, target) values (?, ?, ?, ?)"
        )

        count = 0
        for item in album_reader.list_album_metadata(db):
            db.conn.execute(insert_query, (item.src, "album", item.relation, item.target))
            count += 1

        write_miscellaneous_permalinks(db)
        db.conn.commit()

    return {"count": count, "status": "albums_loaded"}
    yield


def read_photos(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Read photo metadata from markdown file and store in database"""
    markdown_path = input.get("markdown_path", "photos.md")
    photo_reader = MarkdownTablePhotoMetadataReader(markdown_path)

    with SqliteDatabase(DATABASE_PATH) as db:
        count = 0
        for md in photo_reader.read_photo_metadata(db):
            fpath = db.encoded_photos_table().fpath_from_url(md.url)
            if not fpath:
                continue

            phash = db.phashes_table().phash_from_fpath(fpath)
            if not phash:
                continue

            db.photo_metadata_table().add_summary(phash, md)
            count += 1

    return {"count": count, "status": "photos_loaded"}
    yield


def read_videos(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Read video metadata from markdown file and store in database"""
    markdown_path = input.get("markdown_path", "videos.md")
    video_reader = MarkdownTableVideoMetadataReader(markdown_path)

    with SqliteDatabase(DATABASE_PATH) as db:
        count = 0
        for md in video_reader.read_video_metadata(db):
            fpath = db.encoded_photos_table().fpath_from_url(md.url)
            if not fpath:
                continue

            db.video_metadata_table().add_summary(fpath, md)
            count += 1

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
