"""Photo albums"""

from dataclasses import dataclass
import os
from typing import Iterator, List
from src.media import IMedia
from src.model import IModel
from src.photo import Photo
from src.video import Video


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
    thumbnail_mosaic_url: str
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
            flags,
            description,
        ) = row

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
            flags=flags.split(","),
            description=description,
        )
