"""Utility functions and type definitions for the scan workflow"""

from __future__ import annotations

from typing import Iterator, TypedDict

from mirror.commons.constants import MISCELLANEOUS_ALBUM_ID, KnownRelations
from mirror.commons.utils import is_miscellaneous_dpath
from mirror.data.binomials import list_photo_binomials
from mirror.data.geoname import GeonameMetadataReader
from mirror.data.types import SemanticTriple
from mirror.models.exif import ExifReader, PhotoExifData
from mirror.models.media import IMedia
from mirror.models.phash import PhashData, PHashReader
from mirror.models.photo import Photo
from mirror.models.video import Video
from mirror.services.database import SqliteDatabase
from mirror.services.vault import MediaVault

DEFAULT_ALBUMS_MARKDOWN_PATH = "albums.md"
DEFAULT_PHOTOS_MARKDOWN_PATH = "photos.md"
DEFAULT_VIDEOS_MARKDOWN_PATH = "videos.md"


class ScanOpts(TypedDict, total=False):
    albums_markdown_path: str
    photos_markdown_path: str
    videos_markdown_path: str
    force_rescan: bool


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


def scan_binomial_wikidata(db: SqliteDatabase, wikidata_client) -> None:
    """Fetch WikiData entries for species binomials."""
    binomials_wikidata_table = db.binomials_wikidata_id_table()
    wikidata_table = db.wikidata_table()

    for binomial in list_unsaved_binomials(db):
        res = wikidata_client.get_by_binomial(binomial)
        if not res:
            binomials_wikidata_table.add(binomial, None)
            continue

        qid = res["id"]
        binomials_wikidata_table.add(binomial, qid)
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
    """Return binomials that haven't been looked up in WikiData"""

    binomials_wikidata_table = db.binomials_wikidata_id_table()

    # subtract the set of stored binomials from the ones in our photos
    unsaved_binomials = set(list_photo_binomials(db))

    for binomial, _qid in binomials_wikidata_table.list():
        if binomial in unsaved_binomials:
            unsaved_binomials.remove(binomial)

    return iter(unsaved_binomials)
