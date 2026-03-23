"""Album views → semantic triples for publish."""

from datetime import datetime
from typing import TYPE_CHECKING, Iterator

import markdown  # type: ignore

from mirror.commons.dates import date_range
from mirror.commons.utils import short_cdn_url
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase


class AlbumTriples:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        for album in db.album_data_view().list():
            min_dt: datetime | None = None
            max_dt: datetime | None = None

            if album.min_date is not None and album.max_date is not None:
                min_dt = datetime.strptime(album.min_date, "%Y:%m:%d %H:%M:%S")
                max_dt = datetime.strptime(album.max_date, "%Y:%m:%d %H:%M:%S")
            else:
                # Fallback: derive min/max from photo ctime when EXIF-derived album dates
                # are missing. This prevents publishing albums with partial triples.
                min_dt = None
                max_dt = None
                for photo in db.photo_data_table().list():
                    if photo.album_id != album.id:
                        continue
                    ctime = photo.get_ctime()
                    if min_dt is None or ctime < min_dt:
                        min_dt = ctime
                    if max_dt is None or ctime > max_dt:
                        max_dt = ctime

                # If we still can't compute dates, skip this album.
                if min_dt is None or max_dt is None:
                    continue

            assert min_dt is not None
            assert max_dt is not None

            description = markdown.markdown(album.description) if album.description else ""

            countries = []
            for flag in album.flags:
                country = flag
                country_id = country.lower().replace(" ", "-")
                countries.append(f"urn:ró:country:{country_id}")

            source = f"urn:ró:album:{album.id}"
            yield SemanticTriple(source, "name", album.name)
            yield SemanticTriple(source, "photos_count", album.photos_count)
            yield SemanticTriple(source, "videos_count", album.videos_count)
            yield SemanticTriple(source, "min_date", str(int(min_dt.timestamp() * 1000)))
            yield SemanticTriple(source, "max_date", str(int(max_dt.timestamp() * 1000)))
            yield SemanticTriple(source, "date_range", date_range(min_dt, max_dt, short=False))
            yield SemanticTriple(source, "short_date_range", date_range(min_dt, max_dt, short=True))
            yield SemanticTriple(source, "thumbnail_url", short_cdn_url(album.thumbnail_url))
            yield SemanticTriple(source, "mosaic", album.mosaic_colours)
            for country in countries:
                yield SemanticTriple(source, "country", country)
            yield SemanticTriple(source, "description", description)
