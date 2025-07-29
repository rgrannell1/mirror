"""Photo albums"""

from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Any, Iterator, List
from mirror.config import ALBUM_METADATA_FILE
from mirror.media import IMedia
from mirror.mirror_types import IModel
from mirror.photo import Photo
from mirror.video import Video
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
class AlbumDataModel:
    """Represents the data in the `album_data` view"""

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
    def from_row(cls, row) -> "AlbumDataModel":
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

        return AlbumDataModel(
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
            flags=flags.split(",") if flags else [],
            description=description,
        )
