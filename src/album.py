
import xattr

from .constants import (
  ATTR_ALBUM_TITLE,
  ATTR_ALBUM_COVER,
)

class Album:
  """A photo-album"""

  def __init__(self, path):
    self.path = path

  def get_metadata(self):
    """Get metadata from an image as extended-attributes"""

    attrs = {attr for attr in xattr.listxattr(self.path)}

    if ATTR_ALBUM_TITLE not in attrs:
      return None

    return {
      'fpath': self.path,
      'title': xattr.getxattr(self.path, ATTR_ALBUM_TITLE).decode('utf-8'),
      'cover': xattr.getxattr(self.path, ATTR_ALBUM_COVER).decode('utf-8')
    }

  def set_metadata(self, attrs):
    """Set metadata on the album as extended-attributes"""

    for attr, value in attrs.items():
      xattr.setxattr(self.path, attr.encode(), value.encode())
