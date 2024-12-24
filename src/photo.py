"""A file for interacting with photos"""

from dataclasses import dataclass
import hashlib
import os
from typing import List
from PIL import Image

from model import IModel


class PhotoContent:
    """Holds the content of an image"""

    content: bytes

    def __init__(self, content: bytes) -> None:
        self.content = content

    def hash(self) -> str:
        return hashlib.md5(self.content).hexdigest()[:10]


@dataclass
class EncodedPhotoModel(IModel):
    """Encoded photo database model"""

    fpath: str
    mimetype: str
    role: str
    url: str

    @classmethod
    def from_row(cls, row: List) -> "EncodedPhotoModel":
        (fpath, mimetype, role, url) = row

        return EncodedPhotoModel(fpath=fpath, mimetype=mimetype, role=role, url=url)


@dataclass
class PhotoModel(IModel):
    """Photo database model"""

    fpath: str
    album_id: str
    tags: List[str]
    thumbnail_url: str
    thumbnail_mosaic_url: str
    full_image: str
    created_at: int
    phash: str

    @classmethod
    def from_row(cls, row: List) -> "PhotoModel":
        (fpath, album_id, tags, thumbnail_url, thumbnail_mosaic_url, full_image, created_at, phash) = row

        return PhotoModel(
            fpath=fpath,
            album_id=album_id,
            tags=tags.split(","),
            thumbnail_url=thumbnail_url,
            thumbnail_mosaic_url=thumbnail_mosaic_url,
            full_image=full_image,
            created_at=created_at,
            phash=phash
        )


class Photo:
    """A class representing a photo"""

    fpath: str
    IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")

    def __init__(self, fpath: str):
        self.fpath = fpath

    @classmethod
    def is_a(cls, fpath: str) -> bool:
        return os.path.isfile(fpath) and fpath.endswith(cls.IMAGE_EXTENSIONS)
