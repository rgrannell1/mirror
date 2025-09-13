"""A file for interacting with photos"""

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from typing import Any, List

from mirror.config import PHOTO_METADATA_FILE
from mirror.constants import SUPPORTED_IMAGE_EXTENSIONS
from mirror.mirror_types import IModel


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
    mosaic_colours: str
    full_image: str
    png_url: str
    mid_image_lossy_url: str
    created_at: int  # todo is this type correct? Schema validate
    phash: str

    def get_ctime(self) -> datetime:
        try:
            return datetime.strptime(str(self.created_at), "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.fromtimestamp(os.path.getctime(self.fpath), tz=timezone.utc)

    @classmethod
    def from_row(cls, row: List) -> "PhotoModel":
        (
            fpath,
            album_id,
            tags,
            thumbnail_url,
            thumbnail_mosaic_url,
            mosaic_colours,
            png_url,
            full_image,
            mid_image_lossy_url,
            created_at,
            phash,
        ) = row

        return PhotoModel(
            fpath=fpath,
            album_id=album_id,
            tags=tags.split(","),
            thumbnail_url=thumbnail_url,
            thumbnail_mosaic_url=thumbnail_mosaic_url,
            mosaic_colours=mosaic_colours,
            full_image=full_image,
            png_url=png_url,
            mid_image_lossy_url=mid_image_lossy_url,
            created_at=created_at,
            phash=phash,
        )


class Photo:
    """A class representing a photo"""

    fpath: str
    IMAGE_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS

    def __init__(self, fpath: str):
        self.fpath = fpath

    @classmethod
    def is_a(cls, fpath: str) -> bool:
        return os.path.isfile(fpath) and fpath.endswith(cls.IMAGE_EXTENSIONS)


@dataclass
class PhotoMetadataModel(IModel):
    """Photo metadata database model"""

    fpath: str
    relation: str
    target: str

    @classmethod
    def from_row(cls, row: List) -> "PhotoMetadataModel":
        (fpath, relation, target) = row

        return PhotoMetadataModel(fpath=fpath, relation=relation, target=target)


@dataclass
class PhotoMetadataSummaryModel(IModel):
    """Photo metadata summary database model. Provided by tools which give semantic information about
    metadata"""

    url: str
    name: str
    genre: list[str]
    rating: str | None
    places: list[str]
    description: str | None
    subjects: list[str]
    covers: list[str]

    @classmethod
    def from_row(cls, row: List) -> "PhotoMetadataSummaryModel":
        (_, url, name, genre, rating, places, description, subjects, covers) = row

        return PhotoMetadataSummaryModel(
            url=url,
            name=name,
            genre=genre.split(",") if genre else [],
            rating=rating,
            places=places.split(",") if places else [],
            description=description,
            subjects=subjects.split(",") if subjects else [],
            covers=covers.split(",") if covers else [],
        )
    @classmethod
    @lru_cache
    def schema(cls) -> dict[str, Any]:
        with open(PHOTO_METADATA_FILE, "r") as f:
            return json.load(f)
