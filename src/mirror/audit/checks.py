"""Blocking publication checks: each mirrors a crash or drop condition somewhere in the pipeline
(scan cover/parse aborts, missing phashes, dropped triples, missing renditions).

Album metadata is checked against albums.md through the real reader (the source of truth publish
uses via ReadAlbums), not against media_metadata_table — that table is only a projection of the
last pipeline run and lags edits to albums.md. Rendition checks read live encoded_photos state.
"""

from collections.abc import Iterator
from enum import StrEnum

from mirror.audit.audit_types import Check, Finding
from mirror.audit.shacl import validate_triples
from mirror.commons.config import PHOTO_DIRECTORY
from mirror.services.database import SqliteDatabase
from mirror.services.metadata import (
    MarkdownAlbumMetadataReader,
    MarkdownTablePhotoMetadataReader,
)
from mirror.services.vault import MediaVault
from mirror.workflows.publish.utils import read_triples
from mirror.workflows.scan.utils import (
    DEFAULT_ALBUMS_MARKDOWN_PATH,
    DEFAULT_PHOTOS_MARKDOWN_PATH,
)


class CheckSlug(StrEnum):
    """Stable identifiers for each audit rule; shared by the check and its findings."""

    ALBUM_COVER_INVALID = "album-cover-invalid"
    METADATA_PARSE_ERROR = "metadata-parse-error"
    PHOTO_MISSING_PHASH = "photo-missing-phash"
    ALBUM_MISSING_METADATA = "album-missing-metadata"
    PHOTO_MISSING_RATING = "photo-missing-rating"
    PHOTO_MISSING_MAIN_IMAGE = "photo-missing-main-image"
    ANIMAL_MISSING_NAME = "animal-missing-name"
    TRIPLE_GRAPH_INVALID = "triple-graph-invalid"


def check_albums_cover(db: SqliteDatabase) -> Iterator[Finding]:
    """Each album needs exactly one +cover photo; scan (list_media) hard-aborts otherwise, which
    silently breaks indexing for every album — so this reads the filesystem, not the database."""
    for album in MediaVault(PHOTO_DIRECTORY).albums():
        covers = list(album.covers())
        if not covers:
            detail = "no +cover photo — scan aborts here, so nothing after it indexes or publishes"
            yield Finding(check=CheckSlug.ALBUM_COVER_INVALID, subject=album.dpath, detail=detail)
        elif len(covers) > 1:
            detail = f"{len(covers)} +cover photos (need exactly one) — scan aborts here"
            yield Finding(check=CheckSlug.ALBUM_COVER_INVALID, subject=album.dpath, detail=detail)


def check_metadata_parses(db: SqliteDatabase) -> Iterator[Finding]:
    """The album/photo markdown readers hard-abort scan on a malformed table, a duplicate photo
    url, or a duplicate cover claim. Surface those here as a clean finding rather than a scan
    traceback — and so the reader-backed checks below can assume the files parse."""
    album_reader = MarkdownAlbumMetadataReader(DEFAULT_ALBUMS_MARKDOWN_PATH)
    try:
        list(album_reader.list_album_metadata(db))
    except ValueError as err:
        yield Finding(
            check=CheckSlug.METADATA_PARSE_ERROR,
            subject=DEFAULT_ALBUMS_MARKDOWN_PATH,
            detail=str(err),
        )

    photo_reader = MarkdownTablePhotoMetadataReader(DEFAULT_PHOTOS_MARKDOWN_PATH)
    try:
        list(photo_reader.read_photo_metadata(db))
    except ValueError as err:
        yield Finding(
            check=CheckSlug.METADATA_PARSE_ERROR,
            subject=DEFAULT_PHOTOS_MARKDOWN_PATH,
            detail=str(err),
        )


def check_photos_missing_phash(db: SqliteDatabase) -> Iterator[Finding]:
    """Photo metadata (ratings, subjects) is keyed by phash, so a photo with no phash can hold no
    metadata and never appears in photos.md or the labeller — usually a symptom of a broken scan."""
    query = """
    select p.fpath from photos p
    where not exists (select 1 from phashes h where h.fpath = p.fpath)
    """
    for row in db.conn.execute(query):
        detail = "no perceptual hash — cannot hold metadata; invisible in photos.md and labeller"
        yield Finding(check=CheckSlug.PHOTO_MISSING_PHASH, subject=row[0], detail=detail)


def resolvable_album_dpaths(db: SqliteDatabase) -> set[str]:
    """Album dpaths for which albums.md yields a non-empty permalink — i.e. what ReadAlbums writes.

    The permalink target must be truthy: a blank permalink cell resolves the dpath but stores an
    empty id, which makes view_album_data.id null and drops the album (and its photos) from triples.
    """
    reader = MarkdownAlbumMetadataReader(DEFAULT_ALBUMS_MARKDOWN_PATH)
    rows = reader.list_album_metadata(db)
    return {row.src for row in rows if row.relation == "permalink" and row.src and row.target}


def rated_photo_urls(db: SqliteDatabase) -> set[str]:
    """Thumbnail urls that photos.md gives a non-empty rating — i.e. what ReadPhotos will record."""
    reader = MarkdownTablePhotoMetadataReader(DEFAULT_PHOTOS_MARKDOWN_PATH)
    return {row.url for row in reader.read_photo_metadata(db) if row.rating}


def check_albums_missing_metadata(db: SqliteDatabase) -> Iterator[Finding]:
    """Report albums dropped from triples because albums.md cannot resolve their dpath."""
    try:
        resolvable = resolvable_album_dpaths(db)
    except ValueError:
        return  # a malformed albums.md is reported by check_metadata_parses
    for album in db.album_data_view().list():
        if album.dpath in resolvable:
            continue
        count = album.photos_count
        noun = "photo" if count == 1 else "photos"
        reason = "albums.md has no permalink id (blank, missing, or stale url)"
        detail = f"{reason} — album and its {count} {noun} dropped"
        yield Finding(check=CheckSlug.ALBUM_MISSING_METADATA, subject=album.dpath, detail=detail)


def check_photos_missing_rating(db: SqliteDatabase) -> Iterator[Finding]:
    """Photos with no rating in photos.md (missing row or blank rating) are unrated at publish."""
    try:
        rated = rated_photo_urls(db)
    except ValueError:
        return  # a malformed photos.md is reported by check_metadata_parses
    for photo in db.photo_data_table().list():
        if photo.thumbnail_url is None or photo.thumbnail_url in rated:
            continue
        detail = "no rating in photos.md — photo needs a rating before publishing"
        yield Finding(check=CheckSlug.PHOTO_MISSING_RATING, subject=photo.fpath, detail=detail)


def check_photos_missing_main_image(db: SqliteDatabase) -> Iterator[Finding]:
    """Photos with no mid_image_lossy rendition render as a broken image on the site."""
    for photo in db.photo_data_table().list():
        if photo.mid_image_lossy_url is not None:
            continue
        detail = "no mid_image_lossy rendition — image broken on site (not yet uploaded?)"
        yield Finding(check=CheckSlug.PHOTO_MISSING_MAIN_IMAGE, subject=photo.fpath, detail=detail)


def check_graph_contract(db: SqliteDatabase) -> Iterator[Finding]:
    """Validate the exact processed publication triples against the SHACL contract."""
    yield from validate_triples(list(read_triples(db)))


def skip_graph_contract(db: SqliteDatabase) -> Iterator[Finding]:
    """Register the graph rule description without running SHACL twice."""
    return iter(())


CHECKS: list[Check] = [
    Check(
        slug=CheckSlug.ALBUM_COVER_INVALID,
        description="Album has no unique +cover photo (breaks scan)",
        run=check_albums_cover,
    ),
    Check(
        slug=CheckSlug.METADATA_PARSE_ERROR,
        description="albums.md / photos.md fails to parse (breaks scan)",
        run=check_metadata_parses,
    ),
    Check(
        slug=CheckSlug.PHOTO_MISSING_PHASH,
        description="Photo has no perceptual hash",
        run=check_photos_missing_phash,
    ),
    Check(
        slug=CheckSlug.ALBUM_MISSING_METADATA,
        description="Album not resolvable from albums.md",
        run=check_albums_missing_metadata,
    ),
    Check(
        slug=CheckSlug.PHOTO_MISSING_RATING,
        description="Photo has no rating in photos.md",
        run=check_photos_missing_rating,
    ),
    Check(
        slug=CheckSlug.PHOTO_MISSING_MAIN_IMAGE,
        description="Photo missing its main rendition",
        run=check_photos_missing_main_image,
    ),
    Check(
        slug=CheckSlug.ANIMAL_MISSING_NAME,
        description="Referenced animal has no name definition",
        run=check_graph_contract,
    ),
    Check(
        slug=CheckSlug.TRIPLE_GRAPH_INVALID,
        description="Published triple graph violates its SHACL contract",
        run=skip_graph_contract,
    ),
]
