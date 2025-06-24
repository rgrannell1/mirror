"""A file for dealing with metadata for albums and photos"""

import json
import re
import sys
import csv
from jsonschema import validate

from collections import defaultdict
from typing import Iterator, Protocol

from src.album import AlbumMetadataModel
from src.database import SqliteDatabase
from src.photo import PhotoMetadataModel, PhotoMetadataSummaryModel
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


class JSONAlbumMetadataWriter(IAlbumMetadataWriter):
    def _contentful_published_albums(self, db: SqliteDatabase) -> set[str]:
        """Retrieve a set of album paths that have content in the database"""

        albums = set()

        for data in db.list_album_data():
            if data.photos_count > 0 or data.videos_count > 0:
                albums.add(data.dpath)

        return albums

    def write_album_metadata(self, db: SqliteDatabase) -> None:
        """Write album metadata to a CSV file"""

        class AlbumFieldsDict(TypedDict):
            fpath: Optional[str]
            summary: Optional[str]
            country: list[str]
            permalink: Optional[str]
            title: Optional[str]

        by_album: dict[str, AlbumFieldsDict] = defaultdict(
            lambda: {
                "fpath": None,
                "summary": "",
                "country": [],
                "permalink": "",
                "title": "",
            }
        )
        published_albums = self._contentful_published_albums(db)

        for data in db.list_album_metadata():
            album_fpath = data.src
            relation = data.relation
            target = data.target

            if album_fpath not in published_albums:
                continue

            by_album[album_fpath]["fpath"] = album_fpath
            if relation in {"county", "country"}:
                by_album[album_fpath]["country"] = re.split(r"\s*,\s*", target) if target else []
            else:
                by_album[album_fpath][relation] = target

        sorted_albums = sorted(by_album.items(), key=lambda pair: pair[0])

        print(json.dumps([pair[1] for pair in sorted_albums], indent=2, ensure_ascii=False))


class JSONAlbumMetadataReader(IAlbumMetadataReader):
    fpath: str

    def __init__(self, fpath: str):
        self.fpath = fpath

    def list_album_metadata(self, db: SqliteDatabase) -> Iterator[AlbumMetadataModel]:
        """Read album metadata from a JSON file"""

        with open(self.fpath, "r", encoding="utf-8") as conn:
            data = json.load(conn)

            for item in data:
                validate(item, AlbumMetadataModel.schema())

                src = item.get("fpath")
                for key, val in item.items():
                    if key == "fpath":
                        continue

                    yield AlbumMetadataModel(
                        src=src,
                        src_type=key,
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
        ]

        rows = []

        for summary in db.list_photo_metadata_summary():
            rows.append(
                [
                    f"![]({summary.url})",
                    summary.name,
                    ",".join(summary.genre),
                    summary.rating or "",
                    ",".join(summary.places),
                    summary.description or "",
                    ",".join(summary.subjects),
                ]
            )

        print("| " + " | ".join(headers) + " |")
        print("| " + " | ".join(["---"] * len(headers)) + " |")

        for row in rows:
            print("| " + " | ".join(row) + " |")


class MarkdownTablePhotoMetadataReader:
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

        for row in reader:
            if len(row) < 7:
                continue
            row = [cell.strip() for cell in row]

            _, embedding, title, genre, rating, places, description, subjects, _ = row

            url = embedding[4:-1]

            yield PhotoMetadataSummaryModel(
                url=url,
                name=title,
                genre=re.split(r"\s*,\s*", genre) if genre else [],
                rating=rating if rating else None,
                places=re.split(r"\s*,\s*", places) if places else [],
                description=description or "",
                subjects=re.split(r"\s*,\s*", subjects) if subjects else [],
            )
