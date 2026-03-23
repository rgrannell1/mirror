"""Scan operations using the zahir workflow engine"""

from __future__ import annotations

from typing import Generator

from zahir import (
    Await,
    Context,
    JobInstance,
    JobOutputEvent,
    spec,
    WorkflowOutputEvent,
)

from mirror.commons.config import DATABASE_PATH, GEONAMES_USERNAME, PHOTO_DIRECTORY
from mirror.workflows.scan.utils import (
    DEFAULT_ALBUMS_MARKDOWN_PATH,
    DEFAULT_PHOTOS_MARKDOWN_PATH,
    ScanOpts,
    list_geonames_from_metadata,
    list_media,
    list_unsaved_binomials,
    list_unsaved_exifs,
    list_unsaved_phashes,
    read_geonames_wikidata_ids,
)
from mirror.services.metadata import MarkdownAlbumMetadataReader, MarkdownTablePhotoMetadataReader
from mirror.data.wikidata import WikidataClient
from mirror.services.database import SqliteDatabase
from mirror.services.vault_sync import VaultIndexSync
from mirror.models.photo import Photo
from mirror.commons.urn import parse_mirror_urn
from mirror.models.video import Video


@spec()
def MediaScan(
    context: Context,
    input: dict,
    dependencies={},
) -> Generator[JobOutputEvent | Await]:
    """Scan media files in the vault and index them in the database"""
    dpath = input.get("dpath", PHOTO_DIRECTORY)

    db = SqliteDatabase(DATABASE_PATH)

    # db.delete_views()  # TEMPORARILY DISABLED: may be causing encoded_videos to disappear

    db.refresh_dependent_views()

    phash_table = db.phashes_table()
    exif_table = db.exif_table()
    photos_table = db.photos_table()
    videos_table = db.videos_table()

    current_fpaths = set()

    # Index all media files
    for entry in list_media(dpath):
        if isinstance(entry, Photo):
            photos_table.add(entry.fpath)
            current_fpaths.add(entry.fpath)
        elif isinstance(entry, Video):
            videos_table.add(entry.fpath)
            current_fpaths.add(entry.fpath)

    # Remove stale photo rows, without touching videos (video deletion is known-broken).
    VaultIndexSync(db).remove_deleted_photos(current_fpaths)

    # Add exif data and phashes
    exif_table.add_many(list_unsaved_exifs(db, dpath))
    phash_table.add_many(list_unsaved_phashes(db, dpath))

    yield JobOutputEvent({"complete": True})


@spec()
def GeonamesScan(
    context: Context,
    input: dict,
    dependencies={},
) -> Generator[JobInstance | JobOutputEvent]:
    """Scan geonames from external API and store in database"""
    if not GEONAMES_USERNAME:
        raise ValueError("GEONAMES_USERNAME environment variable not set")

    db = SqliteDatabase(DATABASE_PATH)
    geoname_table = db.geoname_table()

    from mirror.data.geoname import GeonameClient

    geoname_client = GeonameClient(GEONAMES_USERNAME)

    # Yield individual geoname lookup tasks
    for geoname_urn in list_geonames_from_metadata(db):
        parsed = parse_mirror_urn(geoname_urn)
        gid = parsed["id"]

        if geoname_table.has(gid):
            continue

        res = geoname_client.get_by_id(gid)
        if res:
            geoname_table.add(gid, res)

    yield JobOutputEvent({"complete": True})


@spec()
def WikidataScan(
    context: Context,
    input: dict,
    dependencies={},
) -> Generator[JobOutputEvent]:
    """Scan WikiData for geonames and binomials"""
    db = SqliteDatabase(DATABASE_PATH)
    wikidata_client = WikidataClient()
    wikidata_table = db.wikidata_table()
    binomials_wikidata_table = db.binomials_wikidata_id_table()

    # Process geonames wikidata IDs
    for triple in read_geonames_wikidata_ids(db):
        qid = triple.target

        if wikidata_table.has(qid):
            continue

        res = wikidata_client.get_by_id(qid)
        if not res:
            wikidata_table.add(qid, None)
            continue

        wikidata_table.add(qid, res)

    # Process binomials
    for binomial in list_unsaved_binomials(db):
        res = wikidata_client.get_by_binomial(binomial)
        if not res:
            binomials_wikidata_table.add(binomial, None)
            continue

        qid = res["id"]

        binomials_wikidata_table.add(binomial, qid)
        wikidata_table.add(qid, res)

    yield JobOutputEvent({"complete": True})


@spec()
def ReadAlbums(
    context: Context,
    input: dict,
    dependencies={},
) -> Generator[JobOutputEvent]:
    """Read album metadata from markdown file and store in database"""
    markdown_path = input.get("markdown_path", "albums.md")
    db = SqliteDatabase(DATABASE_PATH)

    album_reader = MarkdownAlbumMetadataReader(markdown_path)

    # Clear existing album metadata
    db.conn.execute("delete from media_metadata_table where src_type = 'album'")

    # Read and store album metadata
    count = 0
    for item in album_reader.list_album_metadata(db):
        db.conn.execute(
            """
            insert or replace into media_metadata_table (src, src_type, relation, target)
            values (?, ?, ?, ?)
        """,
            (item.src, "album", item.relation, item.target),
        )
        count += 1

    db.conn.commit()

    yield JobOutputEvent(
        {
            "count": count,
            "status": "albums_loaded",
        }
    )


@spec()
def ReadPhotos(
    context: Context,
    input: dict,
    dependencies={},
) -> Generator[JobOutputEvent]:
    """Read photo metadata from markdown file and store in database"""
    markdown_path = input.get("markdown_path", "photos.md")
    db = SqliteDatabase(DATABASE_PATH)

    photo_reader = MarkdownTablePhotoMetadataReader(markdown_path)

    # Read and store photo metadata
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

    yield JobOutputEvent(
        {
            "count": count,
            "status": "photos_loaded",
        }
    )


@spec()
def ScanMedia(
    context: Context,
    input: ScanOpts,
    dependencies={},
) -> Generator[Await | WorkflowOutputEvent]:
    """Top-level scan orchestration workflow"""
    dpath = PHOTO_DIRECTORY

    # First scan all media files
    yield MediaScan({"dpath": dpath}, {})

    # Read metadata from markdown files
    yield Await(
        ReadAlbums(
            {
                "markdown_path": input.get("albums_markdown_path") or DEFAULT_ALBUMS_MARKDOWN_PATH,
            },
            {},
        )
    )
    yield Await(
        ReadPhotos(
            {
                "markdown_path": input.get("photos_markdown_path") or DEFAULT_PHOTOS_MARKDOWN_PATH,
            },
            {},
        )
    )

    # Then scan external data sources
    yield WikidataScan({}, {})
