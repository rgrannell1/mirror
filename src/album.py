"""Album for a photo-album"""""

from typing import Optional
from dataclasses import dataclass
from functools import lru_cache
import xattr

from .constants import (
  ATTR_ALBUM_TITLE,
  ATTR_ALBUM_DESCRIPTION,
  ATTR_ALBUM_COVER,
  ATTR_ALBUM_GEOLOCATION
)
from typing import Dict
from typing import TypeVar, Optional
@dataclass


class AlbumMetadata:
  """A dataclass representing metadata for an album"""
  fpath: str
  title: str
  cover: str
  description: str = ""
  geolocation: str = ""


T = TypeVar('T')

class Album:
  """A photo-album"""

  def __init__(self, path):
    self.path = path

  @lru_cache(maxsize=None)
  def list_xattrs(self) -> set:
    """List all extended-attributes on the album"""

    return {attr for attr in xattr.listxattr(self.path)}

  @lru_cache(maxsize=None)
  def has_xattr(self, attr) -> bool:
    """Check if an extended-attribute exists on the album"""

    return attr in self.list_xattrs()

  @lru_cache(maxsize=None)
  def get_xattr(self, attr: str, default: Optional[T] = None) -> str | Optional[T]:
    """Get an extended-attribute from the album"""

    if default is not None and not self.has_xattr(attr):
      return default

    return xattr.getxattr(self.path, attr).decode('utf-8')

  def get_metadata(self) -> Optional[AlbumMetadata]:
    """Get metadata from an image as extended-attributes"""

    # No metadata is set on the album; ignore it.
    if not self.has_xattr(ATTR_ALBUM_TITLE):
      return None

    return AlbumMetadata(
      fpath=self.path,
      title=self.get_xattr(ATTR_ALBUM_TITLE),
      description=self.get_xattr(ATTR_ALBUM_DESCRIPTION, ""),
      cover=self.get_xattr(ATTR_ALBUM_COVER),
      geolocation=self.get_xattr(ATTR_ALBUM_GEOLOCATION, "")
    )

  def set_metadata(self, attrs: Dict):
    """Set metadata on the album as extended-attributes"""

    for attr, value in attrs.items():
      xattr.setxattr(self.path, attr.encode(), value.encode())
