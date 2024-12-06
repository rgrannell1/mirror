"""The root class of media types"""

from typing import Protocol

from photo import Photo
from video import Video


class IMedia(Protocol):
    fpath: str

    @classmethod
    def is_a(cls, fpath: str) -> bool:
        return Photo.is_a(fpath) or Video.is_a(fpath)


class Media(IMedia):
    """Base class of photos and videos"""

    def __init__(self, fpath: str) -> None:
        self.fpath = fpath

    @classmethod
    def is_a(cls, fpath: str) -> bool:
        return Photo.is_a(fpath) or Video.is_a(fpath)
