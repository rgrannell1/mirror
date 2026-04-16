"""A class for interacting with videos"""

from dataclasses import dataclass
import os
from typing import List, Optional

from mirror.models.mirror_types import IModel


@dataclass
class EncodedVideoModel(IModel):
    fpath: str
    mimetype: str
    role: str
    url: str

    @classmethod
    def from_row(cls, row: List) -> "EncodedVideoModel":
        (fpath, mimetype, role, url) = row

        return EncodedVideoModel(fpath=fpath, mimetype=mimetype, role=role, url=url)


@dataclass
class VideoModel(IModel):
    fpath: str
    album_id: str
    tags: List[str]
    description: str
    video_url_unscaled: str
    video_url_1080p: str
    video_url_720p: str
    video_url_480p: str
    poster_url: str

    @classmethod
    def from_row(cls, row: List) -> "VideoModel":
        (
            fpath,
            album_id,
            tags,
            description,
            video_url_unscaled,
            video_url_1080p,
            video_url_720p,
            video_url_480p,
            poster_url,
        ) = row

        return VideoModel(
            fpath=fpath,
            album_id=album_id,
            tags=tags,
            description=description,
            video_url_unscaled=video_url_unscaled,
            video_url_1080p=video_url_1080p,
            video_url_720p=video_url_720p,
            video_url_480p=video_url_480p,
            poster_url=poster_url,
        )


@dataclass
class VideoMetadataSummaryModel(IModel):
    """Video metadata summary model — mirrors PhotoMetadataSummaryModel."""

    url: str
    name: str
    genre: List[str]
    rating: Optional[str]
    places: List[str]
    description: Optional[str]
    subjects: List[str]
    covers: List[str]
    fpath: Optional[str] = None

    @classmethod
    def from_row(cls, row: List) -> "VideoMetadataSummaryModel":
        (fpath, url, name, genre, rating, places, description, subjects, covers) = row

        return VideoMetadataSummaryModel(
            url=url,
            name=name,
            fpath=fpath,
            genre=genre.split(",") if genre else [],
            rating=rating,
            places=places.split(",") if places else [],
            description=description,
            subjects=subjects.split(",") if subjects else [],
            covers=covers.split(",") if covers else [],
        )


class Video:
    """Represents a video file"""

    fpath: str

    VIDEO_EXTENSIONS = (".mp4", ".MP4")

    def __init__(self, fpath: str):
        self.fpath = fpath

    @classmethod
    def is_a(cls, fpath: str) -> bool:
        return os.path.isfile(fpath) and fpath.endswith(cls.VIDEO_EXTENSIONS)
