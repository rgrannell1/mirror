"""Album for a photo-album"""""

import xattr

from .constants import (
  ATTR_ALBUM_TITLE,
  ATTR_ALBUM_DESCRIPTION,
  ATTR_ALBUM_COVER,
)
from typing import Dict

class Album:
  """A photo-album"""

  def __init__(self, path):
    self.path = path

  def get_metadata(self) -> Dict:
    """Get metadata from an image as extended-attributes"""

    attrs = {attr for attr in xattr.listxattr(self.path)}

    # No metadata is set on the album
    if ATTR_ALBUM_TITLE not in attrs:
      return None

    description = ""
    if ATTR_ALBUM_DESCRIPTION in attrs:
      description = xattr.getxattr(self.path, ATTR_ALBUM_DESCRIPTION).decode('utf-8')

    return {
      'fpath': self.path,
      'title': xattr.getxattr(self.path, ATTR_ALBUM_TITLE).decode('utf-8'),
      'description': description,
      'cover': xattr.getxattr(self.path, ATTR_ALBUM_COVER).decode('utf-8')
    }

  def set_metadata(self, attrs):
    """Set metadata on the album as extended-attributes"""

    for attr, value in attrs.items():
      xattr.setxattr(self.path, attr.encode(), value.encode())
