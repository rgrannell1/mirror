
import os
import xattr
from typing import TypeVar, Optional

T = TypeVar('T')

class Media:
  """An abstract class for media (video, images)."""

  @classmethod
  def is_image(cls, path) -> bool:
    """Check if a given file path is an image."""

    image_extensions = ('.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG')
    return os.path.isfile(path) and path.endswith(image_extensions)

  def name(self) -> str:
    """Get the basename of the media."""

    return os.path.basename(self.path)

  def dirname(self) -> str:
    """Get the directory name of the media."""

    return os.path.dirname(self.path)

  def exists(self) -> bool:
    """Check if a piece of media exists."""

    return os.path.exists(self.path)

  def get_exif_attr(self, attr: str, default: Optional[T] = None) -> str | Optional[T]:
    """Get an EXIF attribute from an image"""

    attrs = {attr for attr in xattr.listxattr(self.path)}

    if attr in attrs:
      return xattr.getxattr(self.path, attr).decode('utf-8')

    return default

  def set_xattr_attr(self, attr, value):
    """Set an extended-attribute on an image"""
    try:
      xattr.setxattr(self.path, attr.encode(), value.encode())
    except Exception as err:
      raise ValueError(f"failed to set xattr {attr} on {self.path}") from err
