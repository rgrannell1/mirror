
import os
import xattr

from .constants import ATTR_TAG
from .tags import Tagfile

class PhotoDirectory:
  def __init__(self, path):
    self.path = path

  def list(self):
    """
    Recursively list all files under a given path.
    """
    images = []

    for dirpath, _, filenames in os.walk(self.path):
      for filename in filenames:
        image_path = os.path.join(dirpath, filename)

        if Photo.is_image(image_path):
          images.append(Photo(image_path))

    return images

  def list_tagfiles(self):
    for dirpath, _, filenames in os.walk(self.path):
      for filename in filenames:
        if filename == 'tags.md':
          fpath = os.path.join(dirpath, filename)

          for entry in Tagfile.read(fpath):
            yield entry

  def list_by_folder(self):
    dirs = {}

    for image in self.list():
      dirname = image.dirname()
      if dirname not in dirs:
        dirs[dirname] = []

      dirs[dirname].append(image)

    return dirs

class Photo:
  def __init__(self, path):
    self.path = path

  @classmethod
  def is_image(cls, path):
    """
    Check if a given file path is an image.
    """
    image_extensions = ('.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG')
    return os.path.isfile(path) and path.endswith(image_extensions)

  def name(self):
    """
    Get the basename of the photo.
    """
    return os.path.basename(self.path)

  def dirname(self):
    """
    Get the directory name of the photo.
    """
    return os.path.dirname(self.path)

  def get_metadata(self):
    attrs = {attr.decode('utf-8') for attr in xattr.listxattr(self.path)}

    if not ATTR_TAG in attrs:
      return {}

    tags = {tag.strip() for tag in xattr.getxattr(self.path, ATTR_TAG).decode('utf-8').split(',')}

    return {
      ATTR_TAG: tags
    }

  def set_metadata(self, attrs, tag_metadata):
    for attr, value in attrs.items():
      if attr != ATTR_TAG:
        xattr.setxattr(self.path, attr, value)
        continue

      tag_set = set()
      original_tags = value.split(',')

      for tag in original_tags:
        tag_set.add(tag)

        for new_tag in tag_metadata.add_tags(tag):
          tag_set.add(new_tag)

      xattr.setxattr(self.path, attr, ', '.join(tag_set))
