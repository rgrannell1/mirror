"""A file for dealing with metadata for albums and photos"""

import re
import sys
import csv
from jsonschema import validate

from collections import defaultdict
from typing import Iterator, Protocol

from mirror.album import AlbumMetadataModel
from mirror.database import SqliteDatabase
from mirror.photo import PhotoMetadataModel, PhotoMetadataSummaryModel
from typing import TypedDict, Optional


# Protocols defining how metadata can be communicated to/from other locations
class IAlbumMetadataReader(Protocol):
    """Interface for listing out album metadata"""

    def list_album_metadata(self, db: SqliteDatabase) -> Iterator[AlbumMetadataModel]: ...


class IAlbumMetadataWriter(Protocol):
    """Interface for storing album metadata"""

    def write_album_metadata(self, db: SqliteDatabase) -> None: ...


class IPhotoMetadataReader(Protocol):
    """Interface for listing out photo metadata"""

    def list_photo_metadata(self, db: SqliteDatabase) -> Iterator[PhotoMetadataModel]: ...


class IPhotoMetadataWriter(Protocol):
    """Interface for storing photo metadata"""

    def write_photo_metadata(self, db: SqliteDatabase) -> None: ...


class MarkdownAlbumMetadataWriter(IAlbumMetadataWriter):
    def _contentful_published_albums(self, db: SqliteDatabase) -> set[str]:
        """Retrieve a set of album paths that have content in the database"""

        albums = set()

        for data in db.album_data_view().list():
            if data.photos_count > 0 or data.videos_count > 0:
                albums.add(data.dpath)

        return albums

    def relations_by_album(self, db):
        class AlbumFieldsDict(TypedDict):
            embedding: Optional[str]
            summary: Optional[str]
            country: list[str]
            permalink: Optional[str]
            title: Optional[str]

        by_album: dict[str, AlbumFieldsDict] = defaultdict(
            lambda: {
                "embedding": None,
                "summary": "",
                "country": [],
                "permalink": "",
                "title": "",
            }
        )

        album_data_table = db.album_data_table()
        published_albums = self._contentful_published_albums(db)

        for dpath in published_albums:
            # find an embedding as a minimum

            album_data = db.album_data_table().get_album_data_by_dpath(dpath)

            by_album[dpath] = {
                "embedding": album_data.thumbnail_url if album_data else None,
                "summary": "",
                "country": [],
                "permalink": "",
                "title": "",
            }

        # For every album with metadata saved from the albums metadata file,
        # map this data into a dpath -> dict structure
        albums = list(db.media_metadata_table().list_albums())

        for data in sorted(albums, key=lambda album: album.src):
            dpath = data.src
            relation = data.relation
            target = data.target

            # skip non-published albums
            if dpath not in published_albums:
                continue

            album_data = album_data_table.get_album_data_by_dpath(dpath)
            # not ideal, as it requires manually nominating a cover file first
            if not album_data:
                continue

            url = album_data.thumbnail_url

            by_album[dpath]["embedding"] = url
            if relation in {"county", "country"}:
                by_album[dpath]["country"] = re.split(r"\s*,\s*", target) if target else []
            else:
                by_album[dpath][relation] = target

        return by_album

    def write_album_metadata(self, db: SqliteDatabase) -> None:
        headers = [
            "embedding",
            "title",
            "permalink",
            "country",
            "summary",
        ]

        by_album = self.relations_by_album(db)

        # sort albums by file-path
        sorted_albums = sorted(by_album.items(), key=lambda pair: pair[0])

        # Print as markdown table
        print("| " + " | ".join(headers) + " |")
        print("| " + " | ".join(["---"] * len(headers)) + " |")

        for embedding, album_data in sorted_albums:
            row = [
                f"![]({album_data['embedding']})",
                album_data["title"] or "",
                album_data["permalink"] or "",
                ",".join(album_data["country"]) if album_data["country"] else "",
                album_data["summary"] or "",
            ]
            print("| " + " | ".join(row) + " |")


class MarkdownAlbumMetadataReader(IAlbumMetadataReader):
    fpath: str

    def __init__(self, fpath: str):
        self.fpath = fpath

    def list_album_metadata(self, db: SqliteDatabase) -> Iterator[AlbumMetadataModel]:
        reader = csv.reader(sys.stdin, delimiter="|")
        headers = next(reader)[1:-1]

        if headers[0].strip() != "embedding":
            raise ValueError("Invalid header in Markdown table")

        next(reader)

        album_data = db.album_data_view()

        for row in reader:
            if len(row) < 5:
                continue
            row = [cell.strip() for cell in row]
            _, embedding, title, permalink, country, summary, _ = row

            thumbnail_url = embedding[4:-1]
            dpath = album_data.album_dpath_from_thumbnail_url(thumbnail_url)

            item = {
                "fpath": dpath,
                "title": title,
                "permalink": permalink,
                "country": re.split(r"\s*,\s*", country) if country else [],
                "summary": summary or "",
            }

            validate(item, AlbumMetadataModel.schema())
            src = item.get("fpath")

            if not src:
                continue

            for key, val in item.items():
                if key == "fpath":
                    continue

                yield AlbumMetadataModel(
                    src=src,
                    src_type="photo",
                    # sign
                    relation="county" if key == "country" else key,
                    target=",".join(val) if isinstance(val, list) else val,
                )


class MarkdownTablePhotoMetadataWriter:
    def write_photo_metadata(self, db: SqliteDatabase) -> None:
        headers = [
            "embedding",
            "name",
            "genre",
            "rating",
            "places",
            "description",
            "subjects",
            "cover"
        ]

        rows = []

        db.album_contents_view()
        db.photo_metadata_view()
        db.photo_metadata_table()

        for summary in db.photo_metadata_summary_view().list():
            subjects = list({sub for sub in summary.subjects}) or []
            places = list({sub for sub in summary.places}) or []

            if not summary.name:
                raise ValueError(f"Photo missing an album name: {summary.url}")

            rows.append(
                [
                    f"![]({summary.url})",
                    summary.name,
                    ",".join(summary.genre),
                    summary.rating or "",
                    ",".join(places),
                    summary.description or "",
                    ",".join(subjects),
                    ""
                ]
            )

        print("| " + " | ".join(headers) + " |")
        print("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            print("| " + " | ".join(row) + " |")


class MarkdownTablePhotoMetadataReader(IPhotoMetadataReader):
    fpath: str

    def __init__(self, fpath: str):
        self.fpath = fpath

    def read_photo_metadata(self, db: SqliteDatabase) -> Iterator[PhotoMetadataSummaryModel]:
        """Read photo metadata from a Markdown table"""

        reader = csv.reader(sys.stdin, delimiter="|")
        headers = next(reader)[1:-1]

        if headers[0].strip() != "embedding":
            raise ValueError("Invalid header in Markdown table")

        next(reader)

        unique_urls = set()
        unique_covers = set()

        for row in reader:
            if len(row) < 8:
                continue
            row = [cell.strip() for cell in row]

            _, embedding, title, genre, rating, places, description, subjects, cover, _ = row

            url = embedding[4:-1]
            if url in unique_urls:
                raise ValueError(f"Duplicate photo URL in metadata: {url}")
            unique_urls.add(url)

            covers = re.split(r"\s*,\s*", cover) if cover else []
            for cov in covers:
                if cov in unique_covers:
                    raise ValueError(f"Multiple images claiming to be cover for {cov}")
                unique_covers.add(cov)


            item = {
                "thumbnail_url": url,
                "album": title,
                "genre": re.split(r"\s*,\s*", genre) if genre else [],
                "places": re.split(r"\s*,\s*", places) if places else [],
                "rating": rating if rating else None,
                "subjects": re.split(r"\s*,\s*", subjects) if subjects else [],
                "description": description or "",
                "covers": covers,
            }

            validate(item, PhotoMetadataSummaryModel.schema())

            yield PhotoMetadataSummaryModel(
                url=url,
                name=title,
                genre=item['genre'],
                rating=item['rating'],
                places=item['places'],
                description=item['description'],
                subjects=item['subjects'],
                covers=item['covers']
            )
