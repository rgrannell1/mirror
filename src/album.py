"""Album for a photo-album"""""

from functools import lru_cache
import xattr

from .constants import (
  ATTR_ALBUM_TITLE,
  ATTR_ALBUM_DESCRIPTION,
  ATTR_ALBUM_COVER,
  ATTR_ALBUM_GEOLOCATION
)
from typing import Dict

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
  def get_xattr(self, attr: str, default=None) -> str:
    """Get an extended-attribute from the album"""

    if default is not None and not self.has_xattr(attr):
      return default

    return xattr.getxattr(self.path, attr).decode('utf-8')

  def get_metadata(self) -> Dict:
    """Get metadata from an image as extended-attributes"""

    # No metadata is set on the album; ignore it.
    if not self.has_xattr(ATTR_ALBUM_TITLE):
      return None

    return {
      'fpath': self.path,
      'title': self.get_xattr(ATTR_ALBUM_TITLE),
      'description': self.get_xattr(ATTR_ALBUM_DESCRIPTION, ""),
      'cover': self.get_xattr(ATTR_ALBUM_COVER),
      'geolocation': self.get_xattr(ATTR_ALBUM_GEOLOCATION, "")
    }

  def set_metadata(self, attrs):
    """Set metadata on the album as extended-attributes"""

    for attr, value in attrs.items():
      xattr.setxattr(self.path, attr.encode(), value.encode())
