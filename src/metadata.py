"""A file for dealing with metadata for albums and photos"""

import json
from jsonschema import validate

from collections import defaultdict
from typing import Iterator, Protocol

from src.album import AlbumMetadataModel
from src.database import IDatabase
from src.photo import PhotoMetadataModel
from typing import TypedDict, Optional


# Protocols defining how metadata can be communicated to/from other locations
class IAlbumMetadataReader(Protocol):
    def list_album_metadata(self, db: IDatabase) -> Iterator[AlbumMetadataModel]: ...


class IAlbumMetadataWriter(Protocol):
    def write_album_metadata(self, db: IDatabase) -> None: ...


class IPhotoMetadataReader(Protocol):
    def list_photo_metadata(self, db: IDatabase) -> Iterator[PhotoMetadataModel]: ...


class IPhotoMetadataWriter(Protocol):
    def write_photo_metadata(self, db: IDatabase) -> None: ...


class JSONAlbumMetadataWriter(IAlbumMetadataWriter):
    def _contentful_published_albums(self, db: IDatabase) -> set[str]:
        """Retrieve a set of album paths that have content in the database"""

        albums = set()

        for data in db.list_album_data():
            if data.photos_count > 0 or data.videos_count > 0:
                albums.add(data.dpath)

        return albums

    def write_album_metadata(self, db: IDatabase) -> None:
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
            if relation == "county":
                by_album[album_fpath]["country"] = target.split(r"[ ]*,[ ]*") if target else []
            else:
                by_album[album_fpath][relation] = target

        sorted_albums = sorted(by_album.items(), key=lambda pair: pair[0])

        print(json.dumps([pair[1] for pair in sorted_albums], indent=2, ensure_ascii=False))


class JSONAlbumMetadataReader(IAlbumMetadataReader):
    def list_album_metadata(self, db: IDatabase) -> Iterator[AlbumMetadataModel]:
        """Read album metadata from a JSON file"""

        ...
