"""Album for a photo-album""" ""

from typing import Optional
from dataclasses import dataclass
from functools import lru_cache
import xattr

from .constants import (
    ATTR_ALBUM_TITLE,
    ATTR_ALBUM_DESCRIPTION,
    ATTR_ALBUM_COVER,
    ATTR_ALBUM_GEOLOCATION,
    ATTR_ALBUM_PERMALINK,
)
from typing import Dict, TypeVar


@dataclass
class AlbumMetadata:
    """A dataclass representing metadata for an album"""

    fpath: str
    title: str
    permalink: str
    cover: str
    description: str = ""
    geolocation: str = ""


T = TypeVar("T")


class Album:
    """A photo-album"""

    path: str

    def __init__(self, path: str):
        self.path = path

    @lru_cache(maxsize=None)
    def list_xattrs(self) -> set:
        """List all extended-attributes on the album"""

        return {attr for attr in xattr.listxattr(self.path)}

    @lru_cache(maxsize=None)
    def has_xattr(self, attr: str) -> bool:
        """Check if an extended-attribute exists on the album"""

        return attr in self.list_xattrs()

    @lru_cache(maxsize=None)
    def get_xattr(self, attr: str, default: Optional[T] = None) -> str | Optional[T]:
        """Get an extended-attribute from the album"""

        if default is not None and not self.has_xattr(attr):
            return default

        return xattr.getxattr(self.path, attr).decode("utf-8")

    def set_xattrs(self, attrs: Dict[str, str]) -> None:
        """Set metadata on the album as extended-attributes"""

        for attr, value in attrs.items():
            xattr.setxattr(self.path, attr.encode(), value.encode())

    def get_metadata(self) -> Optional[AlbumMetadata]:
        """Get metadata from an image as extended-attributes"""

        # No metadata is set on the album; ignore it.
        if not self.has_xattr(ATTR_ALBUM_TITLE):
            return None

        cover = self.get_xattr(ATTR_ALBUM_COVER)
        permalink = self.get_xattr(ATTR_ALBUM_PERMALINK, "")

        return AlbumMetadata(
            fpath=self.path,
            title=self.get_xattr(ATTR_ALBUM_TITLE),
            permalink=permalink,
            description=self.get_xattr(ATTR_ALBUM_DESCRIPTION, ""),
            cover=cover,
            geolocation=self.get_xattr(ATTR_ALBUM_GEOLOCATION, ""),
        )
