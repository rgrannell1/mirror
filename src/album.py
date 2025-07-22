"""Photo albums"""

from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Any, Iterator, List, Optional
from src.config import ALBUM_METADATA_FILE
from src.media import IMedia
from src.mirror_types import IModel
from src.photo import Photo
from src.video import Video
import json


class Album:
    """A class representing a photo album. This corresponds to a folder with a `Published`
    directory underneath"""

    def __init__(self, dpath: str):
        self.dpath = dpath

    def published_path(self) -> str:
        """Get the directory of published media"""
        return os.path.join(self.dpath, "Published")

    def published(self) -> bool:
        """Is there any published media?"""
        return os.path.isdir(self.published_path())

    def media(self) -> Iterator[IMedia]:
        """Yield all media from the photo-album"""

        if not self.published():
            return

        for fname in os.listdir(self.published_path()):
            fpath = os.path.join(self.published_path(), fname)

            if Photo.is_a(fpath):
                yield Photo(fpath)
            elif Video.is_a(fpath):
                yield Video(fpath)


@dataclass
class AlbumModel(IModel):
    id: str
    name: str
    dpath: str
    photos_count: int
    videos_count: int
    min_date: str
    max_date: str
    thumbnail_url: str
    # deprecated
    thumbnail_mosaic_url: str
    mosaic_colours: str
    flags: List[str]
    description: str

    @classmethod
    def from_row(cls, row) -> "AlbumModel":
        (
            id,
            name,
            dpath,
            photos_count,
            videos_count,
            min_date,
            max_date,
            thumbnail_url,
            thumbnail_mosaic_url,
            mosaic_colours,
            flags,
            description,
        ) = row

        if not flags:
            raise ValueError(f"Flags are empty for album {name} ({id}, {dpath})")

        return AlbumModel(
            id=id,
            name=name,
            dpath=dpath,
            photos_count=photos_count,
            videos_count=videos_count,
            min_date=min_date,
            max_date=max_date,
            thumbnail_url=thumbnail_url,
            thumbnail_mosaic_url=thumbnail_mosaic_url,
            mosaic_colours=mosaic_colours,
            flags=flags.split(","),
            description=description,
        )


@dataclass
class AlbumMetadataModel(IModel):
    src: str
    src_type: str
    relation: str
    target: str | None

    @classmethod
    def from_row(cls, row: list) -> "AlbumMetadataModel":
        return cls(
            src=row[0],
            src_type=row[1],
            relation=row[2],
            target=row[3],
        )

    @classmethod
    @lru_cache
    def schema(cls) -> dict[str, Any]:
        with open(ALBUM_METADATA_FILE, "r") as f:
            return json.load(f)


@dataclass
class AlbumDataModel(IModel):
    """Represents the data in the `album_data` view"""

    id: str
    name: str
    dpath: str
    photos_count: int
    videos_count: int
    min_date: str
    max_date: str
    thumbnail_url: str
    thumbnail_mosaic_url: str
    # country, but as ever misnamed
    flags: str
    description: Optional[str]

    @classmethod
    def from_row(cls, row: list) -> "AlbumDataModel":
        return cls(
            id=row[0],
            name=row[1],
            dpath=row[2],
            photos_count=row[3],
            videos_count=row[4],
            min_date=row[5],
            max_date=row[6],
            thumbnail_url=row[7],
            thumbnail_mosaic_url=row[8],
            flags=row[9],
            description=row[10],
        )
