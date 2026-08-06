"""Album views → semantic triples for publish."""

from datetime import datetime
from typing import TYPE_CHECKING, Iterator

import markdown  # type: ignore

from mirror.commons.constants import DATE_FORMAT, MISCELLANEOUS_ALBUM_ID
from mirror.commons.dates import date_range
from mirror.commons.utils import short_cdn_url
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase


def album_photo_date_span(db: "SqliteDatabase", album) -> tuple[datetime, datetime] | None:
    """Fallback: derive min/max from photo ctime when EXIF-derived album dates
    are missing. This prevents publishing albums with partial triples."""
    min_dt: datetime | None = None
    max_dt: datetime | None = None

    for photo in db.photo_data_table().list():
        if photo.album_id != album.id:
            continue

        ctime = photo.get_ctime()
        if min_dt is None or ctime < min_dt:
            min_dt = ctime
        if max_dt is None or ctime > max_dt:
            max_dt = ctime

    # If we still can't compute dates, the album must be skipped.
    if min_dt is None or max_dt is None:
        return None

    return min_dt, max_dt


def album_date_span(db: "SqliteDatabase", album) -> tuple[datetime, datetime] | None:
    """The album's EXIF date span, falling back to photo ctimes."""
    if album.min_date is not None and album.max_date is not None:
        return (
            datetime.strptime(album.min_date, DATE_FORMAT),
            datetime.strptime(album.max_date, DATE_FORMAT),
        )

    return album_photo_date_span(db, album)


def album_date_triples(source: str, min_dt: datetime, max_dt: datetime) -> Iterator[SemanticTriple]:
    """Date triples for one album."""
    yield SemanticTriple(source, "min_date", str(int(min_dt.timestamp() * 1000)))
    yield SemanticTriple(source, "max_date", str(int(max_dt.timestamp() * 1000)))
    yield SemanticTriple(source, "date_range", date_range(min_dt, max_dt, short=False))
    yield SemanticTriple(source, "short_date_range", date_range(min_dt, max_dt, short=True))


def album_triples(album, min_dt: datetime, max_dt: datetime) -> Iterator[SemanticTriple]:
    """Publishable triples for one album."""
    description = markdown.markdown(album.description) if album.description else ""
    countries = [flag for flag in album.flags if flag.startswith("urn:")]
    source = f"urn:ró:album:{album.id}"

    yield SemanticTriple(source, "name", album.name)
    yield SemanticTriple(source, "photos_count", album.photos_count)
    yield SemanticTriple(source, "videos_count", album.videos_count)
    yield from album_date_triples(source, min_dt, max_dt)
    yield SemanticTriple(source, "thumbnail_url", short_cdn_url(album.thumbnail_url))
    yield SemanticTriple(source, "mosaic", album.mosaic_colours)
    for country in countries:
        yield SemanticTriple(source, "country", country)
    yield SemanticTriple(source, "description", description)


class AlbumTriples:
    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        # newest first, so the site's streaming render fills the top of the
        # albums page earliest
        albums = sorted(
            db.album_data_view().list(),
            key=lambda album: album.max_date or "",
            reverse=True,
        )

        for album in albums:
            # miscellaneous is a hidden album; its photos publish, but only a
            # hidden marker publishes for the album itself, so the site never
            # links to an album page for it
            if album.id == MISCELLANEOUS_ALBUM_ID:
                yield SemanticTriple(f"urn:ró:album:{album.id}", "hidden", "true")
                continue

            if album.id is None:
                continue

            span = album_date_span(db, album)
            if span is None:
                continue

            yield from album_triples(album, span[0], span[1])
