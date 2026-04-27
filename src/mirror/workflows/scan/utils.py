"""Utility functions and type definitions for the scan workflow"""

from __future__ import annotations

from typing import Iterator, TypedDict

from mirror.commons.constants import KnownRelations
from mirror.data.geoname import GeonameMetadataReader
from mirror.data.types import SemanticTriple
from mirror.models.exif import ExifReader, PhotoExifData
from mirror.models.media import IMedia
from mirror.models.phash import PhashData, PHashReader
from mirror.models.photo import Photo
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
        covers = list(album.covers())

        if not covers:
            raise ValueError(f"Album {album.dpath} has no cover photo (a photo with '+cover' in its name)")

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

    from mirror.data.binomials import list_photo_binomials

    binomials_wikidata_table = db.binomials_wikidata_id_table()

    # subtract the set of stored binomials from the ones in our photos
    unsaved_binomials = set(list_photo_binomials(db))

    for binomial, _qid in binomials_wikidata_table.list():
        if binomial in unsaved_binomials:
            unsaved_binomials.remove(binomial)

    return iter(unsaved_binomials)
