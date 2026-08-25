"""Scan the media vault and find data absent from the database."""

from __future__ import annotations

from typing import Iterator, TypedDict

from mirror.commons.config import DATABASE_PATH, GEONAMES_USERNAME
from mirror.commons.constants import MISCELLANEOUS_ALBUM_ID, KnownRelations
from mirror.commons.urn import parse_mirror_urn
from mirror.commons.utils import is_miscellaneous_dpath
from mirror.data.binomials import list_photo_binomials
from mirror.data.geoname import GeonameClient, GeonameMetadataReader
from mirror.data.types import SemanticTriple
from mirror.data.wikidata import WikidataClient
from mirror.models.exif import ExifReader, PhotoExifData
from mirror.models.media import IMedia
from mirror.models.phash import PhashData, PHashReader
from mirror.models.photo import Photo
from mirror.models.video import Video
from mirror.services.database import SqliteDatabase
from mirror.services.metadata import (
    MarkdownAlbumMetadataReader,
    MarkdownTablePhotoMetadataReader,
    MarkdownTableVideoMetadataReader,
)
from mirror.services.vault import MediaVault
from mirror.services.vault_sync import VaultIndexSync

DEFAULT_ALBUMS_MARKDOWN_PATH = "albums.md"
DEFAULT_PHOTOS_MARKDOWN_PATH = "photos.md"
DEFAULT_VIDEOS_MARKDOWN_PATH = "videos.md"


class ScanOpts(TypedDict, total=False):
    albums_markdown_path: str
    photos_markdown_path: str
    videos_markdown_path: str
    force_rescan: bool


def index_vault(dpath: str) -> None:
    """Index vault files, EXIF data, and perceptual hashes."""
    with SqliteDatabase(DATABASE_PATH) as db:
        db.refresh_dependent_views()
        current_fpaths = index_media_files(db, dpath)
        VaultIndexSync(db).remove_deleted_photos(current_fpaths)
        db.exif_table().add_many(list_unsaved_exifs(db, dpath))
        db.phashes_table().add_many(list_unsaved_phashes(db, dpath))


def store_geonames() -> None:
    """Fetch and store absent Geonames entries."""
    if not GEONAMES_USERNAME:
        raise ValueError("GEONAMES_USERNAME environment variable not set")
    client = GeonameClient(GEONAMES_USERNAME)
    with SqliteDatabase(DATABASE_PATH) as db:
        table = db.geoname_table()
        for geoname_urn in list_geonames_from_metadata(db):
            geoname_id = parse_mirror_urn(geoname_urn)["id"]
            if not table.has(geoname_id):
                response = client.get_by_id(geoname_id)
                if response:
                    table.add(geoname_id, response)


def store_geoname_wikidata() -> list[str]:
    """Store Wikidata entities for Geonames and return absent binomials."""
    client = WikidataClient()
    with SqliteDatabase(DATABASE_PATH) as db:
        scan_geoname_wikidata(db, client)
        return list(list_unsaved_binomials(db))


def load_album_metadata(markdown_path: str) -> tuple[int, list]:
    """Replace album metadata from one Markdown table."""
    reader = MarkdownAlbumMetadataReader(markdown_path)
    with SqliteDatabase(DATABASE_PATH) as db:
        db.conn.execute("delete from media_metadata_table where src_type = 'album'")
        query = (
            "insert or replace into media_metadata_table"
            " (src, src_type, relation, target) values (?, ?, ?, ?)"
        )
        count = 0
        for item in reader.list_album_metadata(db):
            db.conn.execute(query, (item.src, "album", item.relation, item.target))
            count += 1
        write_miscellaneous_permalinks(db)
        db.conn.commit()
    return count, reader.skipped


def load_photo_metadata(markdown_path: str) -> int:
    """Store photo metadata from one Markdown table."""
    reader = MarkdownTablePhotoMetadataReader(markdown_path)
    count = 0
    with SqliteDatabase(DATABASE_PATH) as db:
        for metadata in reader.read_photo_metadata(db):
            fpath = db.encoded_photos_table().fpath_from_url(metadata.url)
            phash = db.phashes_table().phash_from_fpath(fpath) if fpath else None
            if phash:
                db.photo_metadata_table().add_summary(phash, metadata)
                count += 1
    return count


def load_video_metadata(markdown_path: str) -> int:
    """Store video metadata from one Markdown table."""
    reader = MarkdownTableVideoMetadataReader(markdown_path)
    count = 0
    with SqliteDatabase(DATABASE_PATH) as db:
        for metadata in reader.read_video_metadata(db):
            fpath = db.encoded_photos_table().fpath_from_url(metadata.url)
            if fpath:
                db.video_metadata_table().add_summary(fpath, metadata)
                count += 1
    return count


def list_media(dpath: str) -> Iterator[IMedia]:
    """Return all media from the vault directories"""

    for album in MediaVault(dpath).albums():
        # hidden miscellaneous albums have no album page, so need no cover
        if is_miscellaneous_dpath(album.dpath):
            yield from album.media()
            continue

        covers = list(album.covers())

        if not covers:
            message = f"Album {album.dpath} has no cover photo (a photo with '+cover' in its name)"
            raise ValueError(message)

        if len(covers) > 1:
            raise ValueError(f"Album {album.dpath} has multiple cover photos, using the first one")

        yield from album.media()


def list_unsaved_exifs(db: SqliteDatabase, dpath: str) -> Iterator[PhotoExifData]:
    """Return exif data for all photos not in the database"""

    exif_table = db.exif_table()

    for media in list_media(dpath):
        if not Photo.is_a(media.fpath):
            continue

        if not exif_table.has(media.fpath):
            data = ExifReader.exif(media.fpath)  # type: ignore
            if data is not None:
                yield data


def list_unsaved_phashes(db: SqliteDatabase, dpath: str) -> Iterator[PhashData]:
    """Return phashes for all photos not already stored in the database"""

    phash_table = db.phashes_table()

    for album in MediaVault(dpath).albums():
        for media in album.media():
            if not Photo.is_a(media.fpath):
                continue

            if not phash_table.has(media.fpath):
                yield PHashReader.phash(media.fpath)


def index_media_files(db: SqliteDatabase, dpath: str) -> set[str]:
    """Index photos and videos under dpath; return the fpaths seen."""
    photos_table = db.photos_table()
    videos_table = db.videos_table()

    current_fpaths = set()
    for entry in list_media(dpath):
        if isinstance(entry, Photo):
            photos_table.add(entry.fpath)
            current_fpaths.add(entry.fpath)
        elif isinstance(entry, Video):
            videos_table.add(entry.fpath)
            current_fpaths.add(entry.fpath)

    return current_fpaths


def scan_geoname_wikidata(db: SqliteDatabase, wikidata_client) -> None:
    """Fetch WikiData entries referenced by geonames."""
    wikidata_table = db.wikidata_table()

    for triple in read_geonames_wikidata_ids(db):
        qid = triple.target
        if wikidata_table.has(qid):
            continue

        res = wikidata_client.get_by_id(qid)
        if not res:
            wikidata_table.add(qid, None)
            continue

        wikidata_table.add(qid, res)


def write_miscellaneous_permalinks(db: SqliteDatabase) -> None:
    """Assign the shared hidden album id to every Miscellaneous dpath."""

    dpath_query = "select distinct dpath from photos union select distinct dpath from videos"
    rows = db.conn.execute(dpath_query)

    insert_query = """
    insert or replace into media_metadata_table (src, src_type, relation, target)
    values (?, 'album', 'permalink', ?)
    """

    for (dpath,) in rows:
        if is_miscellaneous_dpath(dpath):
            db.conn.execute(insert_query, (dpath, MISCELLANEOUS_ALBUM_ID))


def list_geonames_from_metadata(db: SqliteDatabase) -> Iterator[str]:
    """Return all geoname URNs from the photo metadata"""

    photo_metadata_table = db.photo_metadata_table()
    geonames = {md.target for md in photo_metadata_table.list_by_target_type("geoname")}
    return iter(geonames)


def read_geonames_wikidata_ids(db: SqliteDatabase) -> Iterator[SemanticTriple]:
    """Read wikidata IDs from geonames metadata"""

    for triple in GeonameMetadataReader().read(db):
        if triple.relation == KnownRelations.WIKIDATA:
            yield triple


def list_unsaved_binomials(db: SqliteDatabase) -> Iterator[str]:
    """Return binomials with no stored WikiData QID.

    Failed lookups store a null QID; those binomials stay in this list, so a
    later scan retries them (e.g. after a transient outage)."""

    binomials_wikidata_table = db.binomials_wikidata_id_table()

    # subtract the resolved binomials from the ones in our photos. Only a Q-item
    # id counts as resolved: old lookups stored lexeme sense ids (L…-S1)
    unsaved_binomials = set(list_photo_binomials(db))

    for binomial, qid in binomials_wikidata_table.list():
        if qid and qid.startswith("Q") and binomial in unsaved_binomials:
            unsaved_binomials.remove(binomial)

    return iter(unsaved_binomials)
